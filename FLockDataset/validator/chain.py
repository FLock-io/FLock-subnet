import torch
import bittensor as bt
from FLockDataset.miners.data import ModelId, ModelMetadata
from typing import Optional
from typing import Optional, Tuple, Union
from bittensor.core.extrinsics.set_weights import set_weights_extrinsic

def retrieve_model_metadata(subtensor: bt.subtensor, subnet_uid: int, hotkey: str) -> Optional[ModelMetadata]:
    """Retrieves model metadata on this subnet for specific hotkey"""
    metadata = bt.core.extrinsics.serving.get_metadata(subtensor, subnet_uid, hotkey)
    bt.logging.debug(f"metadata: {metadata}")
    
    if not metadata:
        return None
    
    try:
        # From the debug output, we can see metadata is a dictionary with nested structure
        commitment = metadata["info"]["fields"][0]
        bt.logging.debug(f"Commitment structure: {commitment}")
        
        chain_str = None
        
        # Handle tuple of dictionary with various Raw types (Raw24, Raw61, Raw68, etc.)
        if isinstance(commitment, tuple) and len(commitment) > 0 and isinstance(commitment[0], dict):
            # Find any key that starts with 'Raw'
            raw_keys = [key for key in commitment[0].keys() if key.startswith('Raw')]
            
            if raw_keys:
                raw_key = raw_keys[0]  # Use the first Raw key found
                # Extract the raw data (tuple of integers)
                raw_data = commitment[0][raw_key][0]
                # Convert the tuple of integers to a string
                chain_str = ''.join(chr(i) for i in raw_data)
                bt.logging.debug(f"Parsed chain string: {chain_str}")
            else:
                bt.logging.error(f"No Raw key found in commitment: {commitment}")
                return None
        else:
            bt.logging.error(f"Unexpected commitment structure: {commitment}")
            return None
        
        # Now we need to parse the chain_str
        # The format should be something like: "reponame:commit_id:commit_hash"
        model_id = None
        try:
            model_id = ModelId.from_compressed_str(chain_str)
            bt.logging.info(f"Successfully parsed model ID: {model_id}")
        except Exception as e:
            # If the metadata format is not correct on the chain then we return None.
            bt.logging.error(f"Failed to parse the metadata on the chain for hotkey {hotkey}: {e}")
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
        uids: [torch.LongTensor, list],
        weights: Union[torch.FloatTensor, list],

        wait_for_inclusion: bool = False,
        wait_for_finalization: bool = False,
        max_retries: int = 5,
) -> Tuple[bool, str, list[Exception]]:
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
            success, message = set_weights_extrinsic(
                subtensor=subtensor,
                wallet=wallet,
                netuid=netuid,
                uids=uids,
                weights=weights,
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
