import tkinter as tk
import json
import time
from pathlib import Path

# Config
BASE_PATH = Path(__file__).parent.parent.parent
STATE_FILE = BASE_PATH / "core" / "memory" / "overlay_state.json"

class VisualOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ARAFURA Vision Overlay")
        
        # Full screen transparent
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3) # Overall transparency (for debug, later use specialized transparency)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black") # Black is transparent
        
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.border_rect = None
        self.cursor_oval = None
        
        # Loop
        self.update_state()
        self.root.mainloop()

    def update_state(self):
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    
                target = data.get('target_rect') # [x, y, w, h]
                cursor = data.get('cursor_pos')  # [x, y]
                active = data.get('active', False)
                
                self.canvas.delete("all")
                
                if active and target:
                    x, y, w, h = target
                    
                    # 1. Blue Border (Outer Glow effect simulation)
                    self.canvas.create_rectangle(
                        x-5, y-5, x+w+5, y+h+5, 
                        outline="#00FFFF", width=4
                    )
                    
                    # 2. Label
                    self.canvas.create_text(
                        x + 20, y - 15,
                        text="ARAFURA VISION TARGET",
                        fill="#00FFFF",
                        font=("Consolas", 12, "bold"),
                        anchor="w"
                    )

                if cursor:
                    cx, cy = cursor
                    # AI Cursor (Circle)
                    r = 10
                    self.canvas.create_oval(
                        cx-r, cy-r, cx+r, cy+r,
                        outline="#00FFFF", width=2, fill="#00AAFF"
                    )
                    
        except Exception as e:
            pass
            # print(e) 
            
        self.root.after(100, self.update_state)

if __name__ == "__main__":
    VisualOverlay()
