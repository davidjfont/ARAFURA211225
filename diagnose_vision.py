import urllib.request
import json

def check_ollama():
    print("Checking Ollama...")
    try:
        with urllib.request.urlopen("http://localhost:11434/", timeout=2) as r:
            print(f"Ollama Status: {r.status}")
    except Exception as e:
        print(f"Ollama Error: {e}")
        return False

    print("Checking 'llava' model...")
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            models = [m['name'] for m in data['models']]
            print(f"Available Models: {models}")
            if "llava:latest" in models or "llava" in models:
                print("SUCCESS: 'llava' is available.")
            else:
                print("FAILURE: 'llava' not found. Run 'ollama pull llava'.")
                return False
    except Exception as e:
        print(f"List Models Error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    check_ollama()
