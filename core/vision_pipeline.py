import os
import time
import threading
import numpy as np
import cv2
from PIL import ImageGrab, Image
import base64
import io
from datetime import datetime

class VisionPipeline:
    """
    ARAFURA v4.0 - Asynchronous Vision Pipeline
    Implements:
    - Dedicated Capture Thread (30 FPS capability)
    - Shared Buffer (Virtual)
    - Differential Vision (Pixel Delta Detection)
    - Windows/Linux Compatibility
    """
    def __init__(self, target_window=None, fps=5):
        self.target_window = target_window
        self.fps = fps
        self.interval = 1.0 / fps
        self.running = False
        self.thread = None
        
        # Shared Buffer (State)
        self.last_frame = None
        self.current_frame = None
        self.delta_score = 0.0
        self.is_changed = False
        
        # Config
        self.delta_threshold = 0.001  # 0.1% change required to trigger "changed"
        self.lock = threading.Lock()

    def start(self):
        """Starts the asynchronous capture loop"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("[VisionPipeline] Started.")

    def stop(self):
        """Stops the capture loop"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[VisionPipeline] Stopped.")

    def set_window(self, window_obj):
        """Updates the target window for capture"""
        with self.lock:
            self.target_window = window_obj

    def _capture_loop(self):
        """Internal loop running in a dedicated thread"""
        while self.running:
            start_time = time.time()
            
            frame = self._capture_screen()
            if frame is not None:
                self._update_buffer(frame)
            
            # Control FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, self.interval - elapsed)
            time.sleep(sleep_time)

    def _capture_screen(self):
        """Platform-agnostic screen capture"""
        try:
            if self.target_window:
                # Capture specific window
                w = self.target_window
                bbox = (w.left, w.top, w.left + w.width, w.top + w.height)
                img = ImageGrab.grab(bbox=bbox)
            else:
                # Full screen fallback
                img = ImageGrab.grab()
            
            # Convert to NumPy for CV2 processing
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            # print(f"[VisionPipeline] Capture error: {e}")
            return None

    def _update_buffer(self, new_frame):
        """Updates the shared buffer and calculates differential delta"""
        with self.lock:
            if self.current_frame is not None:
                self.last_frame = self.current_frame
                
                # DIFFERENTIAL VISION: Calculate MSE or structural difference
                # Fast Delta: Mean Squared Error or Absolute Difference
                if self.last_frame.shape == new_frame.shape:
                    diff = cv2.absdiff(self.last_frame, new_frame)
                    self.delta_score = np.mean(diff) / 255.0
                    self.is_changed = self.delta_score > self.delta_threshold
                else:
                    self.is_changed = True
            else:
                self.is_changed = True
            
            self.current_frame = new_frame

    def get_latest_frame(self, force=False):
        """
        Retrieves the latest frame as a Base64 string for the LLM.
        Only returns if changed, unless force=True.
        """
        with self.lock:
            if self.current_frame is None:
                return None, False
            
            if not self.is_changed and not force:
                return None, False
            
            # Convert to JPEG for transmission
            _, buffer = cv2.imencode('.jpg', self.current_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            b64_str = base64.b64encode(buffer).decode('utf-8')
            
            # Reset change flag after delivery
            change_detected = self.is_changed
            self.is_changed = False 
            
            return b64_str, change_detected

    def get_status(self):
        """Returns visual health metrics"""
        return {
            "fps": self.fps,
            "delta_score": round(self.delta_score, 6),
            "is_animated": self.delta_score > 0.05,
            "active": self.running
        }

    def check_impact(self, reference_frame_cv):
        """
        Compares the CURRENT screen against a reference frame.
        Returns (has_impact: bool, score: float)
        """
        if reference_frame_cv is None or self.current_frame is None:
            return False, 0.0
            
        with self.lock:
            if reference_frame_cv.shape != self.current_frame.shape:
                return True, 1.0 # Significant change (resize/move)
            
            diff = cv2.absdiff(reference_frame_cv, self.current_frame)
            score = np.mean(diff) / 255.0
            return score > self.delta_threshold, score

    def get_current_cv(self):
        """Returns the raw current frame for reference"""
        with self.lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def get_region_crop(self, bbox: tuple):
        """
        Captures a specific region of the screen (x, y, x2, y2).
        Returns Base64 encoded PNG for high fidelity.
        Used for Tile Scanning (500x500).
        """
        try:
            # Capture using ImageGrab (efficient for regions)
            img = ImageGrab.grab(bbox=bbox)
            
            # Convert to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return b64_str
        except Exception as e:
            print(f"[VisionPipeline] Region capture error: {e}")
            return None

if __name__ == "__main__":
    # Test execution
    vp = VisionPipeline(fps=2)
    vp.start()
    try:
        for _ in range(5):
            time.sleep(2)
            b64, changed = vp.get_latest_frame()
            status = vp.get_status()
            print(f"Frame Change: {changed} | Delta: {status['delta_score']}")
    finally:
        vp.stop()
