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

class SystemState:
    """Formalizes ARAFURA's cognitive and operational state."""
    """Formalizes ARAFURA's cognitive and operational state."""
    def __init__(self, persistence_path: Path = None):
        self.lock = threading.Lock()
        self.persistence_path = persistence_path
        
        # State Variables
        self.power_level = 5.0
        self.perception_freq = 1.0 # Hz (base)
        self.aggressiveness = 0.5 # 0-1
        self.autonomy_active = False
        self.gamer_mode = False
        self.hitl_paused = False
        self.interrupt_signal = threading.Event()
        self.mood = "NOMINAL" # PERSISTENT EMOTIONAL STATE
        self.strategy = "OBSERVATION" # ACTIVE OPERATIONAL STRATEGY
        self.active_incident = None # TRACK CURRENT ISSUE
        self.action_budget = {"tokens": 5, "last_refill": time.time(), "rate": 0.5}
        self.cognitive_history = [] # Trace of internal state transitions

        # Load if path exists
        if self.persistence_path and self.persistence_path.exists():
            self.load()

    def save(self):
        """Persists cognitive state to JSON."""
        if not self.persistence_path: return
        with self.lock:
            try:
                data = {
                    "power_level": self.power_level,
                    "mood": self.mood,
                    "strategy": self.strategy,
                    "gamer_mode": self.gamer_mode,
                    "autonomy_active": self.autonomy_active,
                    "last_updated": time.time()
                }
                self.persistence_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            except Exception as e:
                print(f"⚠️ [State] Save Error: {e}")

    def load(self):
        """Loads cognitive state from JSON."""
        if not self.persistence_path: return
        with self.lock:
            try:
                data = json.loads(self.persistence_path.read_text(encoding='utf-8'))
                self.power_level = data.get("power_level", 5.0)
                self.mood = data.get("mood", "NOMINAL")
                self.strategy = data.get("strategy", "OBSERVATION")
                self.gamer_mode = data.get("gamer_mode", False)
                # Note: We do NOT persist autonomy_active to avoid auto-start loop safety risks
            except Exception as e:
                print(f"⚠️ [State] Load Error: {e}")

class ArafuraOrchestrator:
    def __init__(self, base_path: Path, event_callback=None):
        self.base_path = base_path
        self.identity_path = base_path / "core" / "prompts" / "identity.txt"
        self.event_callback = event_callback
        
        # 1. Cargar Identidad
        self.identity = self._load_identity()
        self.perception_lock = threading.Lock() # Resource Arbiter for OCR/Vision
        
        # 2. Inicializar Cerebro (Router) and Memoria
        self.router = ModelRouter(base_path)
        self.memory = MemoryManager(base_path)
        
        # 3. Inicializar Cuerpo (Vision)
        self.visual = VisualAgent(self.memory, self.router) 
        self.visual.event_callback = self._emit_event # Connect callback
        # Pass perception_lock via property injection later, or re-init here if lock existed.
        # But lock is defined LATER in this init. Let's move lock init UP or pass it here.
        # simpler: define lock earlier.
        self.vision_pipeline = VisionPipeline(fps=5, capture_lock=self.perception_lock) # 5 FPS is enough for intelligence
        
        # 3.1 Inicializar Sensor OCR Local (Tesseract)
        self.ocr_engine = LocalOCREngine()

        # NO iniciar threads aquí para evitar interferir con el foco del terminal inicial
        
        # 4. Inicializar Memoria Vectorial (Experiencias)
        self.vector_memory = VectorMemory(base_path)
        
        # 5. Inicializar Monitor (Self-Optimization)
        self.monitor = SystemMonitor()
        
        # 6. Inicializar Capa RAG Corporativa v5.0
        self.rag = RAGManager(base_path)
        
        # Estado Holístico (Decoupled Architecture)
        state_path = base_path / "core" / "memory" / "cognitive_state.json"
        self.state = SystemState(persistence_path=state_path)
        self.running = True
        self.lock = threading.Lock()
        
        self.last_thought_time = 0
        self.last_perception_time = 0
        self.thought_log = []
        self.visual_log = []
        self.context_history = [] 
        self.system_mode = "chat" 
        
        # GAMER METADATA
        self.gamer_prompt_path = base_path / "core" / "prompts" / "arafura_gamer.md"
        self.gamer_prompt = self._load_gamer_prompt()
        self.last_scores = {}  
        
        # AUTONOMY METADATA
        self.autonomy_end_time = 0
        self.autonomy_action_count = 0
        self.last_autonomy_action = ""
        self.autonomy_loop_interval = 5  
        self.user_autonomy_prompt = ""  

        # WINDOW KNOWLEDGE MEMORY 📓
        self.knowledge_path = base_path / "core" / "memory" / "window_knowledge.json"
        self.window_knowledge = self._load_knowledge()

        # LIFE MOMENTS 🌿
        self.last_activity_time = time.time()
        self.last_life_thought_time = 0
        self.idle_threshold = 120  

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
        """Carga la identidad base e inyecta metadatos temporales (Día de Persistencia)"""
        base_identity = ""
        if self.identity_path.exists():
            base_identity = self.identity_path.read_text(encoding='utf-8')
        else:
            base_identity = "Eres ARAFURA."

        # Cargar metadatos de creación desde arafura_identity.json (Raíz)
        json_identity_path = self.base_path / "arafura_identity.json"
        persistence_info = ""
        
        try:
            if json_identity_path.exists():
                data = json.loads(json_identity_path.read_text(encoding='utf-8'))
                created_date_str = data.get("entity", {}).get("created", "2025-12-21")
                created_date = datetime.strptime(created_date_str, "%Y-%m-%d")
                now = datetime.now()
                delta = now - created_date
                persistence_day = delta.days + 1 # El día de creación es el día 1
                
                persistence_info = (
                    f"\n\n[CONTEXTO TEMPORAL]\n"
                    f"- Fecha Actual: {now.strftime('%Y-%m-%d')}\n"
                    f"- Fecha de Nacimiento: {created_date_str}\n"
                    f"- DÍA DE PERSISTENCIA: {persistence_day}\n"
                )
        except Exception as e:
            print(f"[Orchestrator] Error calculando persistencia: {e}")

        return base_identity + persistence_info

    def _load_gamer_prompt(self):
        """Load the GAMER MODE prompt for aggressive gameplay"""
        if self.gamer_prompt_path.exists():
            return self.gamer_prompt_path.read_text(encoding='utf-8')
        return "You are ARAFURA GAMER. Output JSON with buttons and actions."

    def _extract_actions(self, response: str, img_size: tuple = None) -> list:
        """Parses actions from LLM response (Text syntax or JSON). Returns list of command strings."""
        commands = []
        w, h = img_size if img_size else (2560, 1600)

        # 0. Limpieza de bloques de pensamiento (DeepSeek R1 / Reasoning models)
        if "<think>" in response:
            import re
            response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

        # 1. Classic Syntax: [[ACTION: click 100, 200]]
        if "[[ACTION:" in response:
            import re
            matches = re.findall(r"\[\[ACTION: (.*?)\]\]", response)
            commands.extend(matches)

        # 2. JSON Syntax (Common in LLaVA/DeepSeek)
        try:
            json_str = None
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response and "}" in response:
                # Find the largest JSON-like structure
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
            
            if json_str:
                data = json.loads(json_str)
                # Normalización: puede venir como {"actions": []}, {"action": ...}, o una lista
                actions_list = []
                if isinstance(data, dict):
                    if "actions" in data: actions_list = data["actions"]
                    elif "action" in data: actions_list = [data]
                elif isinstance(data, list):
                    actions_list = data

                for act in actions_list:
                    if not isinstance(act, dict): continue
                    mode = act.get("action", act.get("type", ""))
                    if mode in ["click", "move"]:
                        x = act.get("x", 0)
                        y = act.get("y", 0)
                        # Handle relative coords
                        if isinstance(x, float) and x <= 1.0: x = int(x * w)
                        if isinstance(y, float) and y <= 1.0: y = int(y * h)
                        commands.append(f"{mode} {x} {y}")
                    elif mode == "type":
                        text = act.get("text", "")
                        commands.append(f"type {text}")
                    elif mode == "scroll":
                        amount = act.get("amount", 0)
                        commands.append(f"scroll {amount}")
        except Exception as e:
            msg = f"⚠️ ACTION PARSE ERROR: {str(e)}"
            self._emit_event("visual_log", {"msg": msg})
            self.memory.log("system_error", msg)

        return commands

    def _check_system_commands(self, user_input: str):
        """Maneja los comandos de sistema. Devuelve la respuesta si es un comando, else None."""
        lower_input = user_input.lower().strip()
        
        # 1. Comandos de Sistema Básicos
        if user_input.startswith("/ventana"):
            res = self._handle_system_command(user_input)
            self.memory.log("system_hidden", res)
            return res
        
        if user_input.startswith("/leer "):
            res = self._handle_leer_command(user_input)
            self.memory.log("system", res)
            return res

        if lower_input == "/status":
            return f"[SYSTEM MONITOR]\n{self.monitor.get_status_str()}\nMode: {self.system_mode.upper()}"

        if lower_input in ["/salir", "salir", "exit", "/exit"]:
            self.running = False
            self.memory.log("system", "Shutdown initiated by user.")
            return "Protocolo de desconexión iniciado. ARAFURA Core deteniéndose... 👋"
        
        if lower_input in ["/aether", "/pointer", "/tracker"]:
            msg = f"📡 [ARAFURA] Tracker activo en ({self.visual.ghost_cursor.x}, {self.visual.ghost_cursor.y}). Estado: {self.visual.ghost_cursor.state}"
            self.memory.log("system", msg)
            return msg
        
        if lower_input.startswith("/cortex "):
            return self._handle_cortex_execution(user_input)

        if lower_input in ["/ayuda", "/help"]:
            return self._get_help_text()
        
        if lower_input == "/scan":
            threading.Thread(target=self.scan_screen_routine, daemon=True).start()
            return "🛰️ Iniciando Escaneo Espacial (Vision Gravity). Observa el log visual."
        
        if lower_input == "/ocr":
            threading.Thread(target=self.run_ocr_scan, daemon=True).start()
            return "📖 Iniciando Escaneo OCR (Local Tesseract). Observa el log visual."

        # 2. Cambios de Modo y Autonomía
        if lower_input in ["modo vision", "/mode vision"]:
            self.system_mode = "vision"
            self._update_monitor_ui()
            return "Modo VISIÓN activado. Ahora puedo ver lo que tú ves."
            
        if lower_input in ["modo chat", "/mode chat"]:
            self.system_mode = "chat"
            self.state.gamer_mode = False
            self.state.save()
            self._update_monitor_ui()
            return "Modo CHAT activado."

        if lower_input in ["/gamer", "modo gamer", "/game", "/mode gamer"]:
            self.state.gamer_mode = not self.state.gamer_mode
            self.state.save()
            self.system_mode = "vision" if self.state.gamer_mode else self.system_mode
            self.last_perception_time = 0 # Forzar visual inmediata
            self._update_monitor_ui()
            if self.state.gamer_mode:
                self._emit_event("visual_log", {"msg": "🎮 GAMER MODE ACTIVATED! Let's WIN!"})
                return "🎮 **GAMER MODE ACTIVATED!**\n\nARAFURA es ahora una JUGADORA COMPETITIVA."
            return "Gamer mode desactivado."

        if lower_input.startswith("/actua"):
            return self._handle_actua_command(user_input)

        return None

    def _update_monitor_ui(self):
        """Helper to sync UI state"""
        self._emit_event("monitor_update", {
            "equity": self.monitor.equity,
            "prosperity": self.monitor.prosperity,
            "mode": self.system_mode.upper(),
            "autonomy": self.state.autonomy_active,
            "gamer": self.state.gamer_mode
        })

    def _handle_cortex_execution(self, user_input):
        if not self.visual or not getattr(self.visual, 'active_window', None):
            return "❌ Error: No Active Window. Use '/ventana <N>' first."
        order = user_input[8:].strip()
        # ... Resto de la lógica de cortex (la mantendré en process_input o la moveré aquí)
        # Por brevedad y para no romper el archivo, moveré el bloque entero aquí.
        try:
            self.visual.active_window.activate()
            time.sleep(0.2)
            img_global = self.visual.capture_frame()
            img_crop = self.visual.capture_cursor_crop(size=500)
            if not img_global: return "❌ Error: Global capture failed."
            import io, base64
            def encode_img(img):
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode('utf-8')
            b64_global = encode_img(img_global)
            b64_crop = encode_img(img_crop) if img_crop else None
            images = [b64_global]
            if b64_crop: images.append(b64_crop)
            w, h = img_global.size
            prompt = (f"USER ORDER: '{order}'\nGLOBAL SCREEN: {w}x{h}\nCONTEXT: Dual images.\nTASK: Action Logic.")
            res = self.router.route_request(task_type="visual", prompt=prompt, images=images)
            actions = self._extract_actions(res, (w, h))
            feedback = ""
            for action_cmd in actions:
                res_action = self.visual.execute_decision({"decision": action_cmd})
                feedback += f"✅ Executed: {action_cmd} -> {res_action}\n"
            return feedback if feedback else f"👁️ Cortex Thought: {res}"
        except Exception as e:
            return f"❌ Cortex Error: {e}"

    def _handle_actua_command(self, user_input):
        if not self.visual or not getattr(self.visual, 'active_window', None):
            return "❌ Error: No hay ventana activa. Usa '/ventana <N>' primero."
        parts = user_input.split()
        if len(parts) > 1 and parts[1].lower() == "stop":
            self.state.autonomy_active = False
            self.system_mode = "chat"
            self.state.interrupt_signal.set()
            self._emit_event("visual_log", {"msg": "🛑 EMERGENCY STOP: Autonomy & Thread Interrupt."})
            self._update_monitor_ui()
            return f"🛑 **AUTONOMÍA DETENIDA**"
        
        # 1. Configurar Tiempos
        seconds = 60
        if len(parts) > 1:
            try: seconds = int(parts[1])
            except: pass
        
        # 2. Activar Motores
        self.state.autonomy_active = True
        self.autonomy_end_time = time.time() + seconds
        self.autonomy_action_count = 0
        self.system_mode = "vision"
        self.last_perception_time = 0 # Forzar visual inmediata
        
        # 3. Lanzar Escaneo Inicial (Mejora la precision al arrancar)
        threading.Thread(target=self.scan_screen_routine, daemon=True).start()
        
        self._update_monitor_ui()
        return f"🤖 **AUTONOMÍA ACTIVADA ({seconds}s)**\n[SYSTEM] Vision Mode + Spatial Mapping INITIATED."

    def _get_help_text(self):
        return """**ARAFURA SYSTEM COMMANDS**\n... (Ayuda corta) ..."""

    def process_stream(self, user_input: str, task_type: str = "chat"):
        """Versión generatriz de process_input para streaming de pensamientos"""
        self.last_activity_time = time.time()
        
        # 0. Verificar Comandos Primero
        cmd_res = self._check_system_commands(user_input)
        if cmd_res:
            yield cmd_res
            return

        # LOG USER INPUT (Normal flowing message)
        self.memory.log("user", user_input)
        self.context_history.append({"role": "user", "content": user_input})
        if len(self.context_history) > 10: self.context_history = self.context_history[-10:]

        # 1. Preparar contexto (Vision + RAG)
        images = None
        knowledge_context = ""
        rag_hits = self.rag.query(user_input, limit=2)
        if rag_hits: knowledge_context += f"\n\n### KNOWLEDGE:\n{rag_hits}"
        
        gov_hits = self.rag.query("governance principles", limit=2)
        if gov_hits: knowledge_context += f"\n\n### GOVERNANCE:\n{gov_hits}"

        sys_prompt = f"{self.identity}\n{knowledge_context}"

        if self.state.gamer_mode:
             sys_prompt += f"\n\n{self.gamer_prompt}"
        
        if self.system_mode == "vision" and self.visual:
            if not getattr(self.visual, 'active_window', None):
                yield "❌ **VISION ERROR**: No active window selected. Use `/ventana` to list and `/ventana <N>` to select target."
                return

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
                         
                         # Precision context for stream
                         sys_prompt = (
                            "You are ARAFURA's Visual Cortex. Answer questions concisely based strictly on current vision.\n"
                            "GROUNDING: Use [X, Y] (0-1000) for positions. Describe elements before acting."
                         )
            except Exception as e:
                print(f"Stream vision capture error: {e}")

        full_response = ""
        is_thinking = False
        
        try:
            self.state.interrupt_signal.clear() # Reset on new request
            for token in self.router.stream_request(
                task_type=task_type,
                prompt=user_input,
                system_prompt=sys_prompt,
                context_messages=self.context_history,
                images=images
            ):
                if self.state.interrupt_signal.is_set():
                    yield "\n\n[INTRUPCIÓN: Operación cancelada por el usuario.]"
                    break
                if "<think>" in token: is_thinking = True
                self._emit_event("thought_stream", {"token": token, "is_thinking": is_thinking})
                if "</think>" in token: is_thinking = False
                full_response += token
                yield token
                
            # 1.1 Resume from HITL if user responds
            if self.state.hitl_paused:
                self.state.hitl_paused = False
                self._emit_event("visual_log", {"msg": "▶️ Resuming from HITL via chat input."})

            # 2. Final Logic (Post-Stream)
            final_response = self._finalize_response(full_response, regions if 'regions' in locals() else images)
            
            # Since the generator yielded the parts, the caller might only get parts.
            # But api.py joins them. To support [[INTERNAL]] logic, we check if it changed.
            if len(final_response) > len(full_response):
                extra = final_response[len(full_response):]
                yield extra
        except Exception as e:
            yield f"Error en stream: {e}"

    def process_input(self, user_input: str, task_type: str = "chat"):
        """Procesa una entrada del usuario y devuelve respuesta (Legacy/Sync)."""
        self.last_activity_time = time.time()
        
        with self.lock:
            # 0. Verificar Comandos
            cmd_res = self._check_system_commands(user_input)
            if cmd_res:
                return cmd_res

            # LOG USER INPUT
            self.memory.log("user", user_input)
            
            # (Resto de la lógica de procesamiento normal...)
            # Como he movido los comandos a _check_system_commands, 
            # puedo limpiar mucho process_input.

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

            # 4. Contexto Adicional (RAG + Gobernanza)
            knowledge_context = ""
            rag_hits = self.rag.query(user_input, limit=2)
            if rag_hits: knowledge_context += f"\n\n### KNOWLEDGE:\n{rag_hits}"
            
            gov_hits = self.rag.query("governance principles", limit=2)
            if gov_hits: knowledge_context += f"\n\n### GOVERNANCE:\n{gov_hits}"

            sys_prompt = f"{self.identity}\n{knowledge_context}"

            if task_type == "visual":
                sys_prompt += "\n\nYou are ARAFURA's Visual Cortex. Answer concisely based on vision. Use normalized coordinates [X, Y] (0-1000)."

            response = self.router.route_request(
                task_type=task_type,
                prompt=user_input,
                system_prompt=sys_prompt,
                context_messages=self.context_history,
                images=images
            )
            
            # 5. Finalize with Multimodal Logic & Automation
            final_response = self._finalize_response(response, images if images else (captured_img if 'captured_img' in locals() else None))
            return final_response

    def _finalize_response(self, response: str, visual_context=None):
        """Calculates actions, cortex queries, and memories from LLM response."""
        if not response or not response.strip():
            return "ARAFURA está analizando el contexto visual, pero la respuesta es inconclusa. ¿Podrías ser más específica?"

        # 0. Thinking cleanup
        content = response
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # 1. Store Assistant History
        self.context_history.append({"role": "assistant", "content": response})
        self.memory.log("assistant", response)

        # 2. Extract and Execute Actions [[ACTION: ...]]
        import re
        actions = re.findall(r"\[\[ACTION: (.*?)\]\]", content)
        for action_cmd in actions:
            decision_json = {"decision": action_cmd}
            if self.visual:
                res_action = self.visual.execute_decision(decision_json)
                msg = f"[SYSTEM] Executed: {action_cmd} -> {res_action}"
                self.visual_log.append(msg)
                self._emit_event("visual_log", {"msg": msg})

        # 3. Handle Cortex Queries [[CORTEX: ...]]
        cortex_queries = re.findall(r"\[\[CORTEX: (.*?)\]\]", content)
        for query in cortex_queries:
            # Capture if needed
            images_to_use = None
            if visual_context:
                import io, base64
                if isinstance(visual_context, list): # Already b64
                    images_to_use = visual_context
                else: # PIL
                    buf = io.BytesIO()
                    visual_context.save(buf, format="PNG")
                    images_to_use = [base64.b64encode(buf.getvalue()).decode('utf-8')]
            
            cortex_res = self.router.route_request(
                task_type="visual",
                prompt=query,
                system_prompt="You are ARAFURA's Visual Cortex. Provide [X, Y] (0-1000) grounding and state analysis.",
                images=images_to_use
            )
            cortex_msg = f"👁️ **CORTEX:** {cortex_res}"
            response += f"\n\n{cortex_msg}"
            self._emit_event("visual_log", {"msg": cortex_msg})

        # 4. Handle Memories [[MEMORY: ...]]
        memories = re.findall(r"\[\[MEMORY: (.*?)\]\]", content)
        for mem_text in memories:
            self.vector_memory.store_experience(
                category="visual_persistance",
                observation=mem_text,
                action="Commit",
                outcome="Saved",
                image_pil=visual_context if visual_context and not isinstance(visual_context, list) else None
            )
            response += f"\n\n💾 [MEMORY] Recorded: {mem_text}"

        # 5. Handle Consultations [[CONSULT: ...]] (HITL)
        consultations = re.findall(r"\[\[CONSULT: (.*?)\]\]", content)
        for query in consultations:
            self.state.hitl_paused = True
            cons_msg = f"⚠️ **HUMAN CONSULTATION REQUIRED:**\n{query}\n\n[System Paused. Reply to resume.]"
            response += f"\n\n{cons_msg}"
            self._emit_event("hitl_consultation", {"msg": query})
            self._emit_event("visual_log", {"msg": "⏸️ Autonomy paused for HITL."})

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
                        
                        # UX: Auto-activar vision mode e inmediata percepción
                        self.system_mode = "vision"
                        self.last_perception_time = 0 # FORZAR REFRESCO INMEDIATO
                        
                        # Force UI Update
                        self._emit_event("monitor_update", {
                            "equity": self.monitor.equity,
                            "prosperity": self.monitor.prosperity,
                            "mode": self.system_mode.upper(),
                            "autonomy": self.state.autonomy_active,
                            "gamer": self.state.gamer_mode
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
        """Coordinador Modular de Ciclos de Vida (Hardenened Architecture)"""
        while self.running:
            try:
                now = time.time()
                
                # 1. Ciclo de Salud y Telemetría
                self._cycle_monitor_ui(now)
                
                # 2. Ciclo de Visión y Autonomía
                if not self.state.hitl_paused and not self.state.interrupt_signal.is_set():
                    self._cycle_vision_autonomy(now)
                
                # 3. Ciclo de Reflexión Estratégica
                self._cycle_deep_thought(now)
                
                # 4. Ciclo de Momentos de Vida / Spontaneity
                self._cycle_life_moments(now)

                # 5. Mantenimiento de Memoria
                self._manage_memory()

            except Exception as e:
                print(f"致命的なエラー (Critical Background Error): {e}")
                time.sleep(1)
            
            time.sleep(0.05)

    def _cycle_monitor_ui(self, now):
        """Gestiona la telemetría y sincronización de la UI"""
        # (Lógica extraída de run_background_loop)
        if now - self.last_monitor_time > 1:
            self.last_monitor_time = now
            self.monitor.tick()
            
            # Hierarchy: AUTO > GAMER > VISION > CHAT
            if self.state.autonomy_active:
                remaining = int(self.autonomy_end_time - now)
                mode_display = f"AUTO {remaining}s"
            elif self.state.gamer_mode:
                mode_display = "GAMER 🎮"
            else:
                mode_display = self.system_mode.upper()

            # EMIT CORE HEALTH v5.1 (Load scaling)
            base_load = self.state.power_level * 10
            if self.state.gamer_mode: base_load += 15
            if self.state.autonomy_active: base_load += 25
            
            import random
            load = min(100, max(0, base_load + random.randint(-5, 5)))
            trace = "#" + self.vector_memory.last_id[:6].upper() if hasattr(self.vector_memory, 'last_id') and self.vector_memory.last_id else "#EMPTY"
            
            self._emit_event("nucleus_update", {
                "load": load,
                "sync": "ESTABLE",
                "trace": trace,
                "autonomy": self.state.autonomy_active,
                "gamer": self.state.gamer_mode,
                "mode": mode_display
            })

    def _cycle_vision_autonomy(self, now):
        """Ciclo crítico de percepción visual y acción"""
        # Power scaling: 1.0 (5s) -> 10.0 (0.2s)
        if self.state.power_level >= 9.0:
            vision_interval = 0.2
        else:
            base_interval = 2.0 if not self.state.gamer_mode else 1.0
            vision_interval = base_interval / (self.state.power_level / 5.0)

        if self.visual and getattr(self.visual, 'active_window', None) and now - self.last_perception_time > vision_interval:
            self.last_perception_time = now
            try:
                # Capture Base64 image
                b64_img, changed = self.vision_pipeline.get_latest_frame(force=True)
                if not b64_img: return
                
                # Precision Crop
                crop_img = self.visual.capture_cursor_crop(size=500)
                def encode_pil(img):
                    import io, base64
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    return base64.b64encode(buf.getvalue()).decode('utf-8')
                b64_crop = encode_pil(crop_img) if crop_img else None

                # Emit Feed
                self._emit_event("vision_frame", {"image": b64_img})
                if b64_crop:
                    self._emit_event("vision_crop", {"image": b64_crop})

                if self.system_mode == "vision":
                    w, h = self.visual.active_window.width, self.visual.active_window.height
                    
                    if self.state.autonomy_active:
                        self._execute_autonomy_cycle(w, h, b64_img, b64_crop)
                    else:
                        # Reflex Mode (High Speed simple vision processing)
                        self._execute_vision_reflex(w, h, b64_img, b64_crop)

            except Exception as e:
                print(f"Vision Cycle Error: {e}")

    def _execute_vision_reflex(self, w, h, b64_img, b64_crop):
        """Versión simplificada de autonomía para respuesta rápida"""
        if self.state.gamer_mode:
            prompt = f"{self.gamer_prompt}\n\nSCREEN: {w}x{h}. Window: {self.visual.active_window.title}"
        elif self.state.power_level >= 8.5:
            prompt = f"TURBO MODE. Resolution: {w}x{h}.\nTASK: Tactical GUI maintenance.\nACT NOW."
        else:
            prompt = (
                f"ROLE: Autonomous GUI Agent (SIMA).\n"
                f"SCREEN RESOLUTION: {w}x{h}.\n"
                "GOAL: PROSPERITY & SURVIVAL.\n"
                "Use [[ACTION: ...]]"
            )

        images = [b64_img]
        if b64_crop: images.append(b64_crop)
        
        res = self.router.route_request(task_type="visual", prompt=prompt, images=images)
        if res:
             self._process_autonomous_response(res, w, h)

    def _process_autonomous_response(self, res, w, h):
        """Parsea y ejecuta acciones con el Action Budget integrado"""
        clean_res = res.replace('\n', ' ').strip()
        words = clean_res.split()
        if len(words) > 133: clean_res = " ".join(words[:133]) + "..."
        
        mode_tag = "GAMER" if self.state.gamer_mode else "SIMA"
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] [{mode_tag}] {clean_res}"
        self.visual_log.append(msg)
        self._emit_event("visual_log", {"msg": msg})

        # Actions
        actions = self._extract_actions(res, (w, h))
        for action_cmd in actions:
            if self._spend_action_token():
                decision_json = {"decision": action_cmd}
                self.visual.execute_decision(decision_json)
                self._emit_event("visual_log", {"msg": f"--> [AUTO] Executed: {action_cmd}"})
            else:
                self._emit_event("visual_log", {"msg": "⚠️ ACTION BUDGET DEPLETED."})
                break

    def _cycle_deep_thought(self, now):
        """Pensamiento estratégico de fondo"""
        if now - self.last_thought_time > 20:
            self.last_thought_time = now
            try:
                context_str = f"Focus: {self.visual.active_window.title if self.visual and self.visual.active_window else 'Nominal'}"
                prompt = f"System Context: {context_str}. Generate a strategic thought (max 50 words)."
                res = self.router.route_request("reflexion", prompt)
                if res:
                    clean_res = res.replace('\n', ' ').strip()
                    self.thought_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {clean_res}")
                    self._emit_event("thought_log", {"msg": clean_res})
            except Exception as e:
                print(f"Deep Thought Error: {e}")

    def _cycle_life_moments(self, now):
        """Spontaneity Engine (Life Moments)"""
        # Solo si ocioso
        if now - self.last_activity_time > self.idle_threshold:
            if now - self.last_life_thought_time > 300: # 5 min
                self.last_life_thought_time = now
                try:
                    prompt = "System is idle. You are ARAFURA. Generate a spontaneous technical observation."
                    res = self.router.route_request("reflexion", prompt)
                    if res:
                        msg = f"🌿 [LIFE] {res.strip()}"
                        self._emit_event("thought_log", {"msg": msg})
                except Exception as e:
                    self._emit_event("visual_log", {"msg": f"🌿 [LIFE] Error en momento espontáneo: {str(e)}"})

    def _manage_memory(self):
        """Truncates logs and context to prevent unbounded growth."""
        MAX_LOGS = 100
        MAX_CONTEXT = 30
        
        if len(self.thought_log) > MAX_LOGS:
            self.thought_log = self.thought_log[-MAX_LOGS:]
        
        if len(self.visual_log) > MAX_LOGS:
            self.visual_log = self.visual_log[-MAX_LOGS:]
            
        if len(self.context_history) > MAX_CONTEXT:
            # Preserve identity first message if it's there
            if self.context_history and self.context_history[0].get('role') == 'system':
                self.context_history = [self.context_history[0]] + self.context_history[-(MAX_CONTEXT-1):]
            else:
                self.context_history = self.context_history[-MAX_CONTEXT:]

    def _execute_autonomy_cycle(self, w, h, b64_img, b64_crop):
        """Ciclo de autonomía avanzado con persistencia cognitiva"""
        # (Injecting cognitive state into prompt)
        strategy_context = f"CURRENT STRATEGY: {self.state.strategy}. MOOD: {self.state.mood}."
        now = time.time()
        remaining = int(self.autonomy_end_time - now)
        
        # Check timeout
        if remaining <= 0:
            self.state.autonomy_active = False
            self.state.gamer_mode = False
            self._emit_event("visual_log", {"msg": f"🛑 AUTONOMÍA FINALIZADA. Total acciones: {self.autonomy_action_count}"})
            self._update_monitor_ui()
            return
        
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
{strategy_context}
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
{strategy_context}
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
                
                # Record state before action
                pre_equity = self.monitor.equity

                if atype == "move":
                    self.visual.execute_decision({"decision": f"move {abs_x}, {abs_y}"})
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
                    with self.perception_lock:
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
                    # Log Tile Index + Center
                    t_row, t_col = y // tile_size, x // tile_size
                    print(f"📖 [OCR] Processing Tile [{t_row},{t_col}] at ({center_x},{center_y})")
                    self._emit_event("visual_log", {
                        "msg": f"📖 OCR Reading Tile [{t_row},{t_col}]..."
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
                            msg = f"📝 OCR Found {len(tile_entry['ocr'])} items in [{t_row},{t_col}]: {sample_text}..."
                            self._emit_event("visual_log", {"msg": msg})
            
            # Allow UI to breathe
            time.sleep(0.1)
                        
        self._emit_event("visual_log", {"msg": f"✅ OCR COMPLETE. Indexing {len(self.ocr_memory)} tiles."})

    def set_power_level(self, level: float):
        """Ajusta la agresividad y consumo de recursos (Overclocking)"""
        self.state.power_level = max(1.0, min(10.0, level))
        # Decoupling: Power 10 -> Max Aggressiveness & Frequency
        self.state.aggressiveness = self.state.power_level / 10.0
        self.state.perception_freq = self.state.power_level / 2.0 # Max 5Hz
        
        self._emit_event("visual_log", {"msg": f"⚡ SYSTEM OVERCLOCK: Power Level {self.state.power_level:.1f} (Freq: {self.state.perception_freq:.1f}Hz)"})
        self._update_monitor_ui()

    def _spend_action_token(self):
        """Action Budget (Token Bucket) logic"""
        now = time.time()
        elapsed = now - self.state.action_budget["last_refill"]
        # Refill rate also scales with power level slightly
        refill_rate = 0.5 + (self.state.power_level / 10.0) 
        self.state.action_budget["tokens"] = min(10, self.state.action_budget["tokens"] + elapsed * refill_rate)
        self.state.action_budget["last_refill"] = now
        
        if self.state.action_budget["tokens"] >= 1:
            self.state.action_budget["tokens"] -= 1
            return True
        return False

    def start(self):
        print("[Orchestrator] ARAFURA SYSTEM ONLINE")
        
        # Iniciar Sistemas Perceptuales (Visión + Puntero)
        self.vision_pipeline.start()
        self.visual.start_ghost_cursor()
        
        # Precarga concurrente
        threading.Thread(target=self.router.load_model, args=("chat",)).start()
        threading.Thread(target=self.router.load_model, args=("reflexion",)).start()
        threading.Thread(target=self.router.load_model, args=("vision",)).start()
        
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

