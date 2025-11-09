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
import logging
import threading
import time
import torch
import typing
import random
import atexit
import sys

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]
import bittensor as bt
import numpy as np
import json
import hashlib
from dataclasses import asdict
from typing import Dict, List, Tuple


class LokiBatchHandler(logging.Handler):
    """Batch log records and push them to Grafana Cloud Loki."""

    def __init__(
        self,
        *,
        url: str,
        username: str,
        password: str,
        labels: Dict[str, str],
        flush_interval: float,
        max_buffer: int = 5000,
        request_timeout: float = 10.0,
    ) -> None:
        super().__init__()
        if requests is None:
            raise RuntimeError("requests library is required for Loki logging.")
        self.url = url
        self.auth = (username, password)
        self.labels = labels
        self.flush_interval = max(1.0, float(flush_interval))
        self.max_buffer = max_buffer
        self.request_timeout = request_timeout
        self._buffer: List[Tuple[int, str]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_event = threading.Event()
        self._session = requests.Session()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, name="GrafanaLokiFlush", daemon=True
        )
        self._flush_thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()

        timestamp_ns = int(record.created * 1_000_000_000)
        should_flush_immediately = False

        with self._lock:
            self._buffer.append((timestamp_ns, message))
            if len(self._buffer) >= self.max_buffer:
                should_flush_immediately = True

        if should_flush_immediately:
            self._flush()
        else:
            self._flush_event.set()

    def _flush_loop(self) -> None:
        while not self._stop_event.is_set():
            triggered = self._flush_event.wait(self.flush_interval)
            self._flush_event.clear()
            if triggered or not self._stop_event.is_set():
                self._flush()

        # Final flush on exit
        self._flush()

    def _flush(self) -> None:
        batch: List[Tuple[int, str]] = []
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []

        payload = {
            "streams": [
                {
                    "stream": self.labels,
                    "values": [[str(ts), line] for ts, line in batch],
                }
            ]
        }

        try:
            response = self._session.post(
                self.url,
                json=payload,
                auth=self.auth,
                timeout=self.request_timeout,
            )
            if response.status_code >= 400:
                self._handle_flush_failure(batch, f"HTTP {response.status_code}: {response.text.strip()}")
        except Exception as err:  # pylint: disable=broad-except
            self._handle_flush_failure(batch, repr(err))

    def _handle_flush_failure(self, batch: List[Tuple[int, str]], reason: str) -> None:
        # Requeue the failed batch (newest logs kept if exceeding max_buffer)
        with self._lock:
            batch.extend(self._buffer)
            self._buffer = batch[-self.max_buffer :]
        try:
            sys.stderr.write(f"[GrafanaLokiHandler] Failed to push logs: {reason}\n")
        except Exception:
            # If stderr write fails, ignore to avoid recursive logging.
            pass

    def close(self) -> None:
        self._stop_event.set()
        self._flush_event.set()
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=self.flush_interval + 1.0)
        self._flush()
        try:
            self._session.close()
        finally:
            super().close()


_LOKI_HANDLER: typing.Optional[LokiBatchHandler] = None
_LOKI_HANDLER_LOCK = threading.Lock()


def setup_loki_logging_from_env() -> typing.Optional[LokiBatchHandler]:
    """Configure Loki logging handler once per process based on environment variables."""
    global _LOKI_HANDLER

    with _LOKI_HANDLER_LOCK:
        if _LOKI_HANDLER is not None:
            return _LOKI_HANDLER

        if requests is None:
            try:
                sys.stderr.write(
                    "[GrafanaLokiHandler] requests library not available; skipping Loki setup.\n"
                )
            except Exception:
                pass
            return None

        loki_url = os.getenv("GRAFANA_LOKI_URL")
        loki_username = os.getenv("GRAFANA_LOKI_USERNAME")
        loki_password = os.getenv("GRAFANA_LOKI_PASSWORD")
        validator_hotkey = os.getenv("VALIDATOR_HOTKEY")
        subnet = os.getenv("SUBNET")

        if not all([loki_url, loki_username, loki_password, validator_hotkey]):
            return None

        try:
            flush_interval = float(os.getenv("LOKI_FLUSH_INTERVAL_SECS", "300"))
        except ValueError:
            flush_interval = 300.0

        labels: Dict[str, str] = {
            "app": "validator",
            "validator_hotkey": validator_hotkey,
        }
        if subnet:
            labels["subnet"] = subnet

        handler = LokiBatchHandler(
            url=loki_url,
            username=loki_username,
            password=loki_password,
            labels=labels,
            flush_interval=flush_interval,
        )
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        _LOKI_HANDLER = handler
        atexit.register(handler.close)
        return handler
from flockoff.constants import Competition
from flockoff import constants
from flockoff.utils.chain import assert_registered
from flockoff.utils.git import check_and_update_code
from flockoff.validator.chain import (
    retrieve_model_metadata,
    set_weights_with_err_msg,
    reveal_weights_with_err_msg,
)
from flockoff.validator.validator_utils import compute_score, load_jsonl, count_similar
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

        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)
        bt.axon.add_args(parser)
        config = bt.config(parser)
        bt.logging.debug(f"Parsed config: {config}")
        return config

    def __init__(self):
        self._loki_handler = setup_loki_logging_from_env()
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
        self.pending_reveal: typing.Optional[dict] = None
        self._update_score_init()
        bt.logging.info("Validator ready to run")

    def _update_score_init(self):
        bt.logging.info("start to update score init")
        current_uids = self.metagraph.uids.tolist()
        competition = Competition.from_defaults()
        db_normalized_scores = self.score_db.get_all_normalized_scores(current_uids)
        weights = torch.tensor(db_normalized_scores, dtype=torch.float32)

        for uid in current_uids:
            retrieved_raw_score = self.score_db.get_raw_eval_score(uid)
            if retrieved_raw_score is not None:
                normalized_score = compute_score(
                    retrieved_raw_score,
                    competition.bench,
                    competition.minb,
                    competition.maxb,
                    competition.pow,
                    competition.bheight,
                    competition.id,
                    competition.id,
                )
                if uid < len(weights):
                    weights[uid] = normalized_score
                else:
                    bt.logging.warning(f"UID {uid} out of bounds for new_weights tensor, skipping.")

        weights = torch.where(
            weights < constants.MIN_WEIGHT_THRESHOLD,
            torch.zeros_like(weights),
            weights,
        )
        for uid in current_uids:
            if uid < len(weights):
                final_normalized_weight = weights[uid].item()
                self.score_db.update_final_normalized_score(uid, final_normalized_weight)

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
        check_and_update_code()

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
        # base_raw_score is set to constants.DEFAULT_RAW_SCORE (999), representing no prior evaluation.
        base_raw_score = constants.DEFAULT_RAW_SCORE
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

        competition = Competition.from_defaults()

        eval_namespace = competition.repo

        bt.logging.info(f"Competition commitment: {competition}")

        bt.logging.info("Sampling competitors for evaluation")
        competitors = current_uids
        duplicate_sample_size = min(self.config.miner_duplicate_sample_size, len(competitors))
        sample_size = min(self.config.miner_sample_size, len(competitors))
        uids_to_check_duplicate = self.rng.choice(competitors, duplicate_sample_size, replace=False).tolist()
        uids_to_eval = self.rng.choice(uids_to_check_duplicate, sample_size, replace=False).tolist()
        lucky_num = int.from_bytes(os.urandom(4), "little")
        bt.logging.debug(f"UIDs to evaluate: {uids_to_eval}")

        raw_scores_this_epoch = {}
        block_per_uid = {}
        metadata_per_uid = {}  # Track metadata for each UID

        duplicate_groups = []
        processed_uids = set()
        bt.logging.info("Checking for duplicate scores using raw scores")
        eval_data_dir = self.config.eval_data_dir
        bt.logging.info(
            f"Downloading eval dataset: {eval_namespace}/{constants.eval_commit}"
        )
        download_dataset(
            eval_namespace,
            constants.eval_commit,
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

        for uid_i in uids_to_check_duplicate:
            metadata_i = retrieve_model_metadata(
                self.subtensor, self.config.netuid, self.metagraph.hotkeys[uid_i]
            )

            if metadata_i is None:
                bt.logging.debug(
                    f"Skipping UID {uid_i}  (metadata is None)"
                )
                continue
            metadata_per_uid[uid_i] = metadata_i  # Store metadata for this UID
            block_per_uid[uid_i] = metadata_i.block

            bt.logging.info(
                f"Downloading training dataset: {metadata_i.id.namespace}/{metadata_i.id.commit}"
            )
            miner_i_data_dir = os.path.join(self.config.data_dir, f"miner_{uid_i}")
            download_dataset(
                metadata_i.id.namespace,
                metadata_i.id.commit,
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
                self.score_db.update_raw_eval_score(uid_i, constants.DEFAULT_RAW_SCORE)
                continue
            except Exception as e:
                bt.logging.error(f"Error loading data files for UID {uid_i}: {e}")
                bt.logging.info(f"Assigning fallback score to UID {uid_i} due to data loading error")
                raw_scores_this_epoch[uid_i] = constants.DEFAULT_RAW_SCORE
                self.score_db.update_raw_eval_score(uid_i, constants.DEFAULT_RAW_SCORE)
                continue

            if count_similar(eval_data_jsonl, miner_i_data_jsonl) != len(miner_i_data_jsonl):
                raw_scores_this_epoch[uid_i] = constants.DEFAULT_RAW_SCORE
                self.score_db.update_raw_eval_score(uid_i, constants.DEFAULT_RAW_SCORE)
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
                    metadata_j = retrieve_model_metadata(
                        self.subtensor, self.config.netuid, self.metagraph.hotkeys[uid_j]
                    )
                    if metadata_j is None:
                        bt.logging.debug(
                            f"Skipping UID {uid_j}  (metadata is None)"
                        )
                        continue
                    try:
                        os.makedirs(miner_j_data_dir, exist_ok=True)
                        bt.logging.info(
                            f"Downloading training dataset: {metadata_j.id.namespace}/{metadata_j.id.commit}"
                        )
                        download_dataset(
                            metadata_j.id.namespace,
                            metadata_j.id.commit,
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
                self.score_db.update_raw_eval_score(uid, constants.DEFAULT_RAW_SCORE)

        for uid in uids_to_eval:
            # Try to reveal previously committed weights if any
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
                        bt.logging.success(f"Reveal succeeded: {reveal_msg}")
                        self.pending_reveal = None
                    else:
                        bt.logging.info(f"Reveal not successful yet: {reveal_msg}")
                except Exception as e:
                    bt.logging.error(f"Reveal attempt failed: {e}")

            current_raw_score = raw_scores_this_epoch.get(uid)
            if current_raw_score is not None and current_raw_score == constants.DEFAULT_RAW_SCORE:
                bt.logging.info(f"The dataset for UID {uid} is invalid.")
                continue
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
                last_rev = self.score_db.get_score_revision(uid, ns)
                bt.logging.info(f"Metadata namespace: {ns}, commit: {revision}")
                if last_rev == revision:
                    bt.logging.info(
                        f"Skipping UID {uid} as it has already been evaluated with revision {revision}"
                    )
                    retrieved_raw_score = self.score_db.get_raw_eval_score(uid)
                    raw_scores_this_epoch[uid] = retrieved_raw_score if retrieved_raw_score is not None else constants.DEFAULT_RAW_SCORE
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
                    self.score_db.update_raw_eval_score(uid, eval_loss)
                    self.score_db.set_score_revision(uid, ns, revision, self.metagraph.hotkeys[uid])

                    bt.logging.info(f"Stored evaluation results for UID {uid}")

                except Exception as e:
                    bt.logging.error(f"train error: {e}")
                    if "CUDA" in str(e):
                        bt.logging.error("CUDA error detected, terminating process")
                        os._exit(1)
                    raw_scores_this_epoch[uid] = constants.DEFAULT_RAW_SCORE
                    self.score_db.update_raw_eval_score(uid, constants.DEFAULT_RAW_SCORE)
                    bt.logging.info(
                        f"Assigned fallback score {constants.DEFAULT_RAW_SCORE:.6f} to UID {uid} due to train error"
                    )
            else:
                bt.logging.warning(f"No metadata found for UID {uid}")
                raw_scores_this_epoch[uid] = constants.DEFAULT_RAW_SCORE
                self.score_db.update_raw_eval_score(uid, constants.DEFAULT_RAW_SCORE)

        bt.logging.info("Normalizing raw scores")
        normalized_scores_this_epoch = {}
        for uid in uids_to_check_duplicate:
            current_raw_score = raw_scores_this_epoch.get(uid)
            if current_raw_score is not None:
                bt.logging.debug(
                    f"Computing normalized score for UID {uid} with raw score {current_raw_score}"
                )
                if competition.bench is None or competition.bench <= 0:
                    bt.logging.warning(
                        f"Invalid benchmark ({competition.bench}) for UID {uid}; defaulting score to 0"
                    )
                    normalized_score = constants.DEFAULT_NORMALIZED_SCORE
                else:
                    # Get the metadata for this specific UID
                    uid_metadata = metadata_per_uid.get(uid)
                    if uid_metadata is not None and uid_metadata.id is not None:
                        competition_id = uid_metadata.id.competition_id
                    else:
                        bt.logging.warning(f"No metadata found for UID {uid} during normalization, using None for competition_id")
                        competition_id = None
                    
                    normalized_score = compute_score(
                        current_raw_score,
                        competition.bench,
                        competition.minb,
                        competition.maxb,
                        competition.pow,
                        competition.bheight,
                        competition_id,
                        competition.id,
                    )
                normalized_scores_this_epoch[uid] = normalized_score
            else:
                # It's possibly due to the should_set_weights function causing data loss
                bt.logging.debug(f"Save the original score for UID {uid} as raw score was missing")
                # normalized_scores_this_epoch[uid] = self.weights[uid]
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

    async def run(self):
        while True:
            await self.run_step()


if __name__ == "__main__":
    asyncio.run(Validator().run())