import pytesseract
from PIL import Image
import io
import base64
import os
from pathlib import Path

class LocalOCREngine:
    def __init__(self):
        self.active = True
        self.lang = "spa+eng"
        
        # Determine local tessdata path
        base_path = Path(os.getcwd())
        tessdata_path = base_path / "tessdata"
        
        if tessdata_path.exists():
            # Tesseract 3.02 expects prefix to be the PARENT of 'tessdata' directory
            # If data is in C:/Auth/tessdata/, PREFIX must be C:/Auth/
            parent_dir = str(tessdata_path.parent)
            if not parent_dir.endswith(os.sep):
                parent_dir += os.sep
            
            print(f"[LocalOCR] Setting TESSDATA_PREFIX to Parent: {parent_dir}")
            os.environ["TESSDATA_PREFIX"] = parent_dir
        
        try:
            # Simple check
            pytesseract.get_tesseract_version()
        except:
            print("[LocalOCR] Warning: Tesseract might not be reachable.")

    def analyze_image_b64(self, b64_string: str) -> list:
        """
        Analyzes a base64 encoded image and returns text + bbox.
        """
        try:
            img_data = base64.b64decode(b64_string)
            image = Image.open(io.BytesIO(img_data))
            return self.analyze_image(image)
        except Exception as e:
            print(f"[LocalOCR] Decode Error: {e}")
            return []

    def analyze_image(self, image: Image.Image) -> list:
        """
        Returns list of {"text": str, "bbox": [x1, y1, x2, y2], "confidence": float}
        """
        results = []
        w, h = image.size

        # Try image_to_data first (Optimal)
        try:
            # Tesseract 3.05+ supports DICT output. 3.02 fails.
            data = pytesseract.image_to_data(image, lang=self.lang, output_type=pytesseract.Output.DICT)
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if int(data['conf'][i]) > 10: # Filter low confidence
                    text = data['text'][i].strip()
                    if len(text) > 0:
                        results.append({
                            "text": text,
                            "bbox": [data['left'][i], data['top'][i], 
                                     data['left'][i] + data['width'][i], 
                                     data['top'][i] + data['height'][i]],
                            "confidence": int(data['conf'][i]) / 100.0,
                            "ui_likelihood": 0.5 # Unknown without context
                        })
            return results
        except:
            # Fallback to image_to_boxes (Char level aggregation)
            # Format: 'char x1 y1 x2 y2 page' where (0,0) is BOTTOM-LEFT
            try:
                box_str = pytesseract.image_to_boxes(image, lang=self.lang)
                return self._aggregate_chars(box_str, h)
            except Exception as e:
                print(f"[LocalOCR] OCR Failed: {e}")
                return []

    def _aggregate_chars(self, box_args: str, img_height: int) -> list:
        """
        Aggregates characters into words based on proximity.
        Tesseract 'boxes' format uses Bottom-Left origin for Y.
        """
        lines = box_args.strip().splitlines()
        words = []
        current_word_chars = []
        last_x2 = -100
        
        # Threshold for character spacing (simulated space)
        CHAR_SPACING_THRESH = 15 

        for line in lines:
            parts = line.split()
            if len(parts) < 6: continue
            
            char = parts[0]
            if char == "~": continue # Tesseract often uses ~ for space? Verify.
            
            x1 = int(parts[1])
            y1_bott = int(parts[2])
            x2 = int(parts[3])
            y2_bott = int(parts[4])
            
            # Convert Y to Top-Left origin
            # y_top = H - y_bott
            # y1 (bottom) -> y2 (top) in new sys
            # y2 (top) -> y1 (top) in new sys
            y1 = img_height - y2_bott 
            y2 = img_height - y1_bott

            # Check spacing to start new word
            if last_x2 != -100 and (x1 - last_x2) > CHAR_SPACING_THRESH:
                if current_word_chars:
                    w = self._finalize_word(current_word_chars)
                    if w: words.append(w)
                    current_word_chars = []

            current_word_chars.append({'c': char, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            last_x2 = x2
        
        # Append last word
        if current_word_chars:
            w = self._finalize_word(current_word_chars)
            if w: words.append(w)

        return words

    def _finalize_word(self, chars: list) -> dict:
        text = "".join([c['c'] for c in chars]).strip()
        
        # Filter noise
        if len(text) < 2 and text not in ["a", "I", "1", "0"]:
            return None

        x1 = min([c['x1'] for c in chars])
        y1 = min([c['y1'] for c in chars])
        x2 = max([c['x2'] for c in chars])
        y2 = max([c['y2'] for c in chars])
        
        print(f"[LocalOCR] Debug Word: '{text}' at ({x1},{y1})")
        
        return {
            "text": text,
            "bbox": [x1, y1, x2, y2],
            "confidence": 0.8,
            "ui_likelihood": 0.5
        }
