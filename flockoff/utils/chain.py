import json
import bittensor as bt



def assert_registered(wallet: bt.wallet, metagraph: bt.metagraph) -> int:
    """Asserts the wallet is a registered miner and returns the miner's UID.

    Raises:
        ValueError: If the wallet is not registered.
    """
    if wallet.hotkey.ss58_address not in metagraph.hotkeys:
        raise ValueError(
            f"You are not registered. \nUse: \n`btcli s register --netuid {metagraph.netuid}` to register via burn \n or btcli s pow_register --netuid {metagraph.netuid} to register with a proof of work"
        )
    uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
    bt.logging.success(
        f"You are registered with address: {wallet.hotkey.ss58_address} and uid: {uid}"
    )
    return uid


def write_chain_commitment(
    wallet: bt.wallet, node, subnet_uid: int, data: dict
) -> bool:
    """
    Writes JSON data to the chain commitment.

    Args:
        wallet: The wallet for signing the transaction
        node: The subtensor node to connect to
        subnet_uid: The subnet identifier
        data: Dictionary containing the JSON data to commit

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Convert dict to JSON string
        json_str = json.dumps(data)

        # Pass the string directly - let bittensor handle the encoding
        result = node.commit(wallet, subnet_uid, json_str)
        return result
    except Exception as e:
        bt.logging.error(f"Failed to write chain commitment: {str(e)}")
        return False
