
from PIL import ImageGrab
import os

print("📸 Testing Screen Capture...")
try:
    # 1. Capture Full Screen
    img = ImageGrab.grab()
    print(f"✅ Capture Success: Size {img.size}")
    
    # 2. Save
    path = os.path.abspath("test_fullscreen.png")
    img.save(path)
    print(f"💾 Saved to: {path}")
    
    # 3. Test Region Capture (0,0,500,500)
    bbox = (0, 0, 500, 500)
    img_region = ImageGrab.grab(bbox=bbox)
    print(f"✅ Region Capture Success: Size {img_region.size}")
    region_path = os.path.abspath("test_region.png")
    img_region.save(region_path)
    print(f"💾 Saved region to: {region_path}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
