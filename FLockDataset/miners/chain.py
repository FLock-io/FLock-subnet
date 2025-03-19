import bittensor as bt
import inspect
import functools
import multiprocessing
import asyncio
import time
from typing import Optional, Any

# Create a bittensor wallet and subtensor
wallet = bt.wallet()
subtensor = bt.subtensor()
print(wallet.coldkey.ss58_address)

def run_in_subprocess(func: functools.partial, ttl: int) -> Any:
    """Runs the provided function on a subprocess with 'ttl' seconds to complete."""
    def wrapped_func(func: functools.partial, queue: multiprocessing.Queue, log_queue: multiprocessing.Queue):
        try:
            log_queue.put(f"Starting {func.func.__name__} in subprocess")
            start_time = time.time()
            result = func()
            elapsed = time.time() - start_time
            log_queue.put(f"Completed {func.func.__name__} in {elapsed:.2f} seconds")
            queue.put(result)
        except (Exception, BaseException) as e:
            log_queue.put(f"Error in subprocess: {str(e)}")
            queue.put(e)
    
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    log_queue = ctx.Queue()
    process = ctx.Process(target=wrapped_func, args=[func, queue, log_queue])
    
    print(f"Starting subprocess for {func.func.__name__}")
    process.start()
    
    # Monitor the process and collect logs
    timeout = time.time() + ttl
    while process.is_alive() and time.time() < timeout:
        try:
            while not log_queue.empty():
                print(log_queue.get(block=False))
            time.sleep(0.5)
        except Exception:
            pass
    
    if process.is_alive():
        print(f"Process for {func.func.__name__} timed out after {ttl} seconds. Terminating...")
        process.terminate()
        process.join()
        raise TimeoutError(f"Failed to {func.func.__name__} after {ttl} seconds")
    
    # Collect any remaining logs
    while not log_queue.empty():
        try:
            print(log_queue.get(block=False))
        except Exception:
            pass
    
    try:
        result = queue.get(block=False)
        if isinstance(result, Exception):
            raise result
        if isinstance(result, BaseException):
            raise Exception(f"BaseException raised in subprocess: {str(result)}")
        return result
    except Exception as e:
        raise Exception(f"Failed to get result from subprocess: {str(e)}")

def debug_commit_process(func, wallet, subnet_uid, data):
    """A simplified version that tries to debug the commit process without subprocesses"""
    print(f"Attempting direct commit call with subnet_uid: {subnet_uid}, data length: {len(data)}")
    try:
        # First check if we can ping the endpoint
        print(f"Chain endpoint: {subtensor.chain_endpoint}")
        result = func(wallet, subnet_uid, data)
        print(f"Commit result: {result}")
        return result
    except Exception as e:
        print(f"Direct commit error: {str(e)}")
        print(f"Exception type: {type(e)}")
        raise e

async def store_model_metadata(subtensor: bt.subtensor,
                              wallet: Optional[bt.wallet],
                              subnet_uid: str, data: str):
    """Stores model metadata on this subnet for a specific wallet."""
    if wallet is None:
        raise ValueError("No wallet available to write to the chain.")
    
    print(f"Preparing to commit metadata to subnet {subnet_uid}")
    print(f"Wallet hotkey: {wallet.hotkey.ss58_address if hasattr(wallet, 'hotkey') else 'Not available'}")
    print(f"Wallet coldkey: {wallet.coldkey.ss58_address}")
    
    # Get network status before committing
    try:
        print("Checking network status...")
        # Use proper Bittensor API calls - adjust based on available methods
        print(f"Network: {subtensor.network}")
        print(f"Chain endpoint: {subtensor.chain_endpoint}")
    except Exception as e:
        print(f"Failed to get network status: {str(e)}")
    
    # Check if subnet exists and if wallet is registered
    try:
        print("Checking subnets...")
        subnets = subtensor.get_subnets()
        print(f"Available subnets: {[net.netuid for net in subnets]}")
        subnet_exists = any(str(net.netuid) == subnet_uid for net in subnets)
        print(f"Subnet {subnet_uid} exists: {subnet_exists}")
    except Exception as e:
        print(f"Failed to check subnet existence: {str(e)}")
    
    try:
        # Try a simpler approach without subprocess first
        print("Attempting direct commit first for debugging...")
        result = debug_commit_process(subtensor.commit, wallet, subnet_uid, data)
        print(f"Direct commit succeeded with result: {result}")
        return result
    except Exception as e:
        print(f"Direct commit failed: {str(e)}")
        print("Falling back to subprocess approach...")
    
    # Wrap calls to the subtensor in a subprocess with a timeout to handle potential hangs.
    partial = functools.partial(
        subtensor.commit,
        wallet,
        subnet_uid,
        data,
    )
    
    print(f"Committing metadata to subnet {subnet_uid} with timeout of 60 seconds...")
    try:
        return run_in_subprocess(partial, 60)
    except Exception as e:
        print("\nDiagnostic information:")
        print("1. Error received:", str(e))
        print("2. The 'no close frame received or sent' error suggests a WebSocket connection issue")
        print("3. This typically happens when the connection to the Bittensor network is interrupted")
        
        # Suggest possible solutions
        print("\nPossible solutions:")
        print("1. Check your internet connection")
        print("2. Try a different chain endpoint using: subtensor = bt.subtensor(chain_endpoint='wss://...')")
        print("3. Ensure your subnet_uid is correct")
        print("4. Make sure your wallet has enough balance for network fees")
        raise e

# Example function to use the wallet and subtensor with store_model_metadata
async def store_example_metadata():
    subnet_uid = "1"  # Example subnet ID - replace with your actual subnet ID
    metadata = "Example model metadata"  # Replace with your actual metadata
    
    print(f"\n--- Attempting to store metadata ---")
    print(f"Subnet UID: {subnet_uid}")
    print(f"Metadata: {metadata}")
    
    try:
        start_time = time.time()
        await store_model_metadata(subtensor, wallet, subnet_uid, metadata)
        elapsed = time.time() - start_time
        print(f"Successfully stored metadata in {elapsed:.2f} seconds")
    except Exception as e:
        print(f"Failed to store metadata: {str(e)}")

# Main execution function to run async code
async def main():
    # Print wallet info
    print(f"Using wallet with address: {wallet.coldkey.ss58_address}")
    
    # Print subtensor connection info
    try:
        print(f"Connected to network: {subtensor.network}")
        print(f"Subtensor URL: {subtensor.chain_endpoint}")
    except Exception as e:
        print(f"Failed to get subtensor info: {str(e)}")
    
    # Store example metadata
    await store_example_metadata()

# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
