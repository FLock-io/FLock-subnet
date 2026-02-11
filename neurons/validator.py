# The MIT License (MIT)

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import argparse
import asyncio
import time

import torch
import typing
import random
import bittensor as bt
import numpy as np
import json
from flockoff.constants import Competition
from flockoff import constants
from flockoff.utils.chain import assert_registered
from flockoff.utils.git import check_and_update_code
from enum import Enum
from datetime import datetime, timezone, timedelta
from flockoff.validator.chain import (
    retrieve_model_metadata,
    set_weights_with_err_msg,
    reveal_weights_with_err_msg,
)
from flockoff.validator.validator_utils import load_jsonl, count_similar, select_winner
from flockoff.validator.trainer import (
    train_lora,
    download_dataset,
    check_valid_revision,
    get_hg_revision,
)
from flockoff.validator.database import ScoreDB
from dotenv import load_dotenv

load_dotenv()


class CompetitionState(Enum):
    SUBMISSION = "submission"
    VALIDATION = "validation"
    REWARDING = "rewarding"
    COMPLETED = "completed"


class Validator:
    @staticmethod
    def config():
        bt.logging.info("Parsing command line arguments")
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--blocks_per_epoch",
            type=int,
            default=360,
            help="Number of blocks to wait before setting weights.",
        )
        parser.add_argument(
            "--miner_sample_size",
            type=int,
            default=10,
            help="Number of miners to sample for each block.",
        )
        parser.add_argument(
            "--miner_duplicate_sample_size",
            type=int,
            default=50,
            help="Number of miners to sample for each block.",
        )
        parser.add_argument("--netuid", type=int, required=True, help="The subnet UID.")

        parser.add_argument(
            "--cache_dir",
            type=str,
            default="~/data/hf_cache",
            help="Directory to store downloaded model files.",
        )

        parser.add_argument(
            "--data_dir",
            type=str,
            default="~/data/training_data",
            help="Directory to store miner datasets.",
        )

        parser.add_argument(
            "--eval_data_dir",
            type=str,
            default="~/data/eval_data",
            help="Directory to store evaluation datasets.",
        )

        parser.add_argument(
            "--block_threshold",
            type=int,
            default=50,
            help="Number of blocks before epoch end to set weights.",
        )

        parser.add_argument(
            "--active_competition_id",
            type=str,
            default="",
            help="Set the initial winner parameters.",
        )

        parser.add_argument(
            "--reward_competition_id",
            type=str,
            default="",
            help="Set the initial winner parameters.",
        )

        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)
        bt.axon.add_args(parser)
        config = bt.config(parser)
        bt.logging.debug(f"Parsed config: {config}")
        return config

    def __init__(self):
        bt.logging.info("Initializing validator")
        self.config = Validator.config()

        bt.logging.info("Checking git branch")
        check_and_update_code()

        if self.config.cache_dir and self.config.cache_dir.startswith("~"):
            self.config.cache_dir = os.path.expanduser(self.config.cache_dir)

        if self.config.data_dir and self.config.data_dir.startswith("~"):
            self.config.data_dir = os.path.expanduser(self.config.data_dir)

        if self.config.eval_data_dir and self.config.eval_data_dir.startswith("~"):
            self.config.eval_data_dir = os.path.expanduser(self.config.eval_data_dir)

        bt.logging(config=self.config)
        bt.logging.info(f"Starting validator with config: {self.config}")

        # === Bittensor objects ====
        bt.logging.info("Initializing wallet")
        self.wallet = bt.wallet(config=self.config)
        bt.logging.info(f"Wallet initialized: {self.wallet}")
        bt.logging.info("Initializing subtensor")
        try:
            self.subtensor = bt.subtensor(config=self.config)
            bt.logging.info(f"Subtensor initialized: {self.subtensor}")
            bt.logging.info(f"Connected to network: {self.subtensor.network}")
            bt.logging.info(f"Chain endpoint: {self.subtensor.chain_endpoint}")
        except Exception as e:
            bt.logging.error(f"Failed to initialize subtensor: {e}")
            raise

        self.dendrite = bt.dendrite(wallet=self.wallet)

        bt.logging.info(f"Fetching metagraph for netuid: {self.config.netuid}")
        self.metagraph: bt.metagraph = self.subtensor.metagraph(self.config.netuid)
        torch.backends.cudnn.benchmark = True

        bt.logging.info("Checking if wallet is registered on subnet")
        self.uid = assert_registered(self.wallet, self.metagraph)

        bt.logging.info("Initializing weights tensor")


        self.uids_to_eval: typing.Dict[str, typing.List] = {}
        bt.logging.info("Initializing score database")
        self.score_db = ScoreDB("scores.db")
        bt.logging.info("Score database initialized")
        self.rng = np.random.default_rng()
        bt.logging.info("Validator initialization complete")

        self.last_competition_hash = None
        tempo = self.subtensor.tempo(self.config.netuid)
        self.last_submitted_epoch = (
                self.subtensor.get_next_epoch_start_block(self.config.netuid) - tempo
        )
        self.pending_reveal: typing.Optional[dict] = None
        self.active_competition_id: str = self.config.active_competition_id
        self.reward_competition_id: str = self.config.reward_competition_id
        self.use_yesterday_reward: bool = False

        if self.reward_competition_id != "":
            new_weights = torch.zeros_like(torch.tensor(self.metagraph.S), dtype=torch.float32)
            winner = self.score_db.get_competition_winner(self.reward_competition_id)
            if winner:
                new_weights[winner] = 1
            self.weights = new_weights
        else:
            self._comp_exists_in_db()


        bt.logging.info("Validator ready to run")

    def get_burn_uid(self):
        # Get the subtensor owner hotkey
        sn_owner_hotkey = self.subtensor.query_subtensor(
            "SubnetOwnerHotkey",
            params=[self.config.netuid],
        )
        bt.logging.info(f"SN Owner Hotkey: {sn_owner_hotkey}")

        # Get the UID of this hotkey
        sn_owner_uid = self.subtensor.get_uid_for_hotkey_on_subnet(
            hotkey_ss58=sn_owner_hotkey,
            netuid=self.config.netuid,
        )
        bt.logging.info(f"SN Owner UID: {sn_owner_uid}")

        return sn_owner_uid

    def get_registration_block(self, uid: int) -> typing.Optional[int]:
        """Get the block at which a UID was registered on the subnet.

        Args:
            uid: The unique identifier of the neuron.

        Returns:
            The block number when the UID was registered, or None if query fails.
        """
        try:
            result = self.subtensor.query_subtensor(
                "BlockAtRegistration",
                params=[self.config.netuid, uid]
            )
            if result is not None:
                # The result is a BittensorScaleType, extract the value
                registration_block = int(result.value) if hasattr(result, 'value') else int(result)
                return registration_block
            return None
        except Exception as e:
            bt.logging.warning(f"Failed to get registration block for UID {uid}: {e}")
            return None

    def should_set_weights(self) -> bool:
        current_block = self.subtensor.get_current_block()
        next_epoch_block = self.subtensor.get_next_epoch_start_block(self.config.netuid)
        blocks_to_epoch = next_epoch_block - current_block
        if self.last_submitted_epoch == next_epoch_block:
            return False

        threshold = self.config.block_threshold
        return blocks_to_epoch <= threshold

    async def try_sync_metagraph(self) -> bool:
        bt.logging.trace("Syncing metagraph")
        try:
            self.metagraph = self.subtensor.metagraph(self.config.netuid)
            self.metagraph.save()
            bt.logging.info("Synced metagraph")
            return True
        except Exception as e:
            bt.logging.error(f"Error syncing metagraph: {e}")
            return False

    def should_start_new_competition(self, main_commit_id: str) -> bool:

        if not self.active_competition_id:
            return True

        dataset_commit_id = self.score_db.get_competition_info(self.active_competition_id)
        if dataset_commit_id == main_commit_id:
            # The database wasn’t updated, reward as the same as previous day.
            return False
        return True

    def persist_state(self):
        try:
            self.score_db.set_state("active_competition_id", self.active_competition_id)
            self.score_db.set_state("reward_competition_id", self.reward_competition_id)
            self.score_db.set_state("use_yesterday_reward", self.use_yesterday_reward)
            self.score_db.set_state("weights", self.weights.tolist() if isinstance(self.weights, torch.Tensor) else self.weights)
        except Exception as e:
            bt.logging.error(f"Failed to persist validator state: {e}")

    def _comp_exists_in_db(self):
        now = datetime.now(timezone.utc)
        competition_id_today = now.strftime("%Y%m%d")
        competition_id_yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")

        stored_active = self.score_db.get_state("active_competition_id")
        stored_reward = self.score_db.get_state("reward_competition_id")
        stored_use_yesterday = self.score_db.get_state("use_yesterday_reward")
        stored_weights = self.score_db.get_state("weights")

        if stored_active and stored_active in (competition_id_today, competition_id_yesterday) and \
                self.score_db.get_competition_info(stored_active):
            self.active_competition_id = stored_active
            self.reward_competition_id = stored_reward
            self.use_yesterday_reward = stored_use_yesterday
            self.weights = torch.tensor(stored_weights, dtype=torch.float32)
        else:
            self.weights = torch.zeros_like(torch.tensor(self.metagraph.S))
            # Get the burn UID.
            burn_uid = self.get_burn_uid()
            self.weights[burn_uid] = 1
            bt.logging.info(f"Initial weight :{self.weights}")

    async def run_step(self):
        bt.logging.info("Starting run step")
        check_and_update_code()

        bt.logging.info("Attempting to sync metagraph")
        synced_metagraph = await self.try_sync_metagraph()
        if not synced_metagraph:
            bt.logging.warning("Failed to sync metagraph")
            return

        current_uids = self.metagraph.uids.tolist()
        hotkeys = self.metagraph.hotkeys
        coldkeys = self.metagraph.coldkeys
        self.consensus = self.metagraph.C
        bt.logging.debug(f"Consensus: {self.consensus}")

        now = datetime.now(timezone.utc)
        competition_id_today = now.strftime("%Y%m%d")
        minutes_today = now.hour * 60 + now.minute

        competition = Competition.from_defaults()
        eval_namespace = competition.repo
        main_commit_id = get_hg_revision(eval_namespace, constants.eval_commit)
        competitors = current_uids

        # set weight at the begining
        if self.should_set_weights():
            bt.logging.info(f"blocks to epoch less than threshold")
            bt.logging.info(f"Setting weights on chain for netuid {self.config.netuid}")
            uids_py = self.metagraph.uids.tolist()
            weights_py = self.weights.tolist()
            # Create a fresh salt for this commitment
            commit_salt = list(os.urandom(8))
            success, commit_msg, _ = set_weights_with_err_msg(
                subtensor=self.subtensor,
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=uids_py,
                weights=weights_py,
                wait_for_inclusion=True,
                ss58_address=self.wallet.hotkey.ss58_address,
                salt=commit_salt,
            )
            if success:
                # Persist pending reveal state using floats; helper will scale consistently
                self.pending_reveal = {
                    "uids": uids_py,
                    "weights": weights_py,
                    "salt": commit_salt,
                }
                bt.logging.info("Stored pending reveal state for next interval")
            else:
                bt.logging.warning(f"Commit did not succeed: {commit_msg}")
            next_epoch_block = self.subtensor.get_next_epoch_start_block(
                self.config.netuid
            )
            self.last_submitted_epoch = next_epoch_block
        else:
            bt.logging.info(
                f"Blocks to epoch is greater than threshold, not setting weights"
            )

        if self.pending_reveal is not None:
            try:
                bt.logging.info("Attempting to reveal previously committed weights")
                reveal_success, reveal_msg, _ = reveal_weights_with_err_msg(
                    subtensor=self.subtensor,
                    wallet=self.wallet,
                    netuid=self.config.netuid,
                    uids=self.pending_reveal["uids"],
                    weights=self.pending_reveal["weights"],
                    salt=self.pending_reveal["salt"],
                    wait_for_inclusion=True,
                )
                if reveal_success:
                    bt.logging.info(f"Reveal succeeded: {reveal_msg}")
                    self.pending_reveal = None
                else:
                    bt.logging.info(f"Reveal not successful yet: {reveal_msg}")
            except Exception as e:
                bt.logging.error(f"Reveal attempt failed: {e}")

        # SUBMISSION
        if constants.submission_start_utc_min <= minutes_today < constants.validate_start_utc_min:
            # record exists, the task is already created
            if self.score_db.get_competition_info(competition_id_today):
                if self.use_yesterday_reward:
                    time.sleep(10)
                    return
                else:
                    for uid in competitors:
                        metadata = retrieve_model_metadata(
                            self.subtensor, self.config.netuid, self.metagraph.hotkeys[uid]
                        )
                        if metadata is not None:
                            self.score_db.record_submission(self.active_competition_id,
                                                            uid, hotkeys[uid], coldkeys[uid], metadata.block,
                                                            int(time.time()), metadata.id.namespace,
                                                            metadata.id.commit)
                    return

            if self.should_start_new_competition(main_commit_id):
                bt.logging.info("STARTING NEW COMPETITION CYCLE")
                self.score_db.update_competition_status(self.active_competition_id, CompetitionState.COMPLETED.value)
                self.active_competition_id = competition_id_today
                self.use_yesterday_reward = False
                self.score_db.create_competition(self.active_competition_id, int(now.timestamp()), main_commit_id)
                self.persist_state()
            else:
                bt.logging.info("COPY COMPETITION REWARD BEFORE")
                bt.logging.info(f"weights set by reward_competition_id {self.reward_competition_id}")
                self.use_yesterday_reward = True
                self.score_db.copy_competition_id(competition_id_today, self.active_competition_id)
                self.score_db.update_competition_status(self.active_competition_id, CompetitionState.COMPLETED.value)
                self.active_competition_id = competition_id_today
                self.persist_state()

        # VALIDATION
        elif constants.validate_start_utc_min <= minutes_today < 24 * 60 or \
                minutes_today < constants.reward_start_utc_min:

            if self.use_yesterday_reward or self.active_competition_id == "":
                time.sleep(10)
                bt.logging.info(f"now the weight is {self.weights}")
                return

            if self.pending_reveal is not None:
                try:
                    bt.logging.info("Attempting to reveal previously committed weights")
                    reveal_success, reveal_msg, _ = reveal_weights_with_err_msg(
                        subtensor=self.subtensor,
                        wallet=self.wallet,
                        netuid=self.config.netuid,
                        uids=self.pending_reveal["uids"],
                        weights=self.pending_reveal["weights"],
                        salt=self.pending_reveal["salt"],
                        wait_for_inclusion=True,
                    )
                    if reveal_success:
                        bt.logging.info(f"Reveal succeeded: {reveal_msg}")
                        self.pending_reveal = None
                    else:
                        bt.logging.info(f"Reveal not successful yet: {reveal_msg}")
                except Exception as e:
                    bt.logging.error(f"Reveal attempt failed: {e}")

            # set status
            self.score_db.update_competition_status(self.active_competition_id, CompetitionState.VALIDATION.value)

            duplicate_sample_size = min(self.config.miner_duplicate_sample_size, len(competitors))
            sample_size = min(self.config.miner_sample_size, len(competitors))
            uids_to_check_duplicate = self.rng.choice(competitors, duplicate_sample_size, replace=False).tolist()
            uids_to_eval = self.rng.choice(uids_to_check_duplicate, sample_size, replace=False).tolist()
            lucky_num = int.from_bytes(os.urandom(4), "little")
            bt.logging.debug(f"UIDs to evaluate: {uids_to_eval}")

            raw_scores_this_epoch = {}
            block_per_uid = {}

            duplicate_groups = []
            processed_uids = set()
            bt.logging.info("Checking for duplicate scores using raw scores")
            eval_data_dir = self.config.eval_data_dir
            bt.logging.info(
                f"Downloading eval dataset: {eval_namespace}/{main_commit_id}"
            )
            download_dataset(
                eval_namespace,
                main_commit_id,
                local_dir=eval_data_dir,
                cache_dir=self.config.cache_dir,
            )
            os.makedirs(eval_data_dir, exist_ok=True)
            for fname in os.listdir(eval_data_dir):
                if fname.endswith(".jsonl"):
                    src = os.path.join(eval_data_dir, fname)
                    dst = os.path.join(eval_data_dir, "data.jsonl")
                    if src != dst:
                        os.replace(src, dst)
                        bt.logging.info(f"Renamed {fname} → data.jsonl")

            metadata_competition_all = self.score_db.get_competition_submissions(self.active_competition_id)
            for uid_i in uids_to_check_duplicate:

                if uid_i not in metadata_competition_all:
                    bt.logging.debug(
                        f"UID {uid_i} has no metadata, assigning default score"
                    )
                    raw_scores_this_epoch[uid_i] = constants.DEFAULT_RAW_SCORE
                    self.score_db.record_submission_loss(self.active_competition_id, uid_i, constants.DEFAULT_RAW_SCORE, is_eligible=False)
                    continue

                block_per_uid[uid_i] = metadata_competition_all[uid_i]["commitment_block"]
                metadata_i_namespace = metadata_competition_all[uid_i]["namespace"]
                metadata_i_commit = metadata_competition_all[uid_i]["revision"]

                bt.logging.info(
                    f"Downloading {uid_i}:{self.metagraph.hotkeys[uid_i]} training dataset: {metadata_i_namespace}/{metadata_i_commit}, block:{block_per_uid[uid_i]}"
                )
                miner_i_data_dir = os.path.join(self.config.data_dir, f"miner_{uid_i}")

                download_dataset(
                    metadata_i_namespace,
                    metadata_i_commit,
                    local_dir=miner_i_data_dir,
                    cache_dir=self.config.cache_dir,
                    force=random.random() < 0.2
                )
                os.makedirs(miner_i_data_dir, exist_ok=True)

            for uid_i in uids_to_check_duplicate:
                if uid_i in processed_uids:
                    bt.logging.debug(
                        f"Skipping UID {uid_i}  (None, zero, or already processed)"
                    )
                    continue

                miner_i_data_dir = os.path.join(self.config.data_dir, f"miner_{uid_i}")

                try:
                    # Load full eval dataset for validation check
                    eval_data_jsonl = load_jsonl(os.path.join(eval_data_dir, "data.jsonl"))
                    miner_i_data_jsonl = load_jsonl(os.path.join(miner_i_data_dir, "data.jsonl"), max_rows=competition.rows)
                except FileNotFoundError as e:
                    bt.logging.warning(f"Data file not found for UID {uid_i}: {e}")
                    bt.logging.info(f"Assigning fallback score to UID {uid_i} due to missing data file")
                    raw_scores_this_epoch[uid_i] = constants.DEFAULT_RAW_SCORE
                    self.score_db.record_submission_loss(self.active_competition_id, uid_i, constants.DEFAULT_RAW_SCORE, is_eligible=False)
                    continue
                except Exception as e:
                    bt.logging.error(f"Error loading data files for UID {uid_i}: {e}")
                    bt.logging.info(f"Assigning fallback score to UID {uid_i} due to data loading error")
                    raw_scores_this_epoch[uid_i] = constants.DEFAULT_RAW_SCORE
                    self.score_db.record_submission_loss(self.active_competition_id, uid_i, constants.DEFAULT_RAW_SCORE, is_eligible=False)
                    continue

                if count_similar(eval_data_jsonl, miner_i_data_jsonl) != len(miner_i_data_jsonl):
                    raw_scores_this_epoch[uid_i] = constants.DEFAULT_RAW_SCORE
                    self.score_db.record_submission_loss(self.active_competition_id, uid_i, constants.DEFAULT_RAW_SCORE, is_eligible=False)
                    bt.logging.info(
                        f"Assigned fallback score {constants.DEFAULT_RAW_SCORE:.6f} to UID {uid_i} due to the "
                        f"miner dataset is not entirely from the evaluation dataset"
                    )
                    continue

                for uid_j in uids_to_eval:
                    if (
                            uid_i != uid_j
                            and uid_j not in processed_uids
                    ):
                        similar_uids = [uid_i]
                        miner_j_data_dir = os.path.join(self.config.data_dir, f"miner_{uid_j}")

                        if uid_j not in metadata_competition_all:
                            bt.logging.debug(
                                f"Skipping UID {uid_j}  (metadata is None)"
                            )
                            continue
                        try:
                            metadata_j_namespace = metadata_competition_all[uid_j]["namespace"]
                            metadata_j_commit = metadata_competition_all[uid_j]["revision"]
                            os.makedirs(miner_j_data_dir, exist_ok=True)
                            download_dataset(
                                metadata_j_namespace,
                                metadata_j_commit,
                                local_dir=miner_j_data_dir,
                                cache_dir=self.config.cache_dir,
                            )

                            miner_j_data_jsonl = load_jsonl(os.path.join(miner_j_data_dir, "data.jsonl"), max_rows=competition.rows)
                        except FileNotFoundError as e:
                            bt.logging.warning(f"Data file not found for UID {uid_j} during duplicate check: {e}")
                            continue
                        except Exception as e:
                            bt.logging.error(f"Error loading data file for UID {uid_j} during duplicate check: {e}")
                            continue

                        if count_similar(miner_j_data_jsonl, miner_i_data_jsonl) > constants.DEFAULT_DUPLICATE_COUNT:
                            bt.logging.debug(
                                f"Found similar raw score: {uid_i} and {uid_j}"
                            )
                            similar_uids.append(uid_j)

                        if len(similar_uids) > 1:
                            bt.logging.info(f"Found duplicate group: {similar_uids}")
                            duplicate_groups.append(similar_uids)
                            processed_uids.update(similar_uids)

            duplicates = set()
            for group in duplicate_groups:
                bt.logging.info(f"Processing duplicate group: {group}")
                group.sort(key=lambda uid: block_per_uid[uid])
                bt.logging.info(f"Sorted by block: {group}")

                for uid in group[1:]:
                    duplicates.add(uid)
                    raw_scores_this_epoch[uid] = constants.DEFAULT_RAW_SCORE
                    self.score_db.record_submission_loss(self.active_competition_id, uid, constants.DEFAULT_RAW_SCORE, is_eligible=False)

            for uid in uids_to_eval:

                current_raw_score = raw_scores_this_epoch.get(uid)
                if current_raw_score is not None and current_raw_score == constants.DEFAULT_RAW_SCORE:
                    bt.logging.info(f"The dataset for UID {uid} is invalid.")
                    continue
                bt.logging.info(f"Evaluating UID: {uid}")
                bt.logging.info(
                    f"Retrieving model metadata for hotkey: {self.metagraph.hotkeys[uid]}"
                )

                if self.should_set_weights():
                    bt.logging.info(
                        f"approaching weight setting time for netuid {self.config.netuid}, breaking from eval loop"
                    )
                    break

                if uid in metadata_competition_all:
                    ns = metadata_competition_all[uid]["namespace"]
                    revision = metadata_competition_all[uid]["revision"]
                    bt.logging.info(f"Metadata namespace: {ns}, commit: {revision}")

                    if not check_valid_revision(namespace=ns, revision=revision):
                        raw_scores_this_epoch[uid] = constants.DEFAULT_RAW_SCORE
                        self.score_db.record_submission_loss(self.active_competition_id, uid, constants.DEFAULT_RAW_SCORE, is_eligible=False)
                        bt.logging.info(
                            f"Assigned fallback score {constants.DEFAULT_RAW_SCORE:.6f} to UID {uid} due to the dataset hash is invalid"
                        )
                        continue
                    if metadata_competition_all[uid]["eval_loss"] is not None:
                        bt.logging.info(
                            f"Skipping UID {uid} as it has already been evaluated with revision {revision}"
                        )
                        raw_scores_this_epoch[uid] = metadata_competition_all[uid]["eval_loss"]
                        continue
                    try:
                        miner_data_dir = os.path.join(self.config.data_dir, f"miner_{uid}")
                        eval_data_dir = self.config.eval_data_dir

                        bt.logging.info(f"Using data directory: {miner_data_dir}")
                        bt.logging.info(f"Using evaluation directory: {eval_data_dir}")

                        for fname in os.listdir(eval_data_dir):
                            if fname.endswith(".jsonl"):
                                src = os.path.join(eval_data_dir, fname)
                                dst = os.path.join(eval_data_dir, "data.jsonl")
                                if src != dst:
                                    os.replace(src, dst)
                                    bt.logging.info(f"Renamed {fname} → data.jsonl")

                        bt.logging.info("Starting LoRA training")
                        eval_loss = train_lora(
                            lucky_num,
                            competition.bench,
                            competition.rows,
                            cache_dir=self.config.cache_dir,
                            data_dir=miner_data_dir,
                            eval_data_dir=eval_data_dir,
                        )
                        bt.logging.info(f"Training complete with eval loss: {eval_loss}")

                        raw_scores_this_epoch[uid] = eval_loss
                        self.score_db.record_submission_loss(self.active_competition_id, uid, eval_loss, is_eligible=True)

                        bt.logging.info(f"Stored evaluation results for UID {uid}")

                    except Exception as e:
                        bt.logging.error(f"train error: {e}")
                        if "CUDA" in str(e):
                            bt.logging.error("CUDA error detected, terminating process")
                            os._exit(1)
                        raw_scores_this_epoch[uid] = constants.DEFAULT_RAW_SCORE
                        self.score_db.record_submission_loss(self.active_competition_id, uid, constants.DEFAULT_RAW_SCORE, is_eligible=False)
                        bt.logging.info(
                            f"Assigned fallback score {constants.DEFAULT_RAW_SCORE:.6f} to UID {uid} due to train error"
                        )
                else:
                    bt.logging.warning(f"No metadata found for UID {uid}")
                    raw_scores_this_epoch[uid] = constants.DEFAULT_RAW_SCORE
                    self.score_db.record_submission_loss(self.active_competition_id, uid, constants.DEFAULT_RAW_SCORE, is_eligible=False)

        # REWARDING
        elif constants.reward_start_utc_min <= minutes_today < constants.submission_start_utc_min:

            if self.use_yesterday_reward or self.active_competition_id == "":
                time.sleep(10)
                bt.logging.info(f"now the weight is {self.weights}")
                return
                # set status
            if self.score_db.get_competition_status(self.active_competition_id) == CompetitionState.REWARDING.value:
                time.sleep(10)
                return
            winner, winner_loss = select_winner(self.score_db, self.active_competition_id, self.metagraph.hotkeys, self.metagraph.coldkeys)
            bt.logging.info(f"Competition_id {self.active_competition_id} winners is {winner} ")
            if winner:
                new_weights = torch.zeros_like(torch.tensor(self.metagraph.S), dtype=torch.float32)

                if winner < len(new_weights):
                    new_weights[winner] = 1
                else:
                    bt.logging.warning(f"UID {winner} out of bounds for new_weights tensor, skipping.")
                self.weights = new_weights
                self.reward_competition_id = self.active_competition_id
                self.score_db.update_competition_status(self.active_competition_id, CompetitionState.REWARDING.value)
                self.score_db.update_competition_score(self.active_competition_id, winner, winner_loss)
                bt.logging.info(f"weights set by reward_competition_id {self.reward_competition_id}")
                self.persist_state()

            else:
                bt.logging.error(f"There is no score for Competition_id {self.active_competition_id}")
                raise RuntimeError(f"No winners for competition_id {self.active_competition_id}")

        else:
            bt.logging.error(f"The minutes time is error: {minutes_today}")
            raise RuntimeError(f"No winners for competition_id {self.active_competition_id}")


    async def run(self):
        while True:
            await self.run_step()


if __name__ == "__main__":
    asyncio.run(Validator().run())
