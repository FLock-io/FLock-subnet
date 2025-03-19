import bittensor as bt
from FLockDataset.validator.chain import retrieve_model_metadata

# Initialize a connection to the local blockchain
subtensor = bt.subtensor(network="local")
print("Subtensor Object:", subtensor)

success, message = bt.core.extrinsics.serving.set_metadata(
    subtensor=subtensor,
    wallet=bt.wallet(name="miner"),  # Ensure this is your miner's wallet
    netuid=1,  # Your subnet UID
    metadata={"model": "TestModel", "version": "1.0"}
)

print(f"Metadata Submission Status: {success}, Message: {message}")

# # List all subnet UIDs
# subnets = subtensor.get_all_subnets_info()
# print("Available Subnet UIDs:", subnets)

# Use an actual hotkey from one of your wallets
hotkey = "5CXC68jyK2MbJL1raVZQ5k8AY918xwJYujUPnz1NoPTYPBDu"

# Replace `0` with your actual subnet UID
subnet_uid = 1

metadata = retrieve_model_metadata(subtensor, subnet_uid, hotkey)
print("Retrieved Metadata:", metadata)
