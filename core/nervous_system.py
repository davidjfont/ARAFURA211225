import time
import threading
from PIL import Image, ImageChops, ImageStat

class ReflexAction:
    def __init__(self, action_type, params=None):
        self.type = action_type # 'CLICK', 'KEY', 'WAIT', 'ABORT'
        self.params = params or {}
        self.timestamp = time.time()

class ReflexController:
    """
    The 'Reptilian Brain' of ARAFURA.
    Operates on raw visual heuristics, diffs, and rules.
    NO LLMS allowed here. Latency target: < 50ms.
    """
    def __init__(self):
        self.last_frame = None
        self.last_process_time = 0
        self.diff_threshold = 15.0 # Sensitivity (0-255 scaling)
        self.lock = threading.Lock()
        self.consecutive_still_frames = 0
        self.consecutive_motion_frames = 0

    def process_frame(self, current_frame: Image.Image, state_strategy: str) -> str:
        """
        Analyzes a frame and returns a signal:
        - 'STILL': Nothing happening.
        - 'MOTION': Significant change detected.
        - 'TRIGGER_THOUGHT': Complexity detected, wake up cortex.
        """
        if not current_frame:
            return "NO_SIGNAL"

        with self.lock:
            now = time.time()
            # 1. Resize for speed (128px is enough for reflexes)
            thumb = current_frame.resize((128, 128)).convert('L')
            
            if not self.last_frame:
                self.last_frame = thumb
                return "STILL"

            # 2. Compute Diff
            diff = ImageChops.difference(self.last_frame, thumb)
            stat = ImageStat.Stat(diff)
            mean_diff = sum(stat.mean) / len(stat.mean)
            
            self.last_frame = thumb
            
            # 3. Heuristics based on Strategy
            # In AGGRESSIVE/GAMER mode, we are hyper-sensitive to motion
            if state_strategy in ["GAMER", "AGGRESSIVE"]:
                threshold = 5.0
            else:
                threshold = self.diff_threshold

            if mean_diff > threshold:
                self.consecutive_motion_frames += 1
                self.consecutive_still_frames = 0
                return "MOTION"
            else:
                self.consecutive_still_frames += 1
                self.consecutive_motion_frames = 0
                return "STILL"
            
    def get_reflex_action(self, signal: str, state_strategy: str) -> ReflexAction:
        """
        Determines if a reflex action is needed based on the signal.
        """
        # Example Reflex Rule 1: Anti-AFK / Wakeup
        # If we see motion after long stillness, maybe we focus?
        if signal == "MOTION" and self.consecutive_still_frames > 50:
            return ReflexAction("LOG", {"msg": "👁️ [Reflex] Movement detected."})

        # Example Reflex Rule 2: Gamer Reflex (Stub)
        # If strategy is GAMER and we see a massive flash (explosion?), maybe click?
        # (This would need specific region monitoring, kept simple for now)
        
        return None
