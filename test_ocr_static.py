
import sys
import base64
import os

# Add current directory to path so we can import 'core'
sys.path.append(os.getcwd())

from core.local_ocr import LocalOCREngine

def test_static_ocr():
    ocr = LocalOCREngine()
    image_path = "test_region.png"
    
    if not os.path.exists(image_path):
        print(f"❌ Error: {image_path} not found. Run test_capture.py first.")
        return

    print(f"📸 Loading {image_path}...")
    with open(image_path, "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode('utf-8')

    print(f"📖 Running OCR Scan (Lang: {ocr.lang})...")
    try:
        results = ocr.analyze_image_b64(b64_string)
        
        if not results:
            print("⚠️ OCR returned NO results.")
        else:
            print(f"✅ Found {len(results)} elements:")
            for item in results:
                print(f"   - '{item['text']}' (Conf: {item['confidence']})")
                
    except Exception as e:
        print(f"❌ Exception during OCR: {e}")

if __name__ == "__main__":
    test_static_ocr()
