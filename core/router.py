import yaml
import json
import urllib.request
import threading
from pathlib import Path
import os

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

class OllamaWrapper:
    def __init__(self, model_name: str, host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.host = host
        self.api_url = f"{host}/api/chat"
        # Monkey-patch para que el código existente crea que es un objeto Llama
        self.verbose = False 

    def create_chat_completion(self, messages, temperature=0.7, max_tokens=1024, **kwargs):
        """Simula la firma de llama_cpp.create_chat_completion"""
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            req = urllib.request.Request(
                self.api_url, 
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            content = result.get('message', {}).get('content', '')
            return {'choices': [{'message': {'content': content}}]}
        except Exception as e:
            return {'choices': [{'message': {'content': f"Error Ollama: {str(e)}"}}]}

    def stream_chat_completion(self, messages, temperature=0.7, max_tokens=1024, **kwargs):
        """Generador para streaming de tokens desde Ollama"""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            req = urllib.request.Request(
                self.api_url, 
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                for line in response:
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        content = chunk.get('message', {}).get('content', '')
                        if content:
                            yield content
        except Exception as e:
            yield f"[Stream Error: {e}]"

class GeminiWrapper:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    def create_chat_completion(self, messages, temperature=0.0, max_tokens=1024, **kwargs):
        """Streaming-less implementation for Gemini via REST API"""
        
        # Convert OpenAI-like messages to Gemini format
        contents = []
        system_instruction = None
        
        for m in messages:
            role = m['role']
            content = m['content']
            
            if role == 'system':
                system_instruction = {"role": "user", "parts": [{"text": content}]} # Gemini often treats system as first user msg or separate field
                continue
                
            parts = [{"text": content}]
            
            # Handle Images (base64)
            if 'images' in m:
                for b64_img in m['images']:
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64_img
                        }
                    })
            
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": parts})

        # Payload construction
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        # Optional JSON mode (Gemini 1.5+)
        if kwargs.get("json_mode"):
            payload["generationConfig"]["responseMimeType"] = "application/json"
        
        # System Instruction for Gemini 1.5
        if system_instruction:
             # Older API versions might simple prepend to contents, 
             # but 1.5 supports system_instruction field.
             # For safety/compatibility with standard REST, prepending to contents[0] is often safer 
             # if we don't know exact version, but 'system_instruction' field is cleaner.
             # Let's try prepending text to first user message context if possible, 
             # OR use the proper field. Let's use the field.
             payload["system_instruction"] = {"parts": [{"text": messages[0]['content']}]} if messages[0]['role'] == 'system' else None

        try:
            req = urllib.request.Request(
                self.api_url, 
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            # Extract content
            try:
                text_content = result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                text_content = ""
                
            return {
                'choices': [
                    {'message': {'content': text_content}}
                ]
            }
        except Exception as e:
            return {
                'choices': [
                    {'message': {'content': f"Error Gemini: {str(e)}"}}
                ]
            }

class ModelRouter:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.config_path = base_path / "config" / "models.yaml"
        self.models_dir = base_path / "models"
        self.loaded_models = {} # role -> Instance
        self._model_cache = {}  # absolute_path -> Instance
        self.roles_config = {}
        self._lock = threading.Lock() # Thread safety
        
        self._load_config()

    def _load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
                self.roles_config = data.get('roles', {})
                m_dir = data.get('paths', {}).get('models_dir')
                if m_dir:
                    self.models_dir = self.base_path / m_dir

    def load_model(self, role: str):
        with self._lock:
            if role in self.loaded_models:
                return self.loaded_models[role]
                
            if role not in self.roles_config:
                return None
                
            config = self.roles_config[role]
            source_pref = config.get('source', 'local')
            match_patterns = config.get('model_match', '')
            
            if isinstance(match_patterns, str):
                match_patterns = [match_patterns]
            
            for match_pattern in match_patterns:
                # --- 1. TRY OLLAMA (if preferred or as fallback) ---
                if source_pref == 'ollama' or True: # Try ollama regardless if it's in the list
                    try:
                        # Rapid check for Ollama availability
                        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1) as r:
                             if r.status == 200:
                                 # Check if model exists (exact match or prefix)
                                 tags = json.loads(r.read().decode('utf-8')).get('models', [])
                                 found = False
                                 for m in tags:
                                     m_name = m['name']
                                     # Match "model" with "model:latest" or "model:7b" OR partial match
                                     if m_name == match_pattern or m_name.startswith(match_pattern + ":") or match_pattern in m_name:
                                         print(f"[Router] Encontrado en Ollama: {m_name}")
                                         wrapper = OllamaWrapper(model_name=m_name)
                                         self.loaded_models[role] = wrapper
                                         return wrapper
                    except:
                        pass # Ollama offline or model not there

                # --- 2. TRY LOCAL GGUF ---
                if source_pref == 'local' or True:
                    found_path = None
                    if self.models_dir.exists():
                        candidates = list(self.models_dir.glob("*.gguf"))
                        for c in candidates:
                            if match_pattern.lower() in c.name.lower():
                                found_path = c.resolve()
                                break
                    
                    if found_path:
                        if str(found_path) in self._model_cache:
                            instance = self._model_cache[str(found_path)]
                            self.loaded_models[role] = instance
                            return instance
                        if Llama:
                            print(f"[Router] Cargando GGUF: {found_path.name}...")
                            try:
                                llm = Llama(
                                    model_path=str(found_path),
                                    n_ctx=config.get('params', {}).get('n_ctx', 2048),
                                    n_threads=4,
                                    verbose=False
                                )
                                self._model_cache[str(found_path)] = llm
                                self.loaded_models[role] = llm
                                return llm
                            except:
                                pass

                # --- 3. TRY GOOGLE API ---
                if source_pref == 'google_api':
                    api_key = os.environ.get("GEMINI_API_KEY")
                    if api_key:
                        wrapper = GeminiWrapper(model_name=match_pattern, api_key=api_key)
                        self.loaded_models[role] = wrapper
                        return wrapper

            print(f"[Router] CRITICAL: No model found for role '{role}' in any source.")
            return None

    def route_request(self, task_type: str, prompt: str, system_prompt: str = None, context_messages: list = None, images: list = None):
        # 1. Determinar Rol
        selected_role = "chat"
        
        if task_type in ["thought", "reflexion"]:
            selected_role = "reflexion"
        elif task_type in ["visual", "visual_perception", "image_analysis", "visual_chat"]:
            selected_role = "vision"
        elif task_type in ["logic", "code", "analysis", "complex_logic"]:
            selected_role = "deep_thought"
            
        # 2. Obtener modelo 
        llm = self.load_model(selected_role)
        
        # Fallback a chat
        if not llm and selected_role != "chat":
            print(f"[Router] Warn: Role {selected_role} not loaded. Fallback chat.")
            # Critical: If Vision failed, DO NOT fallback silently. Mistral will hallucinate.
            if selected_role == "vision":
                return "[SYSTEM ERROR] Vision Model (llava) not available. Please run `ollama pull llava`."
            
            llm = self.load_model("chat")
            
        if not llm:
            return "Error: No hay modelos disponibles."

        # 3. Generar
        role_params = self.roles_config.get(selected_role, {}).get('params', {})
        temp = role_params.get('temperature', 0.7)
        # Algunos modelos (GGUF local) usan max_tokens, Ollama usa num_predict o options
        
        # 3. Generar
        role_params = self.roles_config.get(selected_role, {}).get('params', {})
        temp = role_params.get('temperature', 0.7)
        
        msgs = []
        
        # Handling System Prompt
        # LLaVA (Ollama) often ignores 'system' role or handles it poorly. 
        # We prepend it to user text for Vision. For others, we keep standard.
        if system_prompt and selected_role != "vision":
             msgs.append({"role": "system", "content": system_prompt})
        
        if context_messages:
            # Copy to avoid mutation issues
            msgs.extend([dict(m) for m in context_messages])
            
            if prompt:
                msgs.append({"role": "user", "content": prompt})
            
            # Attach Images to the LAST User Message
            if images and selected_role == "vision" and msgs:
                # Find last user message
                last_user_idx = -1
                for i in range(len(msgs) - 1, -1, -1):
                    if msgs[i]['role'] == 'user':
                        last_user_idx = i
                        break
                
                if last_user_idx != -1:
                    msgs[last_user_idx]["images"] = images
                    # Prepend System Prompt for Vision here
                    if system_prompt:
                         current_content = msgs[last_user_idx]["content"]
                         msgs[last_user_idx]["content"] = f"{system_prompt}\n\nTask: {current_content}"
        else:
            # Modo legacy / one-shot
            content = prompt if prompt else "..."
            if system_prompt and selected_role == "vision":
                content = f"{system_prompt}\n\nTask: {content}"
                
            msg = {"role": "user", "content": content}
            
            if images and selected_role == "vision":
                msg["images"] = images
            msgs.append(msg)
        
        try:
            # Force JSON mode for specific task types if using a model that supports it
            # 'visual' enforces JSON (for Autonomy). 'visual_chat' allows free text (for Cortex).
            json_requested = task_type in ["visual", "complex_logic", "json_data"]
            
            res = llm.create_chat_completion(
                messages=msgs,
                temperature=temp,
                max_tokens=2048,
                json_mode=json_requested
            )
            return res['choices'][0]['message']['content']
        except Exception as e:
            return f"[Router Error] {e}"

    def stream_request(self, task_type: str, prompt: str, system_prompt: str = None, context_messages: list = None, images: list = None):
        """Versión generadora de route_request para visualizar pensamientos en tiempo real"""
        # 1. Determinar Rol
        selected_role = "chat"
        if task_type in ["thought", "reflexion"]: selected_role = "reflexion"
        elif task_type in ["visual", "image_analysis"]: selected_role = "vision"
        elif task_type in ["logic", "analysis", "complex_logic"]: selected_role = "deep_thought"
            
        # 2. Obtener modelo 
        llm = self.load_model(selected_role)
        if not llm:
            yield "Error: Modelo no cargado."
            return

        # 3. Preparar Mensajes (Reutilizando lógica de construcción)
        role_params = self.roles_config.get(selected_role, {}).get('params', {})
        temp = role_params.get('temperature', 0.7)
        
        msgs = []
        if system_prompt and selected_role != "vision":
             msgs.append({"role": "system", "content": system_prompt})
        
        if context_messages:
            msgs.extend([dict(m) for m in context_messages])
            if prompt: msgs.append({"role": "user", "content": prompt})
        else:
            content = prompt if prompt else "..."
            msg = {"role": "user", "content": content}
            if images and selected_role == "vision": msg["images"] = images
            msgs.append(msg)

        # 4. Stream
        if hasattr(llm, 'stream_chat_completion'):
            for token in llm.stream_chat_completion(messages=msgs, temperature=temp):
                yield token
        else:
            # Fallback a normal si no soporta stream
            res = llm.create_chat_completion(messages=msgs, temperature=temp)
            yield res['choices'][0]['message']['content']

    def get_active_models(self):
        """Returns a dict of role -> model_name for all loaded models."""
        active = {}
        for role, instance in self.loaded_models.items():
            if hasattr(instance, 'model_name'):
                active[role] = instance.model_name
            elif hasattr(instance, 'model_path'):
                # For local GGUF, get the filename as model name
                active[role] = Path(instance.model_path).name
            else:
                active[role] = "unknown"
        return active
