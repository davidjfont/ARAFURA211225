import sys
from pathlib import Path
from datetime import datetime

# Set base path
base_path = Path("c:/Users/wishk/Desktop/2026 - Innovation Architect/11_ARAFURA & AETHER")
sys.path.append(str(base_path))

try:
    from core.orchestrator import ArafuraOrchestrator
    print("Orchestrator imported successfully.")
    
    orch = ArafuraOrchestrator(base_path)
    print("Orchestrator initialized.")
    
    # Mocking router to avoid LLM calls
    class MockRouter:
        def route_request(self, *args, **kwargs):
            return "Mocked Response"
    
    orch.router = MockRouter()
    
    print("Testing process_input...")
    res = orch.process_input("hello")
    print(f"Response: {res}")
    
    print("Testing /aether...")
    res = orch.process_input("/aether")
    print(f"Response: {res}")
    
    print("Success! No crash detected in process_input.")

except Exception as e:
    print(f"FAILED with error: {e}")
    import traceback
    traceback.print_exc()
