try:
    import pytesseract
    from PIL import Image
    import sys

    # Create a dummy image with some text
    img = Image.new('RGB', (100, 30), color = (255, 255, 255))
    import io
    
    # Try basic string
    print("Testing string...")
    print(pytesseract.image_to_string(img))
    
    # Try boxes (char level)
    print("Testing boxes...")
    boxes = pytesseract.image_to_boxes(img)
    print("Boxes result length:", len(boxes))
    print("Success.")

except Exception as e:
    print(f"Error: {e}")
