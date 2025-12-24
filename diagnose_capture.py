import sys
import os
import io
import base64
from pathlib import Path

# Add core path
sys.path.append(str(Path.cwd()))

def check_capture():
    print("Checking Visual Dependencies...")
    try:
        import pyautogui
        import pygetwindow as gw
        from PIL import ImageGrab, Image
        print("Imports: OK")
    except ImportError as e:
        print(f"Imports FAILED: {e}")
        return

    print("Checking Window List...")
    try:
        windows = gw.getAllWindows()
        print(f"Windows Found: {len(windows)}")
        if not windows:
            print("No windows? Weird.")
            return
            
        target = None
        for w in windows:
            if w.title and w.visible and "Chrome" in w.title:
                target = w
                break
        
        if not target:
            target = windows[0]
            
        print(f"Targeting Window: '{target.title}'")
        
        try:
            # Activate
            # target.activate() # Skipping activation to avoid stealing focus aggressively during test
            pass
        except: pass
        
        print(f"Capturing Region: {target.left}, {target.top}, {target.width}, {target.height}")
        
        # Capture
        img = ImageGrab.grab(bbox=(target.left, target.top, target.left + target.width, target.top + target.height))
        print(f"Capture Success: {img.size}")
        
        # Convert
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        print(f"Base64 Len: {len(b64)}")
        print("CAPTURE DIAGNOSIS: PASS")
        
    except Exception as e:
        print(f"CAPTURE DIAGNOSIS: FAILED -> {e}")

if __name__ == "__main__":
    check_capture()
