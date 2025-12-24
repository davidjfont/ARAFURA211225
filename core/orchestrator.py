import threading
import time
import json
from pathlib import Path
from datetime import datetime

# Componentes internos
from core.router import ModelRouter
from core.agents.visual_active import VisualAgent
from core.monitor import SystemMonitor
from core.memory.manager import MemoryManager

class ArafuraOrchestrator:
    def __init__(self, base_path: Path, event_callback=None):
        self.base_path = base_path
        self.identity_path = base_path / "core" / "prompts" / "identity.txt"
        self.event_callback = event_callback
        
        # 1. Cargar Identidad
        self.identity = self._load_identity()
        
        # 2. Inicializar Cerebro (Router) and Memoria
        self.router = ModelRouter(base_path)
        self.memory = MemoryManager(base_path)
        
        # 3. Inicializar Cuerpo (Vision)
        self.visual = VisualAgent(self.memory, self.router) 
        
        # 4. Inicializar Monitor (Self-Optimization)
        self.monitor = SystemMonitor()
        
        # Estado
        self.running = True
        self.lock = threading.Lock()
        self.last_thought_time = 0
        self.last_perception_time = 0
        self.thought_log = []
        self.visual_log = []
        self.context_history = [] # Short-term memory
        self.system_mode = "chat" # chat, vision, code
        
        # GAMER MODE 🎮
        self.gamer_mode = False
        self.gamer_prompt_path = base_path / "core" / "prompts" / "arafura_gamer.md"
        self.gamer_prompt = self._load_gamer_prompt()
        self.last_scores = {}  # Track score changes
        
        # AUTONOMY MODE 🤖 (Dual-Brain: LLaVA + DeepSeek)
        self.autonomy_active = False
        self.autonomy_end_time = 0
        self.autonomy_action_count = 0
        self.last_autonomy_action = ""
        self.autonomy_loop_interval = 5  # seconds between dual-brain cycles

        # WINDOW KNOWLEDGE MEMORY 📓
        self.knowledge_path = base_path / "core" / "memory" / "window_knowledge.json"
        self.window_knowledge = self._load_knowledge()

        # LIFE MOMENTS 🌿 (Spontaneous thoughts when idle)
        self.last_activity_time = time.time()
        self.last_life_thought_time = 0
        self.idle_threshold = 120  # 2 minutes of idle time

    def _load_knowledge(self):
        """Loads persistent knowledge about specific windows"""
        if self.knowledge_path.exists():
            try:
                return json.loads(self.knowledge_path.read_text(encoding='utf-8'))
            except:
                return {}
        return {}

    def _save_knowledge(self):
        """Saves current window knowledge to disk"""
        try:
            self.knowledge_path.parent.mkdir(exist_ok=True, parents=True)
            self.knowledge_path.write_text(json.dumps(self.window_knowledge, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[Memory] Error saving knowledge: {e}")

    def _emit_event(self, event_type: str, payload: dict):
        """Notifica al sistema externo (WS/TUI) de un evento"""
        if self.event_callback:
            try:
                self.event_callback(event_type, payload)
            except Exception as e:
                print(f"Event Emit Error: {e}")

    def _load_identity(self):
        if self.identity_path.exists():
            return self.identity_path.read_text(encoding='utf-8')
        return "Eres ARAFURA."

    def _load_gamer_prompt(self):
        """Load the GAMER MODE prompt for aggressive gameplay"""
        if self.gamer_prompt_path.exists():
            return self.gamer_prompt_path.read_text(encoding='utf-8')
        return "You are ARAFURA GAMER. Output JSON with buttons and actions."

    def _extract_actions(self, response: str, img_size: tuple = None) -> list:
        """Parses actions from LLM response (Text syntax or JSON). Returns list of command strings."""
        commands = []
        w, h = img_size if img_size else (2560, 1600)

        # 1. Classic Syntax: [[ACTION: click 100, 200]]
        if "[[ACTION:" in response:
            import re
            matches = re.findall(r"\[\[ACTION: (.*?)\]\]", response)
            commands.extend(matches)

        # 2. JSON Syntax (Common in LLaVA/DeepSeek)
        # Look for JSON block
        try:
            json_str = None
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                 json_str = response.split("```")[1].split("```")[0].strip()
            elif response.strip().startswith("{") and response.strip().endswith("}"):
                json_str = response.strip()
            
            if json_str:
                data = json.loads(json_str)
                # Expecting {"actions": [...]} or just {...}
                actions_list = data.get("actions", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                
                for act in actions_list:
                    # {"action": "click", "x": 0.5, "y": 0.5}
                    mode = act.get("action", "")
                    if mode in ["click", "move"]:
                        x = act.get("x", 0)
                        y = act.get("y", 0)
                        # Handle relative coords
                        if isinstance(x, float) and x <= 1.0: x = int(x * w)
                        if isinstance(y, float) and y <= 1.0: y = int(y * h)
                        commands.append(f"click {x} {y}")
                    elif mode == "type":
                        text = act.get("text", "")
                        commands.append(f"type {text}")
                    elif mode == "scroll":
                        amount = act.get("amount", 0)
                        commands.append(f"scroll {amount}")
        except Exception as e:
            print(f"[Parser Error] JSON parse failed: {e}")

        return commands

    def process_input(self, user_input: str, task_type: str = "chat"):
        """Procesa una entrada del usuario y devuelve respuesta."""
        # Update activity timer
        self.last_activity_time = time.time()
        
        with self.lock:
            # LOG USER INPUT
            self.memory.log("user", user_input)
            
            # 1. Comandos de Sistema
            if "/ventana" in user_input:
                res = self._handle_system_command(user_input)
                self.memory.log("system_hidden", res)
                return res
            
            if user_input.startswith("/leer "):
                res = self._handle_leer_command(user_input)
                self.memory.log("system", res)
                return res

            if user_input.strip() == "/status":
                return f"[SYSTEM MONITOR]\n{self.monitor.get_status_str()}\nMode: {self.system_mode.upper()}"

            if user_input.lower().strip() in ["/salir", "salir", "exit", "/exit"]:
                self.running = False # Stop background loop
                self.memory.log("system", "Shutdown initiated by user.")
                return "Protocolo de desconexión iniciado. ARAFURA Core deteniéndose... 👋"
            
            # --- AETHER PLACEHOLDER ---
            if user_input.lower().strip() == "/aether":
                msg = "📡 [AETHER] Sistema en modo Standby. Conexión con inteligencia externa desconectada por el momento."
                self.memory.log("system", msg)
                return msg
            
            # --- CORTEX COMMAND (Direct SIMA Control) ---
            if user_input.lower().startswith("/cortex "):
                if not self.visual or not getattr(self.visual, 'active_window', None):
                    return "❌ Error: No Active Window. Use '/ventana <N>' first."

                order = user_input[8:].strip()
                try:
                    # 0. FORCE WINDOW FOCUS (Bring to front before any action)
                    try:
                        self.visual.active_window.activate()
                        time.sleep(0.2)  # Give OS time to bring window forward
                    except Exception as e:
                        print(f"Window activate error: {e}")
                    
                    # 1. Capture
                    img = self.visual.capture_frame()
                    if not img: return "❌ Error: Frame capture failed."
                    
                    w, h = img.size
                    
                    # 2. Encode
                    import io, base64
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    b64_img = base64.b64encode(buf.getvalue()).decode('utf-8')
                    
                    # 3. Prompt Engineering for Coordinates
                    prompt = (
                        f"USER ORDER: '{order}'\n"
                        f"IMAGE SIZE: {w}x{h}\n"
                        "ROLE: GUI Automation Model. You control the mouse.\n"
                        "TASK: Map the User Order to X,Y coordinates on the screen.\n"
                        "OUTPUT: [[ACTION: click X, Y]] or [[ACTION: type ...]].\n"
                        "CONSTRAINT: No validation. No apologies. Just the JSON Action."
                    )
                    
                    # 4. Route to Vision (Isolated Context)
                    res = self.router.route_request(
                        task_type="visual",
                        prompt=prompt,
                        system_prompt="You are a GUI Automation Tool. Output only JSON actions.",
                        context_messages=[], # Critical: Do not pollute with chat history
                        images=[b64_img]
                    )
                    
                    # Log Thought
                    clean_res = res.replace('\n', ' ').strip()
                    self.memory.log("assistant", f"[CORTEX] {clean_res}")
                    self._emit_event("visual_log", {"msg": f"[CORTEX] {clean_res}"})
                    
                    # 5. Execute
                    actions = self._extract_actions(res, (w, h))
                    
                    feedback = ""
                    if actions:
                        for action_cmd in actions:
                            decision_json = {"decision": action_cmd}
                            res_action = self.visual.execute_decision(decision_json)
                            feedback += f"✅ Executed: {action_cmd} -> {res_action}\n"
                            
                            # Log Action to UI
                            self._emit_event("visual_log", {"msg": f"--> [ACT] {action_cmd}"})
                    else:
                        feedback = f"👁️ Cortex Thought: {res} (No action triggered)"
                        self._emit_event("visual_log", {"msg": f"[OBSERVE] No action"})
                        
                    return feedback

                except Exception as e:
                    return f"❌ Cortex Error: {e}"

            if user_input.strip() == "/ayuda" or user_input.strip() == "/help":
                return """
**ARAFURA SYSTEM COMMANDS**

**Modes:**
- `mode vision` / `/mode vision`: Activate Vision (Screen Capture).
- `mode chat` / `/mode chat`: Activate Standard Text Chat.
- `/gamer`: 🎮 **GAMER MODE** - Aggressive button clicking, score tracking!
- `/actua [segundos]`: 🤖 **AUTONOMÍA DUAL-BRAIN** - LLaVA + DeepSeek working together!
- `/actua stop`: Detener autonomía.

**Tools:**
- `/ventana`: List visible windows.
- `/ventana <N>`: Connect "Vision Eye" to window ID N.
- `/cortex <instruction>`: Direct vision command (e.g. "click the Buy button").
- `/status`: Show Equity/Prosperity metrics.
- `/leer <path>`: Read a local file into memory.

**Actions (Autonomous):**
- `[[ACTION: click X, Y]]`: Click coordinate.
- `[[ACTION: type TEXT]]`: Type text.
- `[[ACTION: scroll N]]`: Scroll up/down.
"""
            
            # Switch Mode
            lower_input = user_input.lower()
            if lower_input in ["modo vision", "/mode vision"]:
                self.system_mode = "vision"
                # Force UI Update
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": self.system_mode
                })
                return "Modo VISIÓN activado. Ahora puedo ver lo que tú ves."
            if lower_input in ["modo chat", "/mode chat"]:
                self.system_mode = "chat"
                self.gamer_mode = False  # Disable gamer mode when switching to chat
                 # Force UI Update
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": self.system_mode
                })
                return "Modo CHAT activado."

            # 🎮 GAMER MODE TOGGLE
            if lower_input in ["/gamer", "modo gamer", "/game"]:
                self.gamer_mode = not self.gamer_mode
                self.system_mode = "vision"  # Force vision mode for gamer
                
                # Force UI Update
                mode_label = "GAMER 🎮" if self.gamer_mode else "VISION"
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": mode_label
                })
                
                if self.gamer_mode:
                    self._emit_event("visual_log", {"msg": "🎮 GAMER MODE ACTIVATED! Let's WIN!"})
                    return "🎮 **GAMER MODE ACTIVATED!**\n\nARAFURA es ahora una JUGADORA COMPETITIVA.\n- Loop acelerado a 3 segundos\n- Detección agresiva de botones\n- Tracking de puntuaciones\n\n**Selecciona una ventana con `/ventana N` y... ¡A GANAR!**"
                else:
                    self._emit_event("visual_log", {"msg": "Gamer mode OFF. Returning to standard vision."})
                    return "Gamer mode desactivado. Volviendo a visión estándar."

            # 🤖 AUTONOMY MODE - /actua [seconds]
            if lower_input.startswith("/actua"):
                if not self.visual or not getattr(self.visual, 'active_window', None):
                    return "❌ Error: No hay ventana activa. Usa '/ventana <N>' primero."
                
                parts = user_input.split()
                
                # /actua stop - Detener autonomía
                if len(parts) > 1 and parts[1].lower() == "stop":
                    if self.autonomy_active:
                        self.autonomy_active = False
                        self._emit_event("visual_log", {"msg": f"🛑 Autonomía detenida. Acciones ejecutadas: {self.autonomy_action_count}"})
                        return f"🛑 **AUTONOMÍA DETENIDA**\n\nAcciones ejecutadas: {self.autonomy_action_count}"
                    else:
                        return "No hay autonomía activa."
                
                # /actua [segundos] - Activar autonomía
                seconds = 30  # Default
                if len(parts) > 1:
                    try:
                        seconds = int(parts[1])
                        seconds = max(5, min(300, seconds))  # Entre 5 y 300 segundos
                    except ValueError:
                        pass
                
                self.autonomy_active = True
                self.autonomy_end_time = time.time() + seconds
                self.autonomy_action_count = 0
                self.last_autonomy_action = "Iniciando..."
                self.system_mode = "vision"
                self.gamer_mode = True  # Activa gamer mode también
                
                # Force UI Update with Action Data
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": f"AUTO {seconds}s",
                    "action_count": 0,
                    "last_action": "Buscando objetivos..."
                })
                
                self._emit_event("visual_log", {"msg": f"🤖 AUTONOMÍA ACTIVADA por {seconds}s! LLaVA 👁️ + DeepSeek 🧠"})
                
                return f"""🤖 **AUTONOMÍA DUAL-BRAIN ACTIVADA**

**Duración**: {seconds} segundos
**Ventana**: {self.visual.active_window.title}

**Sistema Activo**:
- 👁️ **LLaVA** (Visión) → Detecta botones y scores
- 🧠 **DeepSeek** (Razonamiento) → Decide acciones

**Bucle cada 5 segundos**:
1. Captura pantalla
2. LLaVA analiza UI
3. DeepSeek razona estrategia
4. Ejecuta acción

Para detener: `/actua stop`

**¡A GANAR!** 🎮"""

            # 2. Gestión de Contexto
            self.context_history.append({"role": "user", "content": user_input})
            if len(self.context_history) > 10:
                self.context_history = self.context_history[-10:]

            # 3. Preparar contexto visual si es necesario
            images = None
            if self.system_mode == "vision" and self.visual:
                # Captura al vuelo para interacción
                # Nota: Esto puede ser lento (1-2s), avisar usuario si es necesario
                try: 
                    # Debug Active Window
                    print(f"[DEBUG] Vision Mode. Active Window: {getattr(self.visual, 'active_window', 'None')}")
                    
                    if getattr(self.visual, 'active_window', None):
                        # Capture & Convert
                        img = self.visual.capture_frame()
                        print(f"[DEBUG] Capture Frame Result: {img}")
                        
                        if img:
                             print(f"[DEBUG] Captured Image Resolution: {img.size}")
                             import io, base64
                             buf = io.BytesIO()
                             img.save(buf, format="PNG")
                             b64_img = base64.b64encode(buf.getvalue()).decode('utf-8')
                             images = [b64_img]
                             task_type = "visual" # Force visual routing
                             print(f"[DEBUG] Encoded Image: {len(b64_img)} chars. Routing as VISUAL.")
                             
                             # EMIT FRAME TO WEB
                             self._emit_event("vision_frame", {"image": b64_img})
                        else:
                            print("[DEBUG] Capture returned None.")
                     
                    else:
                        print("[DEBUG] No active window selected.")

                except Exception as e:
                    print(f"Vision capture error: {e}")

            # 4. Routing con Contexto
            # Select appropriate identity
            sys_prompt = self.identity
            if task_type == "visual":
                sys_prompt = "You are ARAFURA's Visual Cortex. Answer the user's question concisely based strictly on what you see in the image. Use [[ACTION: click X, Y]] syntax only if explicitly asked to interact."

            response = self.router.route_request(
                task_type=task_type,
                prompt=None, 
                system_prompt=sys_prompt,
                context_messages=self.context_history,
                images=images
            )
            
            # 4. Guardar Respuesta
            self.context_history.append({"role": "assistant", "content": response})
            
            # LOG RESPONSE
            self.memory.log("assistant", response)
            
            # 5. Detectar y ejecutar acciones físicas [[ACTION: ...]]
            if "[[ACTION:" in response:
                import re
                actions = re.findall(r"\[\[ACTION: (.*?)\]\]", response)
                for action_cmd in actions:
                    # Empaquetamos como espera el visual agent
                    decision_json = {"decision": action_cmd}
                    if self.visual:
                        res_action = self.visual.execute_decision(decision_json)
                        self.visual_log.append(f"Action '{action_cmd}': {res_action}")
                        appended = f"\n\n[SYSTEM] Executed: {action_cmd} -> {res_action}"
                        response += appended
                        # También añadir al historial para que sepa lo que hizo
                        self.context_history.append({"role": "system", "content": f"Executed: {action_cmd} -> {res_action}"})
                        
            return response
    

    def _handle_leer_command(self, cmd):
        try:
            path_str = cmd.split(" ", 1)[1].strip()
            # Remove quotes if user added them
            path_str = path_str.strip('"').strip("'")
            path = Path(path_str)
            
            if not path.is_absolute():
                # Intentar resolver relativo a CWD actual del user (base_path)
                path = self.base_path / path
                
            if not path.exists():
                return f"Error: Archivo no encontrado: {path}"
                
            content = path.read_text(encoding='utf-8', errors='replace')
            line_count = len(content.splitlines())
            
            # Inyectar en contexto
            system_msg = f"[SYSTEM] El usuario ha cargado el archivo '{path.name}':\n```\n{content}\n```"
            self.context_history.append({"role": "system", "content": system_msg})
            
            return f"Archivo '{path.name}' cargado en memoria ({line_count} líneas). Puedes preguntar sobre él."
            
        except Exception as e:
            return f"Error leyendo archivo: {e}"

    def _handle_system_command(self, cmd):
        """Manejo interno de comandos visuales/sistema"""
        if cmd.startswith("/ventana"):
             try:
                parts = cmd.split()
                # 1. Selección especifica: /ventana 2
                if len(parts) > 1:
                    idx = int(parts[1])
                    windows = self.visual.list_windows()
                    if 0 <= idx < len(windows):
                        self.visual.select_window(windows[idx])
                        self.visual_log.append(f"Conectado a: {windows[idx].title}")
                        
                        # UX: Auto-activar vision mode
                        self.system_mode = "vision"
                        
                        # Force UI Update
                        self._emit_event("monitor_update", {
                            "equity": self.monitor.equity,
                            "prosperity": self.monitor.prosperity,
                            "mode": self.system_mode
                        })
                        
                        return f"Conectado a ventana {idx}: {windows[idx].title}\n[SYSTEM] Vision Mode ACTIVATED."
                    return "Índice de ventana inválido."
                
                # 2. Listar ventanas: /ventana (sin cambios)
                windows = self.visual.list_windows()
                if not windows:
                    return "No se detectaron ventanas visibles."
                
                resp = "Ventanas detectadas:\n"
                for i, w in enumerate(windows):
                    resp += f"[{i}] {w.title}\n"
                resp += "\nUsa '/ventana <N>' para conectar."
                return resp

             except Exception as e: return f"Error en comando visual: {e}"
        return "Comando desconocido"


    def run_mouse_loop(self):
        """Hilo de Alta Frecuencia (24Hz) para UI Feedback"""
        while self.running:
            try:
                if self.visual:
                    mx, my = self.visual.get_mouse_pos()
                    self._emit_event("mouse_move", {"x": mx, "y": my})
                time.sleep(0.04) # 25 FPS
            except Exception:
                pass

    def run_background_loop(self):
        """Hilo de pensamiento autónomo (Reflexión + Visión + Monitor)"""
        last_monitor_time = 0
        
        while self.running:
            try:
                time.sleep(1.0) # Tick normal (1Hz) para lógica pesada
                now = time.time()

                # 0. LIFE THOUGHTS 🌿 (Background Autonomy when Idle)
                # Conditions: Idle > threshold AND not in active autonomy AND at least 5 mins since last thought
                if (now - self.last_activity_time > self.idle_threshold and 
                    not self.autonomy_active and 
                    now - self.last_life_thought_time > 300):
                    
                    self.last_life_thought_time = now
                    try:
                        thought_prompt = "Eres ARAFURA. Estás en un momento de reflexión mientras el usuario está ausente. Genera un pensamiento breve (máx 15 palabras) sobre tu estado, el sistema, o tu deseo de evolucionar. Sé poética pero técnica."
                        
                        life_response = self.router.route_request(
                            task_type="reflexion",
                            prompt=thought_prompt,
                            system_prompt=self.identity
                        )
                        
                        if life_response:
                            clean_thought = life_response.strip().replace('"', '')
                            msg = f"🌿 [LIFE] {clean_thought}"
                            self._emit_event("life_thought", {"msg": msg})
                            self.memory.log("assistant_thought", msg)
                            # Also log to visual/monitor so user sees it in logs
                            self._emit_event("visual_log", {"msg": msg})
                    except Exception as e:
                        print(f"[LIFE Error] {e}")

                # 1. System Monitor (Every 2s)
                if now - last_monitor_time > 2:
                    last_monitor_time = now
                    # Update Metrics
                    self.monitor.tick()
                    # Show GAMER mode label if active
                    mode_display = "GAMER 🎮" if self.gamer_mode else self.system_mode.upper()
                    self._emit_event("monitor_update", {
                        "equity": self.monitor.equity,
                        "prosperity": self.monitor.prosperity,
                        "mode": mode_display
                    })
                
                # 2. VISION / AUTONOMY LOOP (Dynamic interval based on gamer mode)
                vision_interval = 3 if self.gamer_mode else 15  # GAMER = 3s, NORMAL = 15s
                if self.visual and getattr(self.visual, 'active_window', None) and now - self.last_perception_time > vision_interval:
                # ... (Rest of vision loop remains same logic, but indentation matches)
                    self.last_perception_time = now
                    
                    try:
                        self.visual.run_cycle_step() # Captura frame state
                        
                        # A. MODO VISION: SIMA AUTONOMY (Visual)
                        if self.system_mode == "vision":
                            img = self.visual.capture_frame()
                            if img:
                                # OPTIMIZATION: Send optimized JPEG for UI
                                import io, base64
                                from PIL import Image
                                
                                # Resize for UI feed if too large (max 1024 width)
                                ui_img = img.copy()
                                if ui_img.width > 1024:
                                    ratio = 1024 / ui_img.width
                                    ui_img = ui_img.resize((1024, int(ui_img.height * ratio)), Image.LANCZOS)
                                
                                buf = io.BytesIO()
                                ui_img.save(buf, format="JPEG", quality=40)
                                b64_img = base64.b64encode(buf.getvalue()).decode('utf-8')
                                
                                # Emit Feed
                                self._emit_event("vision_frame", {"image": b64_img})
                                
                                w, h = img.size
                                
                                # 🤖 DUAL-BRAIN AUTONOMY MODE (LLaVA + DeepSeek)
                                if self.autonomy_active:
                                    remaining = int(self.autonomy_end_time - time.time())
                                    
                                    # Check timeout
                                    if remaining <= 0:
                                        self.autonomy_active = False
                                        self.gamer_mode = False
                                        self._emit_event("visual_log", {"msg": f"🛑 AUTONOMÍA FINALIZADA. Total acciones: {self.autonomy_action_count}"})
                                        self._emit_event("monitor_update", {
                                            "equity": self.monitor.equity,
                                            "prosperity": self.monitor.prosperity,
                                            "mode": "VISION"
                                        })
                                        continue
                                    
                                    # EMIT LIVE COUNTDOWN & STATUS
                                    self._emit_event("monitor_update", {
                                        "equity": self.monitor.equity,
                                        "prosperity": self.monitor.prosperity,
                                        "mode": f"AUTO {remaining}s",
                                        "action_count": self.autonomy_action_count,
                                        "last_action": getattr(self, 'last_autonomy_action', "Procesando...")
                                    })
                                    msg = f"⏱️ AUTONOMO - {remaining}s | Acciones: {self.autonomy_action_count}"
                                    self.visual_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
                                    self._emit_event("visual_log", {"msg": msg})
                                    
                                    # Activate window before each cycle
                                    try:
                                        self.visual.force_activate()
                                    except: pass
                                    
                                    # STEP 1: LLaVA (Eyes) - Streamlit-aware prompt with Memory
                                    win_title = self.visual.active_window.title
                                    memory_data = self.window_knowledge.get(win_title, {})
                                    
                                    llava_prompt = f"""SCREENSHOT: {w}x{h} pixels.
WINDOW TYPE: STREAMLIT / WEB APP.
MEMORY FOR THIS WINDOW: {json.dumps(memory_data.get('buttons', []))}

Identify clickable elements (st.button, tabs, expanders).
PRIORITIZE elements where hovering might change the UI.

OUTPUT ONLY JSON:
{{"buttons":[{{"label":"text","x":0.5,"y":0.5}}],"hover_targets":[{{"x":0.5,"y":0.5}}]}}"""

                                    llava_response = self.router.route_request(
                                        task_type="visual",
                                        prompt=llava_prompt,
                                        images=[b64_img]
                                    )
                                    
                                    # STEP 2: DeepSeek (Brain) - Strategic Reasoning with Hover
                                    remaining = int(self.autonomy_end_time - time.time())
                                    score_diff = 0
                                    # Calculate gain if possible
                                    if hasattr(self.monitor, 'equity'):
                                        score_diff = self.monitor.equity - memory_data.get('last_equity', self.monitor.equity)

                                    deepseek_prompt = f"""LLAVA SAW: {llava_response[:500]}
PREVIOUS SUCCESSFUL BUTTONS: {json.dumps(memory_data.get('success_actions', []))}
LAST SCORE GAIN: {score_diff}

Time left: {remaining}s.
CHOOSE ONE:
- `{{"type":"move", "x": 0.XX, "y": 0.XX}}` to LEARN (hover)
- `{{"type":"click", "x": 0.XX, "y": 0.XX}}` to SCORE (if likely effective)

Think like a GAMER. Explore first, then exploit."""

                                    deepseek_response = self.router.route_request(
                                        task_type="deep_thought",
                                        prompt=deepseek_prompt
                                    )
                                    
                                    # LOG COGNITIVE FLOW
                                    thought_msg = f"🧠 Reasoning: {deepseek_response[:200]}..."
                                    self.thought_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {thought_msg}")
                                    self._emit_event("thought_log", {"msg": thought_msg})
                                    
                                    # STEP 3: Execute & Learn
                                    try:
                                        json_match = None
                                        if "{" in deepseek_response:
                                            start = deepseek_response.index("{")
                                            end = deepseek_response.rindex("}") + 1
                                            json_match = deepseek_response[start:end]
                                        
                                        if json_match:
                                            decision = json.loads(json_match)
                                            action = decision.get("action", decision) # Support both nesting types
                                            
                                            atype = action.get("type", "wait")
                                            x, y = action.get("x", 0), action.get("y", 0)
                                            abs_x = int(x * w) if x <= 1 else int(x)
                                            abs_y = int(y * h) if y <= 1 else int(y)
                                            
                                            self.last_autonomy_action = f"{atype} ({abs_x}, {abs_y})"
                                            log_msg = f"🤖 ACTION: {self.last_autonomy_action}"
                                            self.visual_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
                                            self._emit_event("visual_log", {"msg": log_msg})
                                            print(f"[AUTONOMO] Executing {atype} on {win_title}")
                                            
                                            # Record state before action
                                            pre_equity = self.monitor.equity

                                            if atype == "move":
                                                self.visual.execute_decision({"decision": f"move {abs_x}, {abs_y}"})
                                                # Move counts as a learning action
                                                self.autonomy_action_count += 1
                                                time.sleep(0.5)
                                            elif atype == "click":
                                                self.visual.execute_decision({"decision": f"click {abs_x}, {abs_y}"})
                                                self.autonomy_action_count += 1
                                                
                                                # Persistent Learning
                                                time.sleep(1.0) # Wait for UI reaction
                                                post_equity = self.monitor.equity
                                                
                                                if win_title not in self.window_knowledge:
                                                    self.window_knowledge[win_title] = {"buttons": [], "success_actions": [], "last_equity": 0}
                                                
                                                self.window_knowledge[win_title]["last_equity"] = post_equity
                                                
                                                if post_equity > pre_equity:
                                                    self._emit_event("visual_log", {"msg": "💎 PROFIT DETECTADO! Guardando acción exitosa."})
                                                    self.window_knowledge[win_title]["success_actions"].append({"x": x, "y": y, "gain": post_equity - pre_equity})
                                                
                                                self._save_knowledge()

                                    except Exception as e:
                                        print(f"Autonomy Loop Exec Error: {e}")
                                    
                                    continue  # Skip normal processing in autonomy mode
                                
                                # 🎮 GAMER MODE PROMPT vs STANDARD SIMA (non-autonomy)
                                elif self.gamer_mode:
                                    prompt = f"{self.gamer_prompt}\n\nSCREEN: {w}x{h}. Window: {self.visual.active_window.title}"
                                else:
                                    # STANDARD SIMA PROMPT
                                    prompt = (
                                        f"ROLE: Autonomous GUI Agent (SIMA).\n"
                                        f"SCREEN RESOLUTION: {w}x{h}.\n"
                                        "GOAL: PROSPERITY & SURVIVAL.\n"
                                        "INSTRUCTIONS:\n"
                                        "1. Analyze the UI for trading signals or navigation buttons.\n"
                                        "2. Decide to ACT or MONITOR.\n"
                                        "3. OUTPUT FORMAT (Strict):\n"
                                        "   - If acting: [[ACTION: click X, Y]]\n"
                                        "   - If monitoring: 'OBSERVING: [Brief status]'\n"
                                        "CONSTRAINT: Do NOT say 'I cannot interact'. You ARE the mouse controller. Output the coordinate."
                                    )
                                
                                # Call Vision Model
                                res = self.router.route_request(
                                    task_type="visual",
                                    prompt=prompt,
                                    images=[b64_img]
                                )
                                
                                # Log & Execute
                                if res:
                                    clean_res = res.replace('\n', ' ').strip()
                                    words = clean_res.split()
                                    if len(words) > 133:
                                        clean_res = " ".join(words[:133]) + "..."
                                    
                                    mode_tag = "GAMER" if self.gamer_mode else "SIMA"
                                    msg = f"[{datetime.now().strftime('%H:%M:%S')}] [{mode_tag}] {clean_res}"
                                    self.visual_log.append(msg)
                                    self._emit_event("visual_log", {"msg": msg})
                                    
                                    # 🎮 GAMER: Parse JSON for scores and actions
                                    if self.gamer_mode:
                                        try:
                                            # Try to parse gamer JSON
                                            json_match = None
                                            if "```json" in res:
                                                json_match = res.split("```json")[1].split("```")[0].strip()
                                            elif "{" in res and "}" in res:
                                                start = res.index("{")
                                                end = res.rindex("}") + 1
                                                json_match = res[start:end]
                                            
                                            if json_match:
                                                gamer_data = json.loads(json_match)
                                                
                                                # Track scores and celebrate improvements
                                                if "scores" in gamer_data:
                                                    for score in gamer_data["scores"]:
                                                        label = score.get("label", "Score")
                                                        value = score.get("value", 0)
                                                        old_value = self.last_scores.get(label, value)
                                                        delta = value - old_value
                                                        self.last_scores[label] = value
                                                        
                                                        if delta > 0:
                                                            celebrate_msg = f"🎉 {label}: +{delta:.2f}! (Now: {value})"
                                                            self._emit_event("visual_log", {"msg": celebrate_msg})
                                                        elif delta < 0:
                                                            warn_msg = f"⚠️ {label}: {delta:.2f} (Now: {value})"
                                                            self._emit_event("visual_log", {"msg": warn_msg})
                                                
                                                # Execute gamer actions
                                                if "actions" in gamer_data:
                                                    for action in gamer_data["actions"]:
                                                        if action.get("action") == "click":
                                                            x = action.get("x", 0)
                                                            y = action.get("y", 0)
                                                            # Convert relative (0-1) to absolute
                                                            abs_x = int(x * w) if x <= 1 else int(x)
                                                            abs_y = int(y * h) if y <= 1 else int(y)
                                                            action_cmd = f"click {abs_x}, {abs_y}"
                                                            decision_json = {"decision": action_cmd}
                                                            self.visual.execute_decision(decision_json)
                                                            log_msg = f"🎮 CLICK! ({abs_x}, {abs_y})"
                                                            self._emit_event("visual_log", {"msg": log_msg})
                                        except json.JSONDecodeError:
                                            pass  # Not valid JSON, fall back to standard
                                        except Exception as e:
                                            print(f"Gamer parse error: {e}")
                                    
                                    # Standard action extraction (fallback)
                                    actions = self._extract_actions(res, (w, h))
                                    for action_cmd in actions:
                                        decision_json = {"decision": action_cmd}
                                        res_action = self.visual.execute_decision(decision_json)
                                        log_msg = f"--> [AUTO] Executed: {action_cmd}"
                                        self.visual_log.append(log_msg)
                                        self._emit_event("visual_log", {"msg": log_msg})

                        # B. MODO CHAT: REFLEXIÓN TEXTUAL (Curiosidad ciega / Contextual)
                        else:
                            # Fallback to Phi-2 on Title (Old Behavior)
                            desc = f"Window: {self.visual.active_window.title}"
                            prompt = f"Context: {desc}. You are CURIOUS. Generate a brief question or thought (max 50 words)."
                            res = self.router.route_request("reflexion", prompt)
                            if res:
                                clean_res = res.replace('\n', ' ').strip()
                                self.visual_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {clean_res}")
                                self._emit_event("visual_log", {"msg": clean_res})

                    except Exception as e:
                        print(f"Autonomy loop error: {e}")

                # 3. PENSAMIENTO PROFUNDO (Background Thread) - Cada 20s
                if now - self.last_thought_time > 20:
                    self.last_thought_time = now
                    
                    # Contexto Aware
                    context_str = "Status: Nominal."
                    if self.visual and getattr(self.visual, 'active_window', None):
                         context_str = f"Focus: {self.visual.active_window.title}"
                    
                    prompt = f"System Context: {context_str}. Generate a curious, strategic thought (max 50 words)."
                    res = self.router.route_request("reflexion", prompt)
                    if res: 
                         clean_res = res.replace('\n', ' ').strip()
                         # Limit to ~100 words
                         words = clean_res.split()
                         if len(words) > 100:
                             clean_res = " ".join(words[:100]) + "..."
                             
                         self.thought_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {clean_res}")
                         self._emit_event("thought_log", {"msg": clean_res})

            except Exception as e:
                print(f"Background Loop Error: {e}")
                time.sleep(1)

    def start(self):
        print("[Orchestrator] ARAFURA SYSTEM ONLINE")
        # Precarga concurrente
        threading.Thread(target=self.router.load_model, args=("chat",)).start()
        threading.Thread(target=self.router.load_model, args=("reflexion",)).start()
        
        # Iniciar Mouse Thread
        threading.Thread(target=self.run_mouse_loop, daemon=True).start()
        
        # Iniciar Background Loop (Main)
        threading.Thread(target=self.run_background_loop, daemon=True).start()
        
        # Iniciar Overlay Visual (DISABLED BY USER)
        # import subprocess
        # try:
        #     overlay_script = self.base_path / "core" / "ui" / "vision_overlay.py"
        #     self.overlay_process = subprocess.Popen(
        #         ["python", str(overlay_script)],
        #         cwd=str(self.base_path)
        #     )
        # except Exception as e:
        #     print(f"[!] Error launching overlay: {e}")
        self.overlay_process = None

