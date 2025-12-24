import yaml
import json
import urllib.request
import threading
from pathlib import Path

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
                # Debug logging
                # print(f"[Ollama DEBUG] Raw Response keys: {result.keys()}") 
                
            # Adaptar respuesta al formato OpenAI/LlamaCpp
            content = result.get('message', {}).get('content', '')
            return {
                'choices': [
                    {'message': {'content': content}}
                ]
            }
        except Exception as e:
            return {
                'choices': [
                    {'message': {'content': f"Error Ollama: {str(e)}"}}
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
            source = config.get('source', 'local')
            match_pattern = config.get('model_match', '')
            
            # OLLAMA SOURCE
            if source == 'ollama':
                print(f"[Router] Conectando {role} -> Ollama ({match_pattern})...")
                try:
                    # Comprobación básica (ping) con Timeout corto
                    with urllib.request.urlopen("http://localhost:11434/", timeout=2) as r:
                        if r.status != 200: raise Exception("Ollama offline")
                    
                    wrapper = OllamaWrapper(model_name=match_pattern)
                    self.loaded_models[role] = wrapper
                    return wrapper
                except Exception as e:
                    print(f"[Router] Error Ollama {role}: {e}")
                    return None

        # LOCAL GGUF SOURCE
        found_path = None
        if self.models_dir.exists():
            candidates = list(self.models_dir.glob("*.gguf"))
            for c in candidates:
                if match_pattern.lower() in c.name.lower():
                    found_path = c.resolve() # Use absolute path for cache key
                    break
            
        if found_path:
            # CHECK CACHE FIRST
            if str(found_path) in self._model_cache:
                print(f"[Router] Reusando modelo cargado para {role} -> {found_path.name}")
                instance = self._model_cache[str(found_path)]
                self.loaded_models[role] = instance
                return instance

            if Llama:
                print(f"[Router] Cargando {role} -> {found_path.name} (Puede tardar)...")
                try:
                    llm = Llama(
                        model_path=str(found_path),
                        n_ctx=config.get('params', {}).get('n_ctx', 2048),
                        n_threads=4,
                        verbose=False
                    )
                    # Store in cache
                    self._model_cache[str(found_path)] = llm
                    self.loaded_models[role] = llm
                    return llm
                except Exception as e:
                    print(f"[Router] Error cargando {role}: {e}")
                    return None
        return None

    def route_request(self, task_type: str, prompt: str, system_prompt: str = None, context_messages: list = None, images: list = None):
        # 1. Determinar Rol
        selected_role = "chat"
        
        if task_type in ["thought", "reflexion"]:
            selected_role = "reflexion"
        elif task_type in ["visual", "visual_perception", "image_analysis"]:
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
            res = llm.create_chat_completion(
                messages=msgs,
                temperature=temp,
                max_tokens=2048 
            )
            return res['choices'][0]['message']['content']
        except Exception as e:
            return f"[Router Error] {e}"
