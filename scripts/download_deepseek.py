import os
import urllib.request
import time
from pathlib import Path

# Config
URL = "https://huggingface.co/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF/resolve/main/DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"
DEST_DIR = Path(__file__).parent.parent / "models"
DEST_FILE = DEST_DIR / "DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"

def download_file():
    if not DEST_DIR.exists():
        DEST_DIR.mkdir(parents=True)
        
    print(f"[*] Downloading DeepSeek R1 GGUF...")
    print(f"    Source: {URL}")
    print(f"    Dest:   {DEST_FILE}")
    
    start_time = time.time()
    
    def reporthook(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            if percent % 10 == 0: # Print every 10%
                elapsed = time.time() - start_time
                speed = (count * block_size) / (elapsed + 0.1) / (1024*1024)
                print(f"    Progress: {percent}% ({speed:.2f} MB/s)", end='\r')

    try:
        urllib.request.urlretrieve(URL, DEST_FILE, reporthook=reporthook)
        print(f"\n[+] Download Complete: {DEST_FILE.name}")
        print(f"    Size: {DEST_FILE.stat().st_size / (1024**3):.2f} GB")
    except Exception as e:
        print(f"\n[!] Error: {e}")

if __name__ == "__main__":
    download_file()
