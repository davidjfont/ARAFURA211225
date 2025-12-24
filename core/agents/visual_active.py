import os
import time
import json
import base64
import io
import threading
from pathlib import Path
from datetime import datetime

# Intentos de importación de dependencias visuales
try:
    import pyautogui
    import pygetwindow as gw
    from PIL import ImageGrab, Image
    VISUAL_DEPS_OK = True
except ImportError:
    VISUAL_DEPS_OK = False
    pyautogui = None
    gw = None
    ImageGrab = None
    Image = None

class VisualAgent:
    def __init__(self, memory_manager, llm_wrapper=None):
        self.memory = memory_manager
        self.llm = llm_wrapper
        self.active_window = None
        self.running = False
        self.base_path = Path(__file__).parent.parent.parent
        self.prompt_path = self.base_path / "core" / "prompts" / "arafura_agent_visual.md"
        
        # Configuraciones de seguridad
        if pyautogui:
            pyautogui.FAILSAFE = True  # Mueve el mouse a la esquina para abortar
            pyautogui.PAUSE = 1.0     # Pausa entre acciones

    def set_llm(self, llm_wrapper):
        """Actualiza el cerebro del agente post-inicialización"""
        self.llm = llm_wrapper

    def check_dependencies(self):
        missing = []
        if not pyautogui: missing.append("pyautogui")
        if not gw: missing.append("pygetwindow")
        if not ImageGrab: missing.append("pillow")
        return missing

    def list_windows(self):
        if not gw: return []
        # Filtrar ventanas visibles y con título, excluyendo el overlay propio
        return [w for w in gw.getAllWindows() if w.title and w.visible and w.title != "Program Manager" and "ARAFURA Vision Overlay" not in w.title]

    def _update_overlay_state(self, x=0, y=0):
        """Sincroniza el estado con el overlay"""
        return # DISABLED BY USER REQUEST
        
        state_file = self.base_path / "core" / "memory" / "overlay_state.json"
        
        data = {
            "active": False,
            "target_rect": None,
            "cursor_pos": [x, y]
        }
        
        if self.active_window:
            data["active"] = True
            data["target_rect"] = [
                self.active_window.left,
                self.active_window.top,
                self.active_window.width,
                self.active_window.height
            ]
            
        try:
            with open(state_file, 'w') as f:
                json.dump(data, f)
        except Exception: 
            pass

    def get_mouse_pos(self):
        """Devuelve coordenadas (x, y) actuales"""
        if pyautogui:
            return pyautogui.position()
        return (0, 0)
    
    def select_window(self, window_obj):
        self.active_window = window_obj
        self.force_activate()  # Bring to front immediately
        self._update_overlay_state()
        return True
    
    def force_activate(self):
        """Force the active window to the foreground using multiple methods"""
        if not self.active_window:
            return False
        
        try:
            # Method 1: pygetwindow activate
            self.active_window.activate()
            time.sleep(0.1)
        except:
            pass
        
        try:
            # Method 2: Minimize and restore (forces focus on Windows)
            if hasattr(self.active_window, 'minimize') and hasattr(self.active_window, 'restore'):
                self.active_window.minimize()
                time.sleep(0.05)
                self.active_window.restore()
                time.sleep(0.1)
        except:
            pass
        
        try:
            # Method 3: Use win32gui if available (most reliable on Windows)
            import win32gui
            import win32con
            hwnd = self.active_window._hWnd
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except ImportError:
            pass  # win32gui not installed
        except Exception as e:
            print(f"Win32 activate error: {e}")
        
        return True

    def execute_decision(self, decision_json):
        """Ejecuta la acción dictada por el JSON del LLM"""
        if not decision_json or 'decision' not in decision_json:
            return "No valid decision"
        
        action = decision_json['decision']
        
        # Logs safe
        print(f" -> Ejecutando: {action}")
        if self.memory:
            self.memory.log("arafura_visual", f"Acción física: {action}")
        
        # Intérprete de acciones simples (extender según necesidad)
        try:
            # Force window to foreground BEFORE any action
            self.force_activate()
            
            # Ej: "click 200, 300"
            if action.startswith("click") and not action.startswith("doubleclick"):
                parts = action.replace(",", "").split()
                if len(parts) >= 3:
                    x, y = int(parts[1]), int(parts[2])
                    
                    # VLM outputs ABSOLUTE coordinates (already screen-based)
                    # Only add offset if coords are clearly in-window relative (small values)
                    if x < self.active_window.width and y < self.active_window.height:
                        # Relative -> Absolute
                        abs_x = self.active_window.left + x
                        abs_y = self.active_window.top + y
                    else:
                        # Already absolute
                        abs_x, abs_y = x, y
                    
                    print(f" -> Click en: {abs_x}, {abs_y}")
                    pyautogui.click(abs_x, abs_y)
                    time.sleep(0.05)  # Let click register
                    self._update_overlay_state(abs_x, abs_y)
            
            # Ej: "type hola"
            elif action.startswith("type"):
                text = action.split(" ", 1)[1]
                # Force Focus (Unconditional)
                try:
                    self.active_window.activate()
                    time.sleep(0.15)
                except Exception as e:
                    print(f" [!] Activate failed: {e}")
                pyautogui.write(text)
                
            # Ej: "key enter" or "key up" or "key space"
            elif action.startswith("key"):
                key = action.split(" ", 1)[1].lower()
                try:
                    self.active_window.activate()
                    time.sleep(0.1)
                except: pass
                # Map common aliases
                key_map = {
                    "arriba": "up", "abajo": "down", "izquierda": "left", "derecha": "right",
                    "intro": "enter", "espacio": "space", "escape": "esc", "tab": "tab"
                }
                key = key_map.get(key, key)
                pyautogui.press(key)

            # Ej: "scroll 50" (up) or "scroll -50" (down) or "scroll up" or "scroll down"
            elif action.startswith("scroll"):
                param = action.split(" ", 1)[1].lower()
                try:
                    self.active_window.activate()
                    time.sleep(0.1)
                except: pass
                
                # Support both numeric and text directions
                if param in ["up", "arriba"]:
                    amount = 500
                elif param in ["down", "abajo"]:
                    amount = -500
                else:
                    try:
                        amount = int(param)
                    except:
                        amount = 300
                pyautogui.scroll(amount)
            
            # Ej: "hotkey ctrl c" or "hotkey shift space"
            elif action.startswith("hotkey"):
                keys = action.split(" ")[1:]
                try:
                    self.active_window.activate()
                    time.sleep(0.1)
                except: pass
                pyautogui.hotkey(*keys)
            
            # Ej: "doubleclick 200, 300"
            elif action.startswith("doubleclick"):
                parts = action.replace(",", "").split()
                if len(parts) >= 3:
                    x, y = int(parts[1]), int(parts[2])
                    try:
                        self.active_window.activate()
                        time.sleep(0.15)
                    except: pass
                    
                    if x < self.active_window.width and y < self.active_window.height:
                        abs_x = self.active_window.left + x
                        abs_y = self.active_window.top + y
                    else:
                        abs_x, abs_y = x, y
                    
                    print(f" -> Double Click: {abs_x}, {abs_y}")
                    pyautogui.doubleClick(abs_x, abs_y)
            
            # Ej: "drag 100 200 300 400" (from x1,y1 to x2,y2)
            elif action.startswith("drag"):
                parts = action.split()
                if len(parts) >= 5:
                    x1, y1, x2, y2 = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                    try:
                        self.active_window.activate()
                        time.sleep(0.15)
                    except: pass
                    
                    # Convert relative to absolute
                    abs_x1 = self.active_window.left + x1
                    abs_y1 = self.active_window.top + y1
                    abs_x2 = self.active_window.left + x2
                    abs_y2 = self.active_window.top + y2
                    
                    print(f" -> Drag: ({abs_x1}, {abs_y1}) -> ({abs_x2}, {abs_y2})")
                    pyautogui.moveTo(abs_x1, abs_y1)
                    pyautogui.drag(abs_x2 - abs_x1, abs_y2 - abs_y1, duration=0.5)
            
            # Ej: "move 200, 300" (move mouse without clicking)
            elif action.startswith("move"):
                parts = action.replace(",", "").split()
                if len(parts) >= 3:
                    x, y = int(parts[1]), int(parts[2])
                    try:
                        self.active_window.activate()
                        time.sleep(0.1)
                    except: pass
                    
                    if x < self.active_window.width and y < self.active_window.height:
                        abs_x = self.active_window.left + x
                        abs_y = self.active_window.top + y
                    else:
                        abs_x, abs_y = x, y
                    
                    pyautogui.moveTo(abs_x, abs_y)
                
            # Ej: "wait" or "wait 3" (seconds)
            elif action.startswith("wait"):
                parts = action.split()
                seconds = int(parts[1]) if len(parts) > 1 else 2
                time.sleep(seconds)
                
            return "Success"
        except Exception as e:
            return f"Failed: {e}"

    def _capture_win32(self, hwnd):
        """High-precision capture using win32 API (handles occlusion)"""
        import win32gui, win32ui, win32con, ctypes
        from PIL import Image
        
        try:
            # Get window DC
            left, top, right, bot = win32gui.GetWindowRect(hwnd)
            w = right - left
            h = bot - top
            
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
            
            saveDC.SelectObject(saveBitMap)
            
            # PrintWindow is the magic for occluded windows
            # PW_RENDERFULLCONTENT = 2 (Win 8.1+)
            result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
            
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1)
            
            # Cleanup
            win32gui.ReleaseDC(hwnd, hwndDC)
            mfcDC.DeleteDC()
            saveDC.DeleteDC()
            win32gui.DeleteObject(saveBitMap.GetHandle())
            
            if result == 1:
                return img
            return None
        except Exception as e:
            print(f"[Win32 Capture] Failed: {e}")
            return None

    def capture_frame(self, save_log=True):
        """Captura la región de la ventana activa con alta precisión"""
        if not self.active_window or not ImageGrab:
            return None
            
        try:
            hwnd = self.active_window._hWnd
            
            # Try Precision Capture (Win32)
            img = self._capture_win32(hwnd)
            
            # Fallback to standard ImageGrab if win32 fails
            if not img:
                w = self.active_window
                bbox = (w.left, w.top, w.left + w.width, w.top + w.height)
                img = ImageGrab.grab(bbox=bbox)
            
            if not img: return None

            # Save optimized log version at 1/3 resolution
            if save_log:
                try:
                    captures_dir = self.base_path / "captures"
                    captures_dir.mkdir(exist_ok=True)
                    
                    new_w, new_h = img.width // 3, img.height // 3
                    img_small = img.resize((new_w, new_h))
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = captures_dir / f"frame_{timestamp}.jpg"
                    img_small.save(filename, "JPEG", quality=75)
                    
                    # Cleanup
                    all_captures = sorted(captures_dir.glob("frame_*.jpg"))
                    if len(all_captures) > 50:
                        for old_file in all_captures[:-50]:
                            old_file.unlink()
                except:
                    pass
            
            return img
        except Exception as e:
            print(f"Frame Capture Error: {e}")
            return None

    def run_cycle_step(self):
        """Un paso del ciclo de vida visual"""
        if not self.llm:
            return "No LLM attached"

        # 1. PERCEPCIÓN
        image = self.capture_frame()
        if not image:
            return "Capture failed"

        # Guardar frame para debug/memoria
        timestamp = datetime.now().strftime("%H-%M-%S")
        debug_dir = self.base_path / "core" / "memory" / "states" / "visual_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        # image.save(debug_dir / f"frame_{timestamp}.png") # Descomentar para debug

        # 2. PROCESAMIENTO MULTIMODAL
        # Convertir a Base64 para Ollama
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # 3. LLAMADA AL ROUTER (VISION ROLE)
        # Asumimos que self.llm es la instancia de ModelRouter
        prompt = "Describe what you see on the screen. Identify UI elements, text, and context."
        
        try:
            # route_request signature: task_type, prompt, system_prompt, context_messages, images
            # Check if self.llm has route_request (it should be the Router)
            if hasattr(self.llm, 'route_request'):
                response = self.llm.route_request(
                    task_type="visual",
                    prompt=prompt,
                    images=[img_str]
                )
                return response
            else:
                return "Router not connected properly."
        except Exception as e:
            return f"VLM Error: {e}"

