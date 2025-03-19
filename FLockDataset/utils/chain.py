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



