# The MIT License (MIT)

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import argparse
import math
import asyncio
import torch
import typing
import multiprocessing
import bittensor as bt
from FLockDataset import constants
from FLockDataset.utils.chain import assert_registered
from FLockDataset.validator.chain import retrieve_model_metadata, set_weights_with_err_msg
from FLockDataset.validator.validator_utils import EvalQueue, compute_wins, adjust_for_vtrust
from FLockDataset.validator.trainer import train_lora, download_dataset, clean_cache_folder


class Validator:
    @staticmethod
    def config():
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--blocks_per_epoch",
            type=int,
            default=100,
            help="Number of blocks to wait before setting weights.",
        )
        parser.add_argument(
            "--miner_sample_size",
            type=int,
            default=3, 
            help="Number of miners to sample for each block.",
        )
        parser.add_argument(
            "--netuid", type=str, help="The subnet UID."
        )

        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)
        bt.axon.add_args(parser)
        config = bt.config(parser)
        return config

    def __init__(self):
        self.config = Validator.config()
        bt.logging(config=self.config)
        bt.logging.on()

        bt.logging.info(f"Starting validator with config: {self.config}")

        # === Bittensor objects ====
        self.wallet = bt.wallet(config=self.config)
        self.subtensor = bt.subtensor(config=self.config)
        self.dendrite = bt.dendrite(wallet=self.wallet)
        self.metagraph: bt.metagraph = self.subtensor.metagraph(self.config.netuid)
        torch.backends.cudnn.benchmark = True

        self.uid = assert_registered(self.wallet, self.metagraph)
        self.weights = torch.zeros_like(torch.tensor(self.metagraph.S))
        self.uids_to_eval: typing.Dict[str, typing.List] = {}

    async def try_sync_metagraph(self, ttl: int) -> bool:
        def sync_metagraph(endpoint):
            # Update self.metagraph
            self.metagraph = bt.subtensor(endpoint).metagraph(self.config.netuid)
            self.metagraph.save()

        process = multiprocessing.Process(
            target=sync_metagraph, args=(self.subtensor.chain_endpoint,)
        )
        process.start()
        process.join(timeout=ttl)
        if process.is_alive():
            process.terminate()
            process.join()
            bt.logging.error(f"Failed to sync metagraph after {ttl} seconds")
            return False

        bt.logging.info("Synced metagraph")
        self.metagraph.load()

        return True

    async def run_step(self):

        # Update self.metagraph
        synced_metagraph = await self.try_sync_metagraph(ttl=60)

        bt.logging.trace("Pulling competition ids for all hotkeys")
        competition_ids: typing.Dict[int, typing.Optional[str]] = {}
        for uid, hotkey in enumerate(list(self.metagraph.hotkeys)):
            competition_ids[uid] = constants.ORIGINAL_COMPETITION_ID

        self.weights.copy_(torch.tensor(self.metagraph.C))
        # Update consensus.
        self.consensus = self.metagraph.C
        if synced_metagraph:
            bt.logging.info("metagraph sync success: {}".format(self.consensus))
        else:
            bt.logging.warning("metagraph sync failed: {}".format(self.consensus))

        for competition in constants.COMPETITION_SCHEDULE:
            bt.logging.trace(
                f"Building consensus state for competition {competition.competition_id}"
            )
            # Evaluate all models on the first iteration.
            consensus = [i for i, val in enumerate(list(self.metagraph.consensus)) if
                         competition_ids[i] == competition.competition_id]

            self.uids_queue = EvalQueue(self.weights.cpu().numpy())
            uids_to_eval = self.uids_queue.take(self.config.miner_sample_size)
            bt.logging.debug(f"Uids to eval: {uids_to_eval}")
            print(f"Uids to eval: {uids_to_eval}")
            self.uids_to_eval[competition.competition_id] = uids_to_eval

            consensus_map = {uid: self.weights[uid].item() for uid in consensus}
            bt.logging.info(
                f"Consensus for competition {competition.competition_id}: {consensus_map}"
            )

            # Sync the first few models, we can sync the rest while running.

            uids_to_sync = list(uids_to_eval)[:self.config.miner_sample_size]
            hotkeys = [self.metagraph.hotkeys[uid] for uid in uids_to_sync]

            print(f"hotkeys: {hotkeys}")
            scores_per_uid = {uid: None for uid in uids_to_sync}
            metadata_per_uid = {uid: None for uid in uids_to_sync}
            block_per_uid = {uid: None for uid in uids_to_sync}
            is_duplicate = []
            lucky_num = int.from_bytes(os.urandom(4), 'little')
            for uid in uids_to_sync:
                metadata = retrieve_model_metadata(self.subtensor, self.config.netuid, self.metagraph.hotkeys[uid])
                print(f"uid: {uid}")
                print(f"results: {metadata}")
                if metadata is not None:
                    try:
                        download_dataset(metadata.id.namespace, metadata.id.commit)
                        download_dataset(constants.eval_namespace, constants.eval_commit, local_dir="eval_data")
                        eval_loss = train_lora(lucky_num)
                        other_uid = [k for k, v in scores_per_uid.items() if
                                     v is not None and math.isclose(eval_loss, v, rel_tol=1e-9)]

                        # check if duplicate
                        for range_id in other_uid:
                            if metadata_per_uid[range_id].block > metadata.block:
                                is_duplicate.append(range_id)
                            else:
                                is_duplicate.append(uid)

                        metadata_per_uid[uid] = metadata
                        scores_per_uid[uid] = eval_loss
                        block_per_uid[uid] = metadata.block
                    except Exception as e:
                        bt.logging.error(f"train error: {e}")
                        scores_per_uid[uid] = 0
                    finally:
                        clean_cache_folder()
                else:
                    scores_per_uid[uid] = 0
            uids_whitelist = [item for item in uids_to_sync if item not in is_duplicate]
            wins, win_rate = compute_wins(
                uids_whitelist, scores_per_uid,
                block_per_uid
            )
            model_weights = torch.tensor(
                [win_rate[uid] for uid in win_rate.keys()], dtype=torch.float32
            )
            step_weights = torch.softmax(model_weights / constants.temperature, dim=0)
            new_weights = torch.zeros_like(self.weights)
            for i, uid_i in enumerate(win_rate.keys()):
                new_weights[uid_i] = step_weights[i]

            consensus_alpha = constants.CONSTANT_ALPHA
            lr = constants.lr
            self.weights = (
                    (1 - lr) * self.weights + lr * new_weights
            )
            # To prevent the weights from completely diverging from consensus, blend in the consensus weights.
            C_normalized = torch.tensor(self.consensus / self.consensus.sum()).nan_to_num(0.0)
            self.weights = (1 - consensus_alpha) * self.weights + consensus_alpha * C_normalized
            self.weights = self.weights.nan_to_num(0.0)
            adjusted_weights = adjust_for_vtrust(self.weights.cpu().numpy(), self.consensus)
            adjusted_weights = torch.tensor(adjusted_weights, dtype=torch.float32)

            bt.logging.debug(f'new weights: {new_weights}')
            bt.logging.debug(f'self weights: {self.weights}')
            bt.logging.debug(f'consensus: {self.consensus}')
            bt.logging.debug(f'adjusted_weights: {adjusted_weights}')

            set_weights_with_err_msg(
                subtensor=self.subtensor,
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=self.metagraph.uids,
                weights=adjusted_weights,
            )

    async def run(self):
        while True:
            await self.run_step()

if __name__ == '__main__':
    asyncio.run(Validator().run())
