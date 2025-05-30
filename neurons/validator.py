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
import torch
import typing
import bittensor as bt
import math
import numpy as np
import json
import hashlib
from dataclasses import asdict

from flockoff import constants
from flockoff.utils.chain import assert_registered, read_chain_commitment
from flockoff.utils.git import check_latest_code
from flockoff.validator.chain import (
    retrieve_model_metadata,
    set_weights_with_err_msg,
)
from flockoff.validator.validator_utils import compute_score
from flockoff.validator.trainer import (
    train_lora,
    download_dataset,
)
from flockoff.validator.database import ScoreDB


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
        check_latest_code()

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
        self.weights = torch.zeros_like(torch.tensor(self.metagraph.S))
        bt.logging.info(f"Weights initialized with shape: {self.weights.shape}")

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

        bt.logging.info("Validator ready to run")

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

    async def run_step(self):
        bt.logging.info("Starting run step")
        bt.logging.info("Attempting to sync metagraph")

        synced_metagraph = await self.try_sync_metagraph()
        if not synced_metagraph:
            bt.logging.warning("Failed to sync metagraph")
            return

        bt.logging.info("Getting current UIDs and hotkeys")
        current_uids = self.metagraph.uids.tolist()
        hotkeys = self.metagraph.hotkeys
        bt.logging.info(f"Current UIDs: {current_uids}")

        # Explicitly setting initial scores for new/reset UIDs.
        # base_raw_score is set to constants.DEFAULT_SCORE (0.0), representing no prior evaluation.
        base_raw_score = constants.DEFAULT_SCORE 
        # initial_normalized_score is set to a small non-zero value (1.0 / 255.0) 
        # to serve as a minimal starting weight for new miners.
        initial_normalized_score = 1.0 / 255.0 
        for uid in current_uids:
            self.score_db.insert_or_reset_uid(uid, hotkeys[uid], base_raw_score, initial_normalized_score)

        bt.logging.info("Getting normalized scores from database for initial weights")
        db_normalized_scores = self.score_db.get_all_normalized_scores(current_uids)

        bt.logging.info("Setting weights tensor from database normalized scores")
        self.weights = torch.tensor(db_normalized_scores, dtype=torch.float32)
        bt.logging.debug(f"Weights tensor initialized: {self.weights}")

        self.consensus = self.metagraph.C
        bt.logging.debug(f"Consensus: {self.consensus}")

        is_testnet = self.config.subtensor.network == "test"
        bt.logging.info(f"Network: {self.config.subtensor.network}")
        bt.logging.info(f"Is testnet: {is_testnet}")
        bt.logging.info("Reading chain commitment")
        subnet_owner = constants.get_subnet_owner(is_testnet)

        competition = read_chain_commitment(
            subnet_owner, self.subtensor, self.config.netuid
        )
        if competition is None:
            bt.logging.error("Failed to read competition commitment")
            return

        comp_dict = asdict(competition)
        comp_hash = hashlib.sha256(
            json.dumps(comp_dict, sort_keys=True).encode()
        ).hexdigest()
        competition_changed = False
        if comp_hash != self.last_competition_hash:
            bt.logging.info(f"Competition hash changed: {comp_hash}")
            self.last_competition_hash = comp_hash
            competition_changed = True

        eval_namespace = competition.repo

        bt.logging.info(f"Competition commitment: {competition}")

        bt.logging.info("Sampling competitors for evaluation")
        competitors = current_uids
        sample_size = min(self.config.miner_sample_size, len(competitors))
        uids_to_eval = self.rng.choice(competitors, sample_size, replace=False).tolist()
        lucky_num = int.from_bytes(os.urandom(4), "little")
        bt.logging.debug(f"UIDs to evaluate: {uids_to_eval}")

        raw_scores_this_epoch = {}
        block_per_uid = {}
        for uid in uids_to_eval:
            bt.logging.info(f"Evaluating UID: {uid}")
            bt.logging.info(
                f"Retrieving model metadata for hotkey: {self.metagraph.hotkeys[uid]}"
            )
            metadata = retrieve_model_metadata(
                self.subtensor, self.config.netuid, self.metagraph.hotkeys[uid]
            )

            if self.should_set_weights():
                bt.logging.info(
                    f"approaching weight setting time for netuid {self.config.netuid}, breaking from eval loop"
                )
                break

            if metadata is not None:
                bt.logging.info(f"Retrieved metadata: {metadata}")
                ns = metadata.id.namespace
                revision = metadata.id.commit
                last_rev = self.score_db.get_revision(ns)
                bt.logging.info(f"Metadata namespace: {ns}, commit: {revision}")
                if not competition_changed and last_rev == revision:
                    bt.logging.info(
                        f"Skipping UID {uid} as it has already been evaluated with revision {revision}"
                    )
                    retrieved_raw_score = self.score_db.get_raw_eval_score(uid)
                    raw_scores_this_epoch[uid] = retrieved_raw_score if retrieved_raw_score is not None else constants.DEFAULT_SCORE
                    block_per_uid[uid] = metadata.block
                    continue
                try:
                    miner_data_dir = os.path.join(self.config.data_dir, f"miner_{uid}")
                    eval_data_dir = self.config.eval_data_dir

                    bt.logging.info(f"Using data directory: {miner_data_dir}")
                    bt.logging.info(f"Using evaluation directory: {eval_data_dir}")

                    os.makedirs(miner_data_dir, exist_ok=True)
                    os.makedirs(eval_data_dir, exist_ok=True)

                    bt.logging.info(
                        f"Downloading training dataset: {metadata.id.namespace}/{metadata.id.commit}"
                    )

                    download_dataset(
                        metadata.id.namespace,
                        metadata.id.commit,
                        local_dir=miner_data_dir,
                        cache_dir=self.config.cache_dir,
                    )

                    bt.logging.info(
                        f"Downloading eval dataset: {eval_namespace}/{constants.eval_commit}"
                    )

                    download_dataset(
                        eval_namespace,
                        constants.eval_commit,
                        local_dir=eval_data_dir,
                        cache_dir=self.config.cache_dir,
                    )

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
                    block_per_uid[uid] = metadata.block
                    self.score_db.update_raw_eval_score(uid, eval_loss)
                    self.score_db.set_revision(ns, revision)

                    bt.logging.info(f"Stored evaluation results for UID {uid}")

                except Exception as e:
                    bt.logging.error(f"train error: {e}")
                    if "CUDA" in str(e):
                        bt.logging.error("CUDA error detected, terminating process")
                        os._exit(1)
                    raw_scores_this_epoch[uid] = constants.DEFAULT_SCORE
                    block_per_uid[uid] = metadata.block
                    self.score_db.update_raw_eval_score(uid, constants.DEFAULT_SCORE)
                    bt.logging.info(
                        f"Assigned fallback score {constants.DEFAULT_SCORE:.6f} to UID {uid} due to train error"
                    )
            else:
                bt.logging.warning(f"No metadata found for UID {uid}")
                raw_scores_this_epoch[uid] = 0
                self.score_db.update_raw_eval_score(uid, 0)

        duplicate_groups = []
        processed_uids = set()

        bt.logging.info("Checking for duplicate scores using raw scores")
        for uid_i, score_i in raw_scores_this_epoch.items():
            if (
                score_i is None
                or score_i == 0
                or score_i == constants.DEFAULT_SCORE
                or uid_i in processed_uids
            ):
                bt.logging.debug(
                    f"Skipping UID {uid_i} with score {score_i} (None, zero, or already processed)"
                )
                continue

            similar_uids = [uid_i]
            for uid_j, score_j in raw_scores_this_epoch.items():
                if (
                    uid_i != uid_j
                    and score_j not in (None, 0, constants.DEFAULT_SCORE)
                    and uid_j not in processed_uids
                ):
                    if math.isclose(score_i, score_j, rel_tol=1e-5):
                        bt.logging.debug(
                            f"Found similar raw score: {uid_i}({score_i}) and {uid_j}({score_j})"
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
                raw_scores_this_epoch[uid] = constants.DEFAULT_SCORE
                self.score_db.update_raw_eval_score(uid, constants.DEFAULT_SCORE)

        bt.logging.info("Normalizing raw scores")
        normalized_scores_this_epoch = {}
        for uid in uids_to_eval:
            current_raw_score = raw_scores_this_epoch.get(uid)
            if current_raw_score is not None:
                bt.logging.debug(
                    f"Computing normalized score for UID {uid} with raw score {current_raw_score}"
                )
                if competition.bench is None or competition.bench <= 0:
                    bt.logging.warning(
                        f"Invalid benchmark ({competition.bench}) for UID {uid}; defaulting score to 0"
                    )
                    normalized_score = constants.DEFAULT_SCORE
                else:
                    normalized_score = compute_score(
                        current_raw_score,
                        competition.bench,
                        competition.minb,
                        competition.maxb,
                        competition.pow,
                        competition.bheight,
                        metadata.id.competition_id,
                        competition.id,
                    )
                normalized_scores_this_epoch[uid] = normalized_score
            else:
                bt.logging.debug(f"Setting zero normalized score for UID {uid} as raw score was missing")
                normalized_scores_this_epoch[uid] = 0
        bt.logging.debug(f"Normalized scores for this epoch: {normalized_scores_this_epoch}")

        bt.logging.info("Creating new weights tensor based on this epoch's normalized scores")
        new_weights = self.weights.clone()
        for uid, norm_score in normalized_scores_this_epoch.items():
            if uid < len(new_weights):
                new_weights[uid] = norm_score
            else:
                bt.logging.warning(f"UID {uid} out of bounds for new_weights tensor, skipping.")

        new_weights = torch.where(
            new_weights < constants.MIN_WEIGHT_THRESHOLD,
            torch.zeros_like(new_weights),
            new_weights,
        )
        bt.logging.debug(
            f"Thresholded new_weights (min {constants.MIN_WEIGHT_THRESHOLD}): {new_weights}"
        )

        bt.logging.info("Updating database with final normalized scores (weights)")
        for uid in uids_to_eval:
            if uid < len(new_weights):
                final_normalized_weight = new_weights[uid].item()
                self.score_db.update_final_normalized_score(uid, final_normalized_weight)

        self.weights = new_weights
        bt.logging.debug(f"Updated self.weights: {self.weights}")
        bt.logging.debug(f"Consensus: {self.consensus}")

        bt.logging.info("Setting weights on chain")
        uids_py = self.metagraph.uids.tolist()
        weights_py = new_weights.tolist()

        if self.should_set_weights():
            bt.logging.info(f"blocks to epoch less than threshold")
            bt.logging.info(f"Setting weights on chain for netuid {self.config.netuid}")
            set_weights_with_err_msg(
                subtensor=self.subtensor,
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=uids_py,
                weights=weights_py,
                wait_for_inclusion=True,
            )
            next_epoch_block = self.subtensor.get_next_epoch_start_block(
                self.config.netuid
            )
            self.last_submitted_epoch = next_epoch_block
        else:
            bt.logging.info(
                f"Blocks to epoch is greater than threshold, not setting weights"
            )

    async def run(self):
        while True:
            await self.run_step()


if __name__ == "__main__":
    asyncio.run(Validator().run())