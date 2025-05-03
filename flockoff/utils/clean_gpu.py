import torch
import gc

def clean_gpu():
    """
    Cleans up GPU VRAM by:
    1. Emptying the CUDA cache
    2. Running garbage collection
    3. Clearing any remaining CUDA memory
    """
    if torch.cuda.is_available():
        # Empty CUDA cache
        torch.cuda.empty_cache()
        
        # Run garbage collection
        gc.collect()
        
        # Clear any remaining CUDA memory
        torch.cuda.synchronize()
        
        # Get current memory usage
        allocated = torch.cuda.memory_allocated() / 1024**2
        cached = torch.cuda.memory_reserved() / 1024**2
        
        print(f"GPU Memory cleaned up successfully!")
        print(f"Allocated memory: {allocated:.2f} MB")
        print(f"Cached memory: {cached:.2f} MB")
    else:
        print("No CUDA-capable GPU found!")

if __name__ == "__main__":
    clean_gpu() 