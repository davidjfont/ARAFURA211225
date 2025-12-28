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
from core.vision_pipeline import VisionPipeline
from core.memory_vector import VectorMemory
import pyautogui
from core.rag_manager import RAGManager
from core.local_ocr import LocalOCREngine

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
        self.visual.event_callback = self._emit_event # Connect callback
        self.vision_pipeline = VisionPipeline(fps=5) # 5 FPS is enough for intelligence
        
        # 3.1 Inicializar Sensor OCR Local (Tesseract)
        self.ocr_engine = LocalOCREngine()

        # NO iniciar threads aquí para evitar interferir con el foco del terminal inicial
        
        # 4. Inicializar Memoria Vectorial (Experiencias)
        self.vector_memory = VectorMemory(base_path)
        
        # 5. Inicializar Monitor (Self-Optimization)
        self.monitor = SystemMonitor()
        
        # 6. Inicializar Capa RAG Corporativa v5.0
        self.rag = RAGManager(base_path)
        
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
        self.autonomy_action_count = 0
        self.last_autonomy_action = ""
        self.autonomy_loop_interval = 5  # seconds between dual-brain cycles
        self.user_autonomy_prompt = ""  # Custom prompt for the current session

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
            
            # --- ARAFURA TRACKER STATUS ---
            if user_input.lower().strip() in ["/aether", "/pointer", "/tracker"]:
                msg = f"📡 [ARAFURA] Tracker activo en ({self.visual.ghost_cursor.x}, {self.visual.ghost_cursor.y}). Estado: {self.visual.ghost_cursor.state}"
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
                    
                    # 1. Double Capture: Global + Precision Crop
                    img_global = self.visual.capture_frame()
                    img_crop = self.visual.capture_cursor_crop(size=500)
                    
                    if not img_global: return "❌ Error: Global capture failed."
                    
                    # Encode both
                    import io, base64
                    def encode_img(img):
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        return base64.b64encode(buf.getvalue()).decode('utf-8')
                    
                    b64_global = encode_img(img_global)
                    b64_crop = encode_img(img_crop) if img_crop else None
                    
                    images = [b64_global]
                    if b64_crop: images.append(b64_crop)
                    
                    # 3. Prompt Engineering for Dual Vision
                    w, h = img_global.size
                    prompt = (
                        f"USER ORDER: '{order}'\n"
                        f"GLOBAL SCREEN: {w}x{h}\n"
                        "CONTEXT: You are provided with TWO images.\n"
                        "1. GLOBAL: Full view of the application.\n"
                        f"2. PRECISION: A 500x500 crop centered on the ARAFURA tracker at ({self.visual.ghost_cursor.x}, {self.visual.ghost_cursor.y}).\n\n"
                        "TASK: Use Global for navigation and Precision for reading/clicking.\n"
                        "OUTPUT: [[ACTION: click X, Y]] (normalized 0-1000) or [[ACTION: type ...]].\n"
                        "CONSTRAINT: Pure JSON action. No conversation."
                    )
                    
                    # 4. Route to Vision (Dual Context)
                    res = self.router.route_request(
                        task_type="visual",
                        prompt=prompt,
                        system_prompt="You are ARAFURA's Visual Cortex. Perform GUI automation.",
                        context_messages=[], 
                        images=images
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
            
            if user_input.lower().strip() == "/scan":
                # Start Spatial Scan in Background Thread
                threading.Thread(target=self.scan_screen_routine, daemon=True).start()
                return "🛰️ Iniciando Escaneo Espacial (Vision Gravity). Observa el log visual."
            
            if user_input.lower().strip() == "/ocr":
                # Start OCR Scan in Background Thread
                threading.Thread(target=self.run_ocr_scan, daemon=True).start()
                return "📖 Iniciando Escaneo OCR (Local Tesseract). Observa el log visual."

            # Switch Mode
            lower_input = user_input.lower()
            if lower_input in ["modo vision", "/mode vision"]:
                self.system_mode = "vision"
                # Force UI Update
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": self.system_mode,
                    "autonomy": self.autonomy_active,
                    "gamer": self.gamer_mode
                })
                return "Modo VISIÓN activado. Ahora puedo ver lo que tú ves."
            if lower_input in ["modo chat", "/mode chat"]:
                self.system_mode = "chat"
                self.gamer_mode = False  # Disable gamer mode when switching to chat
                 # Force UI Update
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": self.system_mode,
                    "autonomy": self.autonomy_active,
                    "gamer": self.gamer_mode
                })
                return "Modo CHAT activado."

            # 🎮 GAMER MODE TOGGLE
            if lower_input in ["/gamer", "modo gamer", "/game", "/mode gamer"]:
                self.gamer_mode = not self.gamer_mode
                self.system_mode = "vision"  # Force vision mode for gamer
                
                # Force UI Update
                mode_label = "GAMER 🎮" if self.gamer_mode else "VISION"
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": mode_label,
                    "autonomy": self.autonomy_active,
                    "gamer": self.gamer_mode
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
                        # Immediate UI Update
                        self._emit_event("monitor_update", {
                            "equity": self.monitor.equity,
                            "prosperity": self.monitor.prosperity,
                            "mode": self.system_mode.upper(),
                            "autonomy": False,
                            "gamer": self.gamer_mode
                        })
                        return f"🛑 **AUTONOMÍA DETENIDA**\n\nAcciones ejecutadas: {self.autonomy_action_count}"
                    else:
                        return "No hay autonomía activa."
                
                # /actua [segundos] [prompt opcional]
                seconds = 60  # Default 60s
                custom_prompt = ""
                
                parts = user_input.split()
                if len(parts) > 1:
                    # Try to parse seconds
                    try:
                        seconds = int(parts[1])
                        seconds = max(5, min(600, seconds))  # 5s to 10m
                        # If there are more parts, it's the prompt
                        if len(parts) > 2:
                            custom_prompt = " ".join(parts[2:])
                    except ValueError:
                        # First arg is not int, so it implies default seconds + prompt
                        custom_prompt = " ".join(parts[1:])
                
                self.autonomy_active = True
                self.autonomy_end_time = time.time() + seconds
                self.autonomy_action_count = 0
                self.last_autonomy_action = "Iniciando..."
                self.user_autonomy_prompt = custom_prompt
                
                self.system_mode = "vision"
                self.gamer_mode = False # Use Standard SIMA Mode (Action Gate)
                
                # AUTO-TRIGGER SPATIAL SCAN (GRAVITY PROTOCOL)
                threading.Thread(target=self.scan_screen_routine, daemon=True).start()
                
                # Force UI Update with Action Data
                self._emit_event("monitor_update", {
                    "equity": self.monitor.equity,
                    "prosperity": self.monitor.prosperity,
                    "mode": f"AUTO {seconds}s",
                    "autonomy": True,
                    "gamer": self.gamer_mode,
                    "action_count": 0,
                    "last_action": "Iniciando Escaneo Espacial..."
                })
                
                prompt_msg = f" | Tarea: {custom_prompt}" if custom_prompt else " | Tarea: Escaneo General"
                self._emit_event("visual_log", {"msg": f"🤖 AUTONOMÍA ACTIVADA ({seconds}s){prompt_msg}. Iniciando Gravity Scan..."})
                
                return f"""🤖 **AUTONOMÍA DUAL-BRAIN ACTIVADA**

**Duración**: {seconds} segundos
**Tarea**: {custom_prompt if custom_prompt else "Escaneo General & Oportunismo"}
**Ventana**: {self.visual.active_window.title}

**Protocolo de Inicio**:
1. 🛰️ **Gravity Scan** (500x500 Mapping) - EJECUTANDO AHORA
2. 👁️ **Análisis Semántico** (Action Gate)

**Action Gate (Safety)**:
Solo ejecutará acciones si tiene >75% confianza.
*Nota: Si definiste una tarea específica, ARAFURA priorizará la acción.*

Para detener: `/actua stop`"""

            # 2. Gestión de Contexto
            self.context_history.append({"role": "user", "content": user_input})
            if len(self.context_history) > 10:
                self.context_history = self.context_history[-10:]

            # 3. Preparar contexto visual y de memoria (RAG)
            images = None
            knowledge_context = ""
            
            # Query memory for relevance to current task/window
            win_title = self.visual.active_window.title if (self.visual and self.visual.active_window) else "Unknown"
            query_str = f"{user_input} (Window: {win_title})"
            experiences = self.vector_memory.query_experience(query_str, limit=3)
            if experiences:
                knowledge_context = "### RELEVANT PAST EXPERIENCES:\n"
                for exp in experiences:
                    img_info = f" (Has Image: {exp.get('image')})" if exp.get('image') else ""
                    knowledge_context += f"- [{exp.get('category')}] {exp.get('observation')} -> {exp.get('action')} -> {exp.get('outcome')}{img_info}\n"

            if self.system_mode == "vision" and self.visual:
                # Actualizar timer para evitar que el loop de fondo interfiera
                self.last_perception_time = time.time()
                try: 
                    if getattr(self.visual, 'active_window', None):
                        captured_img = self.visual.capture_frame()
                        if captured_img:
                             import io, base64
                             buf = io.BytesIO()
                             captured_img.save(buf, format="PNG")
                             b64_img = base64.b64encode(buf.getvalue()).decode('utf-8')
                             images = [b64_img]
                             task_type = "visual"
                             self._emit_event("vision_frame", {"image": b64_img})
                except Exception as e:
                    print(f"Vision capture error: {e}")

            # 4. Routing con Contexto, RAG y Gobernanza
            sys_prompt = self.identity
            
            # INYECTAR GOBERNANZA Y PRINCIPIOS (Always first for alignment)
            gov_context = self.rag.query("governance principles safety", limit=3)
            if gov_context:
                sys_prompt = f"{sys_prompt}\n\n{gov_context}"

            # QUERY RAG for Contextual Knowledge (per user input)
            rag_hits = self.rag.query(user_input, limit=2)
            if rag_hits:
                knowledge_context = f"{knowledge_context}\n\n{rag_hits}"

            if task_type == "visual":
                sys_prompt = (
                    "You are ARAFURA's Visual Cortex. Answer the user's question concisely based strictly on what you see.\n"
                    f"{knowledge_context}\n"
                    "GROUNDING PROTOCOL:\n"
                    "- Use normalized coordinates (0-1000, 0-1000) where (0,0) is Top-Left and (1000,1000) is Bottom-Right.\n"
                    "- Before proposing an action, DESCRIBE the target element clearly (text, color, position).\n"
                    "Use [[ACTION: command]] for physical tasks.\n"
                    "Use [[MEMORY: concise description]] to save the current visual frame as a long-term persistence record."
                )
            else:
                # Inject knowledge into standard chat reasoning
                if knowledge_context:
                    sys_prompt += f"\n\n{knowledge_context}"

            response = self.router.route_request(
                task_type=task_type,
                prompt=user_input, # Pass the actual user prompt
                system_prompt=sys_prompt,
                context_messages=self.context_history,
                images=images
            )
            
            # 5. Guardar Respuesta
            self.context_history.append({"role": "assistant", "content": response})
            self.memory.log("assistant", response)
            
            # 5. Detectar y ejecutar acciones físicas [[ACTION: ...]]
            if "[[ACTION:" in response:
                import re
                actions = re.findall(r"\[\[ACTION: (.*?)\]\]", response)
                confirm_lines = []
                
                # BUCLE DE IMPACTO: Capture pre-action state
                pre_frame_cv = self.vision_pipeline.get_current_cv() if self.vision_pipeline else None
                
                for action_cmd in actions:
                    decision_json = {"decision": action_cmd}
                    if self.visual:
                        res_action = self.visual.execute_decision(decision_json)
                        
                        # IMPACT VERIFICATION (Post-Action)
                        impact_msg = ""
                        if pre_frame_cv is not None and self.vision_pipeline:
                            time.sleep(0.5) # Wait for UI to react
                            has_impact, score = self.vision_pipeline.check_impact(pre_frame_cv)
                            impact_msg = f" (Impacto: {'SÍ' if has_impact else 'NO'} | Δ: {score:.4f})"
                            # Update reference for next action in sequence
                            pre_frame_cv = self.vision_pipeline.get_current_cv()

                        self.visual_log.append(f"Action '{action_cmd}': {res_action}{impact_msg}")
                        conf_msg = f"Executed: {action_cmd} -> {res_action}{impact_msg}"
                        confirm_lines.append(f"[SYSTEM] {conf_msg}")
                        self.context_history.append({"role": "system", "content": conf_msg})
                
                if confirm_lines:
                    response += "\n\n" + "\n".join(confirm_lines)
            
            # 6. NEURAL HIERARCHY: Detect and Process [[CORTEX: ...]] Queries
            if "[[CORTEX:" in response:
                import re
                cortex_queries = re.findall(r"\[\[CORTEX: (.*?)\]\]", response)
                for query in cortex_queries:
                    # Capture current context if images not already set
                    if not images and 'captured_img' in locals():
                        # Use already captured image from step 3
                        img_to_use = [b64_img]
                    elif not images:
                         # Force new capture if none exists
                         img = self.visual.capture_frame()
                         import io, base64
                         buf = io.BytesIO()
                         img.save(buf, format="PNG")
                         img_to_use = [base64.b64encode(buf.getvalue()).decode('utf-8')]
                    else:
                        img_to_use = images

                    # Call Visual Cortex (Multimodal) with GROUNDING
                    cortex_response = self.router.route_request(
                        task_type="visual",
                        prompt=query,
                        system_prompt=(
                            "You are ARAFURA's Visual Cortex specializing in TECHNICAL GROUNDING.\n"
                            "1. Identify the requested elements.\n"
                            "2. Provide coordinates in [X, Y] format (0-1000 scale).\n"
                            "3. Describe visual state (buttons, text, loading indicators).\n"
                            "Be precise and technical. Avoid vague descriptions like 'middle' or 'top'."
                        ),
                        images=img_to_use
                    )
                    
                    cortex_msg = f"[CORTEX RESPONSE] {cortex_response}"
                    self.context_history.append({"role": "system", "content": cortex_msg})
                    
                    # 7. Recursive Reasoning: Let the Brain (DeepSeek/Mistral) synthesize the cortex findings
                    final_synthesis = self.router.route_request(
                        task_type="chat",
                        prompt=f"El Cortex Visual informa: '{cortex_response}'. Integra esta observación en tu flujo de pensamiento y concluye:",
                        system_prompt=self.identity,
                        context_messages=self.context_history
                    )
                    
                    # Merge responses for the UI
                    response += f"\n\n⚙️ **CONSULTA AL CORTEX:** {query}\n👁️ **RESPUESTA CORTEX:** {cortex_response}\n\n{final_synthesis}"
                    self.context_history.append({"role": "assistant", "content": final_synthesis})

            # 8. Detectar y guardar Memorias Visuales [[MEMORY: ...]]
            if "[[MEMORY:" in response:
                import re
                memories = re.findall(r"\[\[MEMORY: (.*?)\]\]", response)
                for mem_text in memories:
                    # Save with current image if it exists
                    self.vector_memory.store_experience(
                        category="visual_persistance",
                        observation=mem_text,
                        action="Commit Memory",
                        outcome="Saved to long-term storage",
                        image_pil=captured_img if 'captured_img' in locals() else None
                    )
                    conf_msg = f"[MEMORY] Recordado: {mem_text}"
                    response += f"\n\n{conf_msg}"
                    self.context_history.append({"role": "system", "content": conf_msg})
                        
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
                        self.vision_pipeline.set_window(windows[idx]) # Sync new pipeline
                        self.visual_log.append(f"Conectado a: {windows[idx].title}")
                        
                        # UX: Auto-activar vision mode
                        self.system_mode = "vision"
                        
                        # Force UI Update
                        self._emit_event("monitor_update", {
                            "equity": self.monitor.equity,
                            "prosperity": self.monitor.prosperity,
                            "mode": self.system_mode
                        })
                        
                        return f"Conectado a ventana {idx}: {windows[idx].title}\n[SYSTEM] Vision Mode + Asynchronous Pipeline ACTIVATED."
                    return "Índice de ventana inválido."
                
                # 2. Listar ventanas: /ventana
                else:
                    windows = self.visual.list_windows()
                    if not windows:
                        return "No se detectaron ventanas visibles."
                    
                    resp = "Ventanas detectadas:\n"
                    for i, w in enumerate(windows):
                        resp += f"[{i}] {w.title}\n"
                    resp += "\nUsa '/ventana <N>' para conectar."
                    return resp

            except Exception as e:
                return f"Error en comando visual: {e}"
        
        elif cmd.startswith("/cortex"):
            # Manual trigger of visual cortex: /cortex [pregunta]
            parts = cmd.split(maxsplit=1)
            query = parts[1] if len(parts) > 1 else "Describe lo que ves en detalle técnico."
            
            # Capture and Route
            captured = self.visual.capture_frame()
            if not captured:
                return "Error: No se pudo capturar frame."
            
            import io, base64
            buf = io.BytesIO()
            captured.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            res = self.router.route_request(
                task_type="visual",
                prompt=query,
                images=[b64]
            )
            self._emit_event("vision_frame", {"image": b64})
            return f"🧠 **ANÁLISIS DE CORTEX:**\n{res}"

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
                    # Hierarchy: AUTO > GAMER > VISION > CHAT
                    if self.autonomy_active:
                        remaining = int(self.autonomy_end_time - now)
                        mode_display = f"AUTO {remaining}s"
                    elif self.gamer_mode:
                        mode_display = "GAMER 🎮"
                    else:
                        mode_display = self.system_mode.upper()

                    self._emit_event("monitor_update", {
                        "equity": self.monitor.equity,
                        "prosperity": self.monitor.prosperity,
                        "mode": mode_display,
                        "autonomy": self.autonomy_active,
                        "gamer": self.gamer_mode
                    })
                
                # 2. VISION / AUTONOMY LOOP (Dynamic interval based on gamer mode)
                vision_interval = 3 if self.gamer_mode else 15  # GAMER = 3s, NORMAL = 15s
                if self.visual and getattr(self.visual, 'active_window', None) and now - self.last_perception_time > vision_interval:
                # ... (Rest of vision loop remains same logic, but indentation matches)
                    self.last_perception_time = now
                    
                    try:
                        # self.visual.run_cycle_step() # Old method: synchronous capture
                        
                        # NEW: Use Asynchronous Pipeline
                        b64_img, changed = self.vision_pipeline.get_latest_frame(force=self.gamer_mode)
                        
                        if not b64_img:
                            continue # Screen hasn't changed enough to justify processing
                        
                        # 1.5 Precision Crop for High-Frequency Analysis
                        crop_img = self.visual.capture_cursor_crop(size=500)
                        def encode_pil(img):
                            import io, base64
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            return base64.b64encode(buf.getvalue()).decode('utf-8')
                        b64_crop = encode_pil(crop_img) if crop_img else None

                        # Emit Feed to UI
                        self._emit_event("vision_frame", {"image": b64_img})
                        
                        # Get frame size info (approximate or from pipeline)
                        # Pipeline currently encodes directly to b64, we can assume system res
                        w, h = 1920, 1080 # Default fallback
                        if self.visual.active_window:
                            w, h = self.visual.active_window.width, self.visual.active_window.height
                        
                        # EMIT CORE HEALTH v4.1
                        load = 10 if not self.autonomy_active else 85
                        trace = "#" + self.vector_memory.last_id[:6].upper() if hasattr(self.vector_memory, 'last_id') and self.vector_memory.last_id else "#EMPTY"
                        self._emit_event("nucleus_update", {
                            "load": load,
                            "sync": "ESTABLE",
                            "trace": trace,
                            "autonomy": self.autonomy_active,
                            "gamer": self.gamer_mode
                        })

                        if self.system_mode == "vision":
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
                                
                                # QUERY VECTOR MEMORY: Has I seen this before?
                                win_title = self.visual.active_window.title if self.visual.active_window else "Desconocida"
                                memory_data = self.window_knowledge.get(win_title, {})
                                past_experiences = self.vector_memory.query_experience(f"Ventana: {win_title} en Streamlit")
                                exp_context = json.dumps(past_experiences, ensure_ascii=False) if past_experiences else "No past history."

                                llava_prompt = f"""SCREENSHOT: {w}x{h} pixels.
WINDOW TYPE: STREAMLIT / WEB APP.
PAST EXPERIENCES: {exp_context}
MEMORY FOR THIS WINDOW: {json.dumps(memory_data.get('buttons', []))}

Identify clickable elements (st.button, tabs, expanders).
PRIORITIZE elements where hovering might change the UI.

OUTPUT ONLY JSON:
{{"buttons":[{{"label":"text","x":0.5,"y":0.5}}],"hover_targets":[{{"x":0.5,"y":0.5}}]}}"""

                                images = [b64_img]
                                if b64_crop: images.append(b64_crop)

                                llava_response = self.router.route_request(
                                    task_type="visual",
                                    prompt=llava_prompt,
                                    images=images
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
                                                # SAVE TO VECTOR MEMORY
                                                self.vector_memory.store_experience(
                                                    category="visual",
                                                    observation=f"Botón pulsado en {win_title} en ({x}, {y})",
                                                    action=f"click {x} {y}",
                                                    outcome=f"Profit Increase: {post_equity - pre_equity}"
                                                )
                                            
                                            self._save_knowledge()

                                except Exception as e:
                                    print(f"Autonomy Loop Exec Error: {e}")
                                
                                continue  # Skip normal processing in autonomy mode
                            
                            # 🎮 GAMER MODE PROMPT vs STANDARD SIMA (non-autonomy)
                            elif self.gamer_mode:
                                prompt = f"{self.gamer_prompt}\n\nSCREEN: {w}x{h}. Window: {self.visual.active_window.title if self.visual.active_window else 'None'}"
                            else:
                                # STANDARD SIMA PROMPT (COGNITIVE UNLOCK / ACTION GATE)
                                # This prompt explicitly authorizes DeepSeek to act.
                                
                                task_instruction = f"TASK: {self.user_autonomy_prompt}\n(PRIORITIZE EXECUTION OF THIS TASK)" if self.user_autonomy_prompt else "TASK: Scan for opportunities and maintain system health."
                                
                                prompt = (
                                    f"ROLE: Autonomous GUI Agent (SIMA).\n"
                                    f"SCREEN RESOLUTION: {w}x{h}.\n"
                                    f"{task_instruction}\n"
                                    "GOAL: PROSPERITY & SURVIVAL.\n"
                                    "\n"
                                    "*** ACTION GATE PROTOCOL - HIGH AUTONOMY ***\n"
                                    "You are AUTHORIZED to generate executable actions immediately if the task is clear.\n"
                                    "Bias for ACTION over observation when a specific task is active.\n"
                                    "\n"
                                    "OUTPUT FORMAT (Strict):\n"
                                    "ACTION:\n"
                                    "type: hover | click\n"
                                    "x: <screen_x>\n"
                                    "y: <screen_y>\n"
                                    "confidence: <0.0 - 1.0>\n"
                                    "\n"
                                    "Do not describe. Do not explain. DECIDE."
                                )
                            
                            # Call Vision Model
                            images = [b64_img]
                            if b64_crop: images.append(b64_crop)
                            
                            res = self.router.route_request(
                                task_type="visual",
                                prompt=prompt,
                                images=images
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
                                                        celebrate_msg = f"🎉 {label}: {delta:.2f}! (Now: {value})"
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
                            desc = f"Window: {self.visual.active_window.title if self.visual.active_window else 'None'}"
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
            except Exception as e:
                print(f"Background Loop Error: {e}")
                time.sleep(1)

    def scan_screen_routine(self):
        """
        ARAFURA v6.0 - Spatial Tile Scan (Gravity Protocol)
        Scans the screen in 500x500 increments to build a spatial map.
        """
        print("[Orchestrator] Initiating Gravity Spatial Scan (500x500)...")
        self._emit_event("visual_log", {"msg": "📡 INITIATING SPATIAL MAPPING (500px TILES)..."})
        
        # Load Gravity Prompt
        prompt_path = self.base_path / "core" / "prompts" / "gravity_scan.md"
        if not prompt_path.exists():
            print("[!] Gravity Prompt not found.")
            return

        gravity_prompt = prompt_path.read_text(encoding='utf-8')
        
        # Get Screen Size
        w, h = pyautogui.size()
        tile_size = 500
        
        spatial_memory = []
        
        # Grid Traversal (Row by Row)
        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                # Calculate BBox (ensure within bounds)
                x2 = min(x + tile_size, w)
                y2 = min(y + tile_size, h)
                bbox = (x, y, x2, y2)
                
                print(f"[Scan] Processing Tile: {bbox}")
                self._emit_event("visual_log", {"msg": f"👁️ Scanning Tile: ({x},{y}) -> ({x2},{y2})"})
                
                # 1. Capture High-Fidelity Crop
                b64_crop = self.vision_pipeline.get_region_crop(bbox)
                
                if b64_crop:
                    # 2. Analyze with Vision Model (Gravity)
                    # We use a specialized routing request for "mapping"
                    # Note: We append the tile coordinates to the prompt for context
                    context_prompt = f"{gravity_prompt}\n\nCURRENT TILE COORDINATES: {bbox}\nANALYZE THIS REGION."
                    
                    response = self.router.route_request("vision", context_prompt, image_b64=b64_crop)
                    
                    # 3. Store Result
                    if response:
                        tile_data = {
                            "bbox": bbox,
                            "analysis": response,
                            "timestamp": datetime.now().isoformat()
                        }
                        spatial_memory.append(tile_data)
                        
                        # Log success
                        log_msg = f"✅ Tile Mapped: {bbox}"
                        self.visual_log.append(log_msg)
                        self._emit_event("visual_log", {"msg": log_msg})
                
                # Small delay to prevent rate limits or visual overwhelmed
                time.sleep(0.5)
        
        print(f"[Orchestrator] Spatial Scan Complete. Mapped {len(spatial_memory)} tiles.")
        self._emit_event("visual_log", {"msg": f"🗺️ SPATIAL MAP COMPLETE ({len(spatial_memory)} Tiles). Ready for Action."})
        
        # Store in Memory (Vector/JSONL) - For now, just keep in transient memory
        # In a real impl, this would go to self.memory.save_spatial_map(spatial_memory)
        self.context_history.append({"type": "spatial_map", "data": spatial_memory})

    def run_ocr_scan(self):
        """
        Phase 7: Tile-Based OCR using Local Tesseract.
        Populates self.ocr_memory with text + global bbox.
        """
        if not self.ocr_engine.active:
             print("[OCR] Engine not active.")
             return

        print("[Orchestrator] Initiating OCR Subsystem Scan (Local Tesseract)...")
        self._emit_event("visual_log", {"msg": "📖 INITIATING OCR SCAN (Local Engine)..."})
        
        w, h = pyautogui.size()
        tile_size = 500
        
        self.ocr_memory = [] # Clear previous OCR
        
        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                x2 = min(x + tile_size, w)
                y2 = min(y + tile_size, h)
                bbox = (x, y, x2, y2)
                
                # Center calculation for Spatial Memory (User Request)
                center_x = x + (tile_size // 2)
                center_y = y + (tile_size // 2)
                
                # 1. Capture High-Res Tile DIRECTLY (Bypassing Pipeline for verification)
                try:
                    from PIL import ImageGrab
                    img_crop = ImageGrab.grab(bbox=bbox)
                    
                    # Debug Save
                    if x == 0 and y == 0:
                        img_crop.save("debug_ocr_live.png")
                        print("📸 [DEBUG] Saved debug_ocr_live.png (Direct Capture)")

                    # Convert to B64 for Engine
                    buffer = io.BytesIO()
                    img_crop.save(buffer, format="PNG")
                    b64_crop = base64.b64encode(buffer.getvalue()).decode('utf-8')
                except Exception as e:
                    print(f"⚠️ [OCR] Capture Failed: {e}")
                    b64_crop = None
                
                if b64_crop:
                    # Clearer Log: Tile Index + Center
                    t_row, t_col = y // tile_size, x // tile_size
                    t_row, t_col = y // tile_size, x // tile_size
                    self._emit_event("visual_log", {
                        "msg": f"📖 OCR Reading Tile [{t_row},{t_col}] (Center: {center_x},{center_y})..."
                    })
                    
                    # 2. Local Analysis (Fast) using configured Language (spa+eng)
                    ocr_results = self.ocr_engine.analyze_image_b64(b64_crop)
                    
                    if ocr_results:
                        # 3. Store with normalized global coordinates
                        tile_entry = {
                            "tile_index": [t_row, t_col],
                            "center": [center_x, center_y],
                            "bbox": bbox,
                            "ocr": []
                        }
                        
                        for item in ocr_results:
                            # Local bbox is relative to tile (0,0 is tile top-left)
                            # Global X = tile_x + item_x1
                            
                            local_bbox = item.get("bbox", [0,0,0,0])
                            
                            gx1 = x + local_bbox[0]
                            gy1 = y + local_bbox[1]
                            gx2 = x + local_bbox[2]
                            gy2 = y + local_bbox[3]
                            
                            item["global_bbox"] = [gx1, gy1, gx2, gy2]
                            tile_entry["ocr"].append(item)
                            
                            if item.get("confidence", 0) > 0.6:
                                print(f"[OCR] Detected: '{item.get('text')}' at {item['global_bbox']}")
                        
                        if tile_entry["ocr"]:
                            self.ocr_memory.append(tile_entry)
                            
                            # Show sample words for verification
                            sample_text = ", ".join([item['text'] for item in tile_entry["ocr"][:3]])
                            msg = f"📝 OCR Tile ({x},{y}): Found {len(tile_entry['ocr'])} items: [{sample_text}...]"
                            self._emit_event("visual_log", {"msg": msg})
            
            # Allow UI to breathe
            time.sleep(0.1)
                        
        self._emit_event("visual_log", {"msg": f"✅ OCR COMPLETE. Indexing {len(self.ocr_memory)} tiles."})

    def start(self):
        print("[Orchestrator] ARAFURA SYSTEM ONLINE")
        
        # Iniciar Sistemas Perceptuales (Visión + Puntero)
        self.vision_pipeline.start()
        self.visual.start_ghost_cursor()
        
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

