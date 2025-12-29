
import sys
import traceback
from pathlib import Path

# Add project root to path
sys.path.append(str(Path.cwd()))

print("--- DEBUG STARTUP ---")
try:
    print("1. Importing ArafuraCortex...")
    from terminals.cli.arafura_cli import ArafuraCortex
    
    print("2. Initializing ArafuraCortex...")
    app = ArafuraCortex()
    
    print("3. Starting Orchestrator (calling start())...")
    app.orchestrator.start()
    
    print("--- STARTUP SUCCESS ---")
except Exception:
    print("\n!!! STARTUP FAILED !!!")
    traceback.print_exc()
