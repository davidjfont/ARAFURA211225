import tkinter as tk
import threading
import time
import ctypes
from pathlib import Path

class GhostCursor:
    """
    ARAFURA v4.1 -ARAFURA Pointer (Dual Cursor)
    Provides a non-blocking, click-through overlay representing the AI's focus.
    """
    def __init__(self):
        self.root = None
        self.canvas = None
        self.cursor_id = None
        self.label_id = None
        self.target_rect_id = None
        self.precision_rect_id = None # 500x500 Vision Box
        
        self.x, self.y = -100, -100 # Default off-screen
        self.target_rect = None # [x, y, w, h]
        self.state = "tracking" # tracking | armed | acting
        
        self.colors = {
            "tracking": "#00FF41", # Aether Neon Green
            "scanning": "#00FFFF", # Cyan (Exploratory)
            "armed": "#FFD700",    # Matrix Gold (Targeting)
            "acting": "#FF3131"     # Danger Red (Action)
        }
        
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """Starts the overlay in a separate thread"""
        if self._running: return
        self._running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        self.root = tk.Tk()
        self.root.title("ARAFURA Pointer")
        self.root.overrideredirect(True) # No window decorations
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        
        # Windows-specific: Click-through via GWL_EXSTYLE
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            # WS_EX_LAYERED = 0x80000, WS_EX_TRANSPARENT = 0x20
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020)
        except Exception:
            pass # Non-windows or failed to set click-through

        # Full screen canvas
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        
        # Transparent background color hack
        bg_color = "#000001" # Near black
        self.root.config(bg=bg_color)
        self.root.attributes("-transparentcolor", bg_color)
        
        self.canvas = tk.Canvas(self.root, width=sw, height=sh, bg=bg_color, highlightthickness=0)
        self.canvas.pack()
        
        # Graphics initialization
        r = 8
        self.cursor_id = self.canvas.create_oval(-20,-20,0,0, outline="white", width=2, fill=self.colors["tracking"])
        self.label_id = self.canvas.create_text(-20,-20, text="ARAFURA", fill="white", font=("Consolas", 8, "bold"))
        self.target_rect_id = self.canvas.create_rectangle(-20,-20,0,0, outline=self.colors["tracking"], width=2)
        self.precision_rect_id = self.canvas.create_rectangle(-20, -20, 0, 0, outline=self.colors["armed"], dash=(5, 5))
        
        self._update_ui_loop()
        self.root.mainloop()

    def _update_ui_loop(self):
        if not self._running: return
        
        with self._lock:
            # Update Cursor (Aether Pointer)
            r = 10 if self.state == "tracking" else 15
            self.canvas.coords(self.cursor_id, self.x - r, self.y - r, self.x + r, self.y + r)
            self.canvas.itemconfig(self.cursor_id, fill=self.colors.get(self.state, "white"))
            
            # Update Label
            self.canvas.coords(self.label_id, self.x, self.y + r + 15)
            self.canvas.itemconfig(self.label_id, text=f"ARAFURA [{self.state.upper()}]")
            
            # Update Precision Box (500x500)
            if self.state in ["scanning", "armed", "acting"]:
                psize = 500
                self.canvas.coords(self.precision_rect_id, 
                                 self.x - psize//2, self.y - psize//2, 
                                 self.x + psize//2, self.y + psize//2)
                self.canvas.itemconfig(self.precision_rect_id, outline=self.colors[self.state])
            else:
                self.canvas.coords(self.precision_rect_id, -1000, -1000, -1000, -1000)

            # Update Target Border (Active Window Glow)
            if self.target_rect:
                tx, ty, tw, th = self.target_rect
                self.canvas.coords(self.target_rect_id, tx-2, ty-2, tx+tw+2, ty+th+2)
                self.canvas.itemconfig(self.target_rect_id, outline=self.colors.get(self.state, "white"))
            else:
                self.canvas.coords(self.target_rect_id, -100, -100, -100, -100)
                
        self.root.after(30, self._update_ui_loop)

    def update_position(self, x, y):
        with self._lock:
            self.x, self.y = x, y

    def set_target_window(self, x, y, w, h):
        with self._lock:
            self.target_rect = [x, y, w, h]

    def set_state(self, state):
        with self._lock:
            if state in self.colors:
                self.state = state

    def stop(self):
        self._running = False
        if self.root:
            self.root.quit()

if __name__ == "__main__":
    # Test
    gc = GhostCursor()
    gc.start()
    time.sleep(1)
    gc.update_position(500, 500)
    gc.set_state("armed")
    time.sleep(5)
    gc.stop()
