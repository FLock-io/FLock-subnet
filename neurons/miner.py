import time
import asyncio
import argparse
import bittensor as bt

from flockoff.utils.chain import (
    assert_registered,
)
from flockoff.constants import Competition
from flockoff.miners import model, chain
from flockoff.miners.data import ModelId
from dotenv import load_dotenv

load_dotenv()


def get_config():
    # Initialize an argument parser
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hf_repo_id",
        type=str,
        help="The hugging face repo id, which should include the org or user and repo name",
    )
    parser.add_argument(
        "--netuid",
        type=str,
        help="The subnet UID.",
    )

    parser.add_argument(
        "--dataset_path",
        type=str,
        help="The dataset path, name as data.json",
    )

    # Include wallet and logging arguments from bittensor
    bt.wallet.add_args(parser)
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    # Parse the arguments and create a configuration namespace
    return bt.config(parser)


async def main(config: bt.config):
    # Create bittensor objects.
    bt.logging(config=config)

    wallet = bt.wallet(config=config)
    subtensor = bt.subtensor(config=config)
    metagraph: bt.metagraph = subtensor.metagraph(int(config.netuid))

    bt.logging.info(f"Starting miner with config: {config}")

    # Make sure we're registered and have a HuggingFace token.
    assert_registered(wallet, metagraph)

    commit_id = model.upload_data(config.hf_repo_id, config.dataset_path)

    competition = Competition.from_defaults()

    model_id_with_commit = ModelId(
        namespace=config.hf_repo_id, commit=commit_id, competition_id=competition.id
    )
    bt.logging.success(
        f"Now committing to the chain with model_id: {model_id_with_commit}"
    )
    bt.logging.debug(
        f"Now committing to the chain with model_id: {model_id_with_commit}"
    )

    # We can only commit to the chain every 20 minutes, so run this in a loop, until successful.
    while True:
        try:
            await chain.store_model_metadata(
                subtensor=subtensor,
                wallet=wallet,
                subnet_uid=config.netuid,
                data=model_id_with_commit.to_compressed_str(),
            )

            bt.logging.success("Committed dataset to the chain.")
            break
        except Exception as e:
            bt.logging.error(f"Failed to advertise model on the chain: {e}")
            bt.logging.error("Retrying in 120 seconds...")
            time.sleep(120)


if __name__ == "__main__":
    config = get_config()
    asyncio.run(main(config))
