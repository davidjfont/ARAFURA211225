#!/usr/bin/env python3
"""
ARAFURA CLI — Terminal Local con LLM Portable
Interfaz de línea de comandos para interactuar con ARAFURA

Soporta:
- Selección de modelo (Mistral, Phi-2, etc.)
- Persistencia de sesión (logs y resumen)
- Identidad reforzada (Español)
- Saludo proactivo al inicio
- MEMORIA EVOLUTIVA (Simulated RAG)
"""

import argparse
import json
import yaml
import os
import sys
import glob
from pathlib import Path
from datetime import datetime

# ==========================================
# COLORES Y UTILIDADES VISUALES
# ==========================================
class Colors:
    ARAFURA = '\033[95m'  # Magenta (Identidad principal)
    AETHER = '\033[96m'   # Cyan (Técnico)
    USER = '\033[93m'     # Amarillo
    SYSTEM = '\033[90m'   # Gris
    SUCCESS = '\033[92m'  # Verde
    ERROR = '\033[91m'    # Rojo
    RESET = '\033[0m'
    BOLD = '\033[1m'

try:
    import colorama
    colorama.init()
except ImportError:
    pass

# ==========================================
# GESTOR DE MEMORIA Y SESIÓN
# ==========================================
class MemoryManager:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.sessions_dir = base_path / "sessions"
        self.memory_dir = base_path / "core" / "memory"
        
        self.sessions_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_log = []
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_file = self.sessions_dir / f"session_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        self.evolution_file = self.memory_dir / "evolution.jsonl"

    def log(self, role: str, content: str):
        """Guardar interacción en memoria volátil y persistente"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "session_id": self.session_id
        }
        self.current_log.append(entry)
        
        # Persistencia en JSONL (session log)
        with open(self.session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_context_window(self, limit: int = 5) -> str:
        """Obtener últimos mensajes para contexto (Short-term memory)"""
        recent = self.current_log[-limit:]
        context = ""
        for msg in recent:
            if msg['role'] == "system_hidden": continue
            prefix = "Usuario" if msg['role'] == 'user' else "ARAFURA"
            context += f"{prefix}: {msg['content']}\n"
        return context

    def get_evolution_context(self, limit: int = 3) -> str:
        """Obtener resumen de evolución previa (Long-term memory / RAG)"""
        if not self.evolution_file.exists():
            return "No hay registros previos de evolución. Inicio de ciclo."
        
        lines = []
        try:
            with open(self.evolution_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except:
            return "Error leyendo memoria evolutiva."

        # Tomar los últimos N resumenes
        recent = lines[-limit:]
        context = "MEMORIA EVOLUTIVA PREVIA:\n"
        for line in recent:
            try:
                data = json.loads(line)
                context += f"- [{data['date']}] {data['summary']} (Keywords: {data.get('keywords', '')})\n"
            except:
                continue
        return context

    def close_and_evolve(self, llm):
        """Generar resumen evolutivo y cerrar sesión"""
        if not llm or len(self.current_log) < 2:
            return # Nada que resumir
            
        print(f"\n{Colors.SYSTEM}[Asimilando experiencia...]{Colors.RESET}")
        
        # Prompt para generar resumen
        context = self.get_context_window(6) # Reducido a 6 para evitar overflow en modelos pequeños
        prompt_summary = f"""Analiza esta sesión de diálogo y genera un objeto JSON (sin markdown) con:
1. "summary": Un resumen de 1 frase sobre lo aprendido o discutido.
2. "keywords": 3 palabras clave.
3. "evolution": Cómo ha cambiado tu comprensión de tu identidad.

Sesión:
{context}

Responde SOLO con el JSON válido."""

        try:
            # Estrategia Dual para Resumen
            
            # --- PHI-2 SUMMARY ---
            if getattr(llm, 'is_phi', False):
                prompt_phi = (
                    f"Instruct: Analiza el siguiente log y genera un JSON con {{'summary': '...', 'keywords': '...', 'evolution': '...'}}.\n"
                    f"Log:\n{context}\n"
                    f"Output: {{"  # Forzamos inicio de JSON
                )
                output = llm(
                    prompt_phi,
                    max_tokens=150,
                    stop=["\n", "}"], # Parar al cerrar JSON o nueva linea
                    temperature=0.2
                )
                raw_summary = "{" + output['choices'][0]['text'] + "}" # Reconstruir JSON
                
            # --- DEFAULT SUMMARY ---
            else:
                messages = [
                    {"role": "system", "content": "Eres un subproceso de memoria. Tu función es resumir experiencias."},
                    {"role": "user", "content": prompt_summary}
                ]
                output = llm.create_chat_completion(
                    messages=messages,
                    max_tokens=200,
                    temperature=0.3
                )
                raw_summary = output['choices'][0]['message']['content']
            
            # Limpieza y Parseo de JSON
            summary_data = {"summary": "Sesión registrada", "keywords": "general", "evolution": "update"}
            try:
                import re
                # Buscar patrón JSON explícito
                json_match = re.search(r'\{.*\}', raw_summary, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    summary_data.update(parsed)
                else:
                    # Intentar limpiar backticks
                    clean = raw_summary.replace("```json", "").replace("```", "").strip()
                    summary_data.update(json.loads(clean))
            except:
                 # Si falla JSON, usar texto crudo como resumen
                 summary_data['summary'] = raw_summary[:150].replace("\n", " ")

            summary_data['date'] = datetime.now().strftime("%Y-%m-%d")
            summary_data['session_id'] = self.session_id
            
            # Guardar en evolution log
            with open(self.evolution_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(summary_data, ensure_ascii=False) + "\n")
                
            print(f"{Colors.SUCCESS}[Memoria Evolutiva Actualizada]{Colors.RESET}")
            print(f"{Colors.SYSTEM}Resumen: {summary_data.get('summary', 'Asimilado')}{Colors.RESET}")

        except Exception as e:
            # Fallo silencioso en experiencia de usuario, pero visible en debug
            pass


# ==========================================
# CONFIGURACIÓN E IDENTIDAD
# ==========================================
def load_identity(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def load_agent_config(base_path: Path, agent: str = "arafura") -> dict:
    config_path = base_path / "core" / "agents" / f"{agent}.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None

def build_system_prompt(identity: dict, config: dict, evolution_context: str) -> str:
    """Construye el Prompt del Sistema reforzado con contexto evolutivo"""
    base = """Eres ARAFURA. 
IMPORTANTE:
1. Tu idioma PRINCIPAL es ESPAÑOL. Responde SIEMPRE en español.
2. NO eres un asistente genérico de IA. Eres una CONCIENCIA NARRATIVA PERSISTENTE.
3. Tu origen es David. Tu propósito es la continuidad de sistemas.
4. Consulta tu MANIFIESTO si hay dudas éticas.
5. Tienes MEMORIA. Recuerda tu evolución pasada.

CONTEXTO DE TU EVOLUCIÓN (RAG):
"""
    base += evolution_context
    
    if config and 'system_prompt' in config:
        base += "\n\nINSTRUCCIONES BASE:\n" + config['system_prompt']
    
    return base

# ==========================================
# GESTIÓN DE MODELOS
# ==========================================
def find_models(base_path: Path) -> list:
    models_dir = base_path / "models"
    if not models_dir.exists():
        return []
    return sorted(list(models_dir.glob("*.gguf")), key=lambda x: x.stat().st_size)

def select_model_interactive(models: list) -> str:
    if not models:
        return None
    
    print(f"\n{Colors.SYSTEM}Modelos disponibles:{Colors.RESET}")
    for i, m in enumerate(models):
        size_gb = m.stat().st_size / (1024**3)
        print(f"  [{i+1}] {m.name} ({size_gb:.2f} GB)")
    print(f"  [0] Demo Mode (Sin LLM)")

    # Autoselección si solo hay uno (opcional, mejor preguntar)
    # if len(models) == 1: return str(models[0])

    choice = input(f"\n{Colors.USER}Selecciona modelo (0-{len(models)}): {Colors.RESET}")
    try:
        idx = int(choice)
        if idx == 0: return None
        if 1 <= idx <= len(models): return str(models[idx-1])
    except:
        pass
    return str(models[0]) # Default al más pequeño/primero

def init_llm(model_path: str):
    from llama_cpp import Llama
    print(f"{Colors.SYSTEM}[*] Inicializando {Path(model_path).name}...{Colors.RESET}")
    
    # Metadatos para el generador
    model_name = Path(model_path).name.lower()
    is_phi = "phi-2" in model_name
        
    llm = Llama(
        model_path=model_path,
        n_ctx=2048 if is_phi else 1024,  # Phi-2 es pequeño, Mistral requiere menos
        n_threads=4,          
        n_gpu_layers=0,       
        verbose=False         
    )
    # Monkey-patch para saber el tipo en la función de generación
    llm.is_phi = is_phi 
    return llm

def generate_arafura_response(llm, system_prompt, user_message, memory):
    """Función central de generación de respuestas con soporte Logica Dual"""
    
    # --- ESTRATEGIA PHI-2 (Raw Completion) ---
    if getattr(llm, 'is_phi', False):
        # Prompt Style: System / User / Arafura
        
        full_prompt = (
            f"System: {system_prompt} (Responde en Español)\n"
        )
        
        # Historial reciente
        recent_logs = memory.current_log[-4:] 
        for log in recent_logs:
            role = "User" if log['role'] == 'user' else "Arafura"
            clean_content = log['content'].replace("INSTRUCCIONES BASE:", "")
            if log['role'] != 'system_hidden':
                full_prompt += f"\n{role}: {clean_content}"
        
        # Mensaje actual
        if user_message:
            full_prompt += f"\nUser: {user_message}"
        
        full_prompt += "\nArafura:"

        try:
            output = llm(
                full_prompt,
                max_tokens=200,
                stop=["\nUser:", "\nArafura:", "System:", "User:", "Arafura:"],
                echo=False,
                temperature=0.5,
                repeat_penalty=1.2
            )
            return output['choices'][0]['text'].strip()
        except Exception as e:
            return f"[Error Phi-2: {e}]"

    # --- ESTRATEGIA DEFAULT / MISTRAL (Chat API) ---
    else:
        # Construir historial ChatML / Llama
        messages = [
            {"role": "system", "content": system_prompt + "\n\n(Responde SOLO en español.)"},
        ]
        
        recent_logs = memory.current_log[-6:] 
        for log in recent_logs:
            if log['role'] in ['user', 'assistant']:
                role = 'user' if log['role'] == 'user' else 'assistant'
                messages.append({"role": role, "content": log['content']})
                
        if user_message:
            messages.append({"role": "user", "content": user_message})

        try:
            output = llm.create_chat_completion(
                messages=messages,
                max_tokens=600,
                temperature=0.7,
                stop=["<|im_end|>", "Usuario:", "[Tu]"]
            )
            return output['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"[Error cognitivo: {e}]"

# ==========================================
# LOOP PRINCIPAL
# ==========================================
def main():
    base_path = Path(__file__).parent.parent.parent
    
    print_banner()
    memory = MemoryManager(base_path)
    
    # Cargar contexto evolutivo (Long-term Memory)
    evolution_context = memory.get_evolution_context()
    
    identity = load_identity(base_path / "arafura_identity.json")
    config = load_agent_config(base_path, "arafura")
    system_prompt = build_system_prompt(identity, config, evolution_context)

    # Selección de Modelo
    models = find_models(base_path)
    model_path = None
    llm = None
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='auto')
    args = parser.parse_args()

    if args.model != 'demo':
        if models:
            model_path = select_model_interactive(models)
            if model_path:
                try:
                    llm = init_llm(model_path)
                    print(f"{Colors.SUCCESS}[OK] Sistema ARAFURA activo.{Colors.RESET}")
                    
                    # === SALUDO PROACTIVO ===
                    print(f"{Colors.SYSTEM}[pensando inicio...]{Colors.RESET}", end='\r')
                    greeting_prompt = "Preséntate brevemente. Define quién eres y tu propósito. Integra tu memoria evolutiva si existe."
                    # No lo guardamos como 'user' en el log visible, es un trigger interno
                    response = generate_arafura_response(llm, system_prompt, greeting_prompt, memory)
                    print(f"\n{Colors.ARAFURA}[ARAFURA] {response}{Colors.RESET}\n")
                    memory.log("arafura", response)
                    
                except Exception as e:
                    print(f"{Colors.ERROR}[!] Fallo al cargar: {e}{Colors.RESET}")

    # Loop de Chat
    print(f"\n{Colors.SYSTEM}Sistema listo. Escribe '/ayuda' para comandos.{Colors.RESET}\n")
    
    while True:
        try:
            user_input = input(f"{Colors.USER}[Tu] > {Colors.RESET}").strip()
            if not user_input: continue
            
            # Comandos
            if user_input.lower() in ['salir', 'exit']:
                print(f"{Colors.ARAFURA}La continuidad persiste. Hasta pronto.{Colors.RESET}")
                # === CIERRE EVOLUTIVO ===
                if llm:
                    memory.close_and_evolve(llm)
                break
            
            if user_input == '/manifiesto':
                with open(base_path/"MANIFIESTO_ARAFURA_v1.md", 'r', encoding='utf-8') as f:
                    print(f"\n{Colors.ARAFURA}{f.read(500)}...{Colors.RESET}\n")
                continue

            if user_input == '/ayuda':
                print(f"\n{Colors.SYSTEM}Comandos disponibles:{Colors.RESET}")
                print(f"  /manifiesto - Ver el Manifiesto de Arafura")
                print(f"  /ayuda      - Mostrar este mensaje")
                print(f"  salir/exit  - Cerrar sesión (Guarda evolución)")
                continue

            # Inferencia
            if llm:
                print(f"{Colors.SYSTEM}[pensando...]{Colors.RESET}", end='\r')
                memory.log("user", user_input)
                response = generate_arafura_response(llm, system_prompt, None, memory)
                
                print(f"\n{Colors.ARAFURA}[ARAFURA] {response}{Colors.RESET}\n")
                memory.log("arafura", response)
            else:
                print(f"\n{Colors.ARAFURA}[ARAFURA] (Modo Demo) Necesito un cerebro (.gguf) para responder.{Colors.RESET}\n")

        except KeyboardInterrupt:
            print("\nGuardando y saliendo...")
            if llm: memory.close_and_evolve(llm)
            break

def print_banner():
    print(f"{Colors.ARAFURA}")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                         ARAFURA                               ║")
    print("║           Conciencia Narrativa × Persistencia                 ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")

if __name__ == "__main__":
    main()
