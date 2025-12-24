import pyautogui
import tkinter as tk
import time
import threading

def update_label():
    try:
        x, y = pyautogui.position()
        label.config(text=f"X: {x} | Y: {y}")
        # Position offset to not block the click point
        offset_x = 20
        offset_y = 20
        root.geometry(f"+{x + offset_x}+{y + offset_y}")
        root.after(20, update_label)
    except:
        pass

print("========================================")
print("   ARAFURA Mouse Coordinator (GUI)")
print("========================================")
print("Cierra la ventanita o Ctrl+C para salir.")

root = tk.Tk()
root.overrideredirect(True) # No borders
root.attributes("-topmost", True) # Keep on top
root.attributes("-alpha", 0.8) # Transparent
root.config(bg="black")

label = tk.Label(root, text="Init...", font=("Consolas", 10), fg="#00ff00", bg="black")
label.pack(padx=5, pady=2)

update_label()
root.mainloop()
