import sys
from pathlib import Path
sys.path.append(str(Path.cwd()))
from core.router import ModelRouter

print("Initializing Router...")
router = ModelRouter(Path.cwd())

print("\n--- Config for Vision ---")
print(router.roles_config.get('vision'))

print("\n--- Attempting to Load Vision ---")
model = router.load_model("vision")

if model:
    print(f"SUCCESS: Loaded model: {model.model_name}")
    # Test inference
    print("Testing connection...")
    try:
        res = model.create_chat_completion(messages=[{"role": "user", "content": "hello"}])
        print(f"Response: {res}")
    except Exception as e:
        print(f"Inference Error: {e}")
else:
    print("FAILURE: Could not load vision model.")
    print("Active models:", router.get_active_models())
