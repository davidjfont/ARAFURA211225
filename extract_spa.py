
import tarfile
import shutil
import os

try:
    with tarfile.open('tessdata/spa.tar.gz', 'r:gz') as tar:
        # Member name is 'tesseract-ocr/tessdata/spa.traineddata'
        member = tar.getmember('tesseract-ocr/tessdata/spa.traineddata')
        member.name = 'spa.traineddata' # flatten
        tar.extract(member, path='tessdata')
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
