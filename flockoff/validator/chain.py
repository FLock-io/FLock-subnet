import torch
import bittensor as bt
from flockoff.miners.data import ModelId, ModelMetadata
from typing import Optional, Tuple, Union, List
from flockoff import constants
from bittensor.core.extrinsics.commit_weights import commit_weights_extrinsic, reveal_weights_extrinsic
from bittensor.utils.weight_utils import generate_weight_hash
from bittensor.core.settings import version_as_int

def retrieve_model_metadata(
    subtensor: bt.subtensor, subnet_uid: int, hotkey: str
) -> Optional[ModelMetadata]:
    """Retrieves model metadata on this subnet for specific hotkey"""
    metadata = bt.core.extrinsics.serving.get_metadata(subtensor, subnet_uid, hotkey)

    if not metadata:
        return None

    try:
        # From the debug output, we can see metadata is a dictionary with nested structure
        commitment = metadata["info"]["fields"][0]

        chain_str = None

        # Handle tuple of dictionary with various Raw types (Raw24, Raw61, Raw68, etc.)
        if (
            isinstance(commitment, tuple)
            and len(commitment) > 0
            and isinstance(commitment[0], dict)
        ):
            # Find any key that starts with 'Raw'
            raw_keys = [key for key in commitment[0].keys() if key.startswith("Raw")]

            if raw_keys:
                raw_key = raw_keys[0]  # Use the first Raw key found
                # Extract the raw data (tuple of integers)
                raw_data = commitment[0][raw_key][0]
                # Convert the tuple of integers to a string
                chain_str = "".join(chr(i) for i in raw_data)
            else:
                bt.logging.error(f"No Raw key found in commitment: {commitment}")
                return None
        else:
            bt.logging.error(f"Unexpected commitment structure: {commitment}")
            return None

        # Check if this is JSON data (special case) or a repository ID
        if chain_str.startswith("{"):
            bt.logging.warning(f"Found JSON data instead of repository ID: {chain_str}")
            # This is not a valid repository ID, so we should skip it
            return None

        # Now we need to parse the chain_str
        model_id = None
        try:
            model_id = ModelId.from_compressed_str(chain_str)
        except Exception as e:
            # If the metadata format is not correct on the chain then we return None.
            bt.logging.error(
                f"Failed to parse the metadata on the chain for hotkey {hotkey}: {e}"
            )
            return None

        model_metadata = ModelMetadata(id=model_id, block=metadata["block"])
        return model_metadata

    except Exception as e:
        bt.logging.error(f"Error processing metadata: {e}")
        bt.logging.error(f"Stack trace:", exc_info=True)
        return None


def set_weights_with_err_msg(
    subtensor: bt.subtensor,
    wallet: bt.wallet,
    netuid: int,
    uids: Union[torch.LongTensor, list],
    weights: Union[torch.FloatTensor, list],
    ss58_address: str,
    salt: List[int],
    wait_for_inclusion: bool = False,
    wait_for_finalization: bool = False,
    max_retries: int = 5,
) -> Tuple[bool, str, List[Exception]]:
    """Same as subtensor.set_weights, but with additional error messages."""
    uid = subtensor.get_uid_for_hotkey_on_subnet(wallet.hotkey.ss58_address, netuid)
    retries = 0
    success = False
    message = "No attempt made. Perhaps it is too soon to set weights!"
    exceptions = []

    while (
        subtensor.blocks_since_last_update(netuid, uid) > subtensor.weights_rate_limit(netuid)  # type: ignore
        and retries < max_retries
    ):
        try:
            new_weight = [int(round(w * constants.SCORE_PRECISION)) for w in weights]
            commit_hash = generate_weight_hash(
                address=ss58_address,
                netuid=netuid,
                uids=uids,
                values=new_weight,
                salt=salt,
                version_key=version_as_int,
            )

            success, message = commit_weights_extrinsic(
                subtensor=subtensor,
                wallet=wallet,
                netuid=netuid,
                commit_hash=commit_hash,
                wait_for_inclusion=wait_for_inclusion,
                wait_for_finalization=wait_for_finalization,
            )

            if (wait_for_inclusion or wait_for_finalization) and success:
                return success, message, exceptions

        except Exception as e:
            bt.logging.exception(f"Error setting weights: {e}")
            exceptions.append(e)
        finally:
            retries += 1

    return success, message, exceptions


def reveal_weights_with_err_msg(
    subtensor: bt.subtensor,
    wallet: bt.wallet,
    netuid: int,
    uids: Union[torch.LongTensor, list],
    weights: Union[torch.FloatTensor, list],
    salt: List[int],
    wait_for_inclusion: bool = False,
    wait_for_finalization: bool = False,
    max_retries: int = 2,
) -> Tuple[bool, str, List[Exception]]:

    retries = 0
    success = False
    message = "Reveal extrinsic not available"
    exceptions: List[Exception] = []

    new_weight = [int(round(w * constants.SCORE_PRECISION)) for w in weights]

    while retries < max_retries:
        try:
            success, message = reveal_weights_extrinsic(
                subtensor=subtensor,
                wallet=wallet,
                netuid=netuid,
                uids=uids,
                weights=new_weight,
                salt=salt,
                version_key=version_as_int,
                wait_for_inclusion=wait_for_inclusion,
                wait_for_finalization=wait_for_finalization,
            )

            if (wait_for_inclusion or wait_for_finalization) and success:
                return success, message, exceptions

            if success:
                return success, message, exceptions
        except Exception as e:
            bt.logging.exception(f"Error revealing weights: {e}")
            exceptions.append(e)
        finally:
            retries += 1

    return success, message, exceptions
