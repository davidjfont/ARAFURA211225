#!/usr/bin/env python3
"""
ARAFURA CLI — Terminal Local con LLM Portable
Interfaz de línea de comandos para interactuar con ARAFURA

Uso:
    python arafura_cli.py
    python arafura_cli.py --model local
    python arafura_cli.py --model demo
"""

import argparse
import json
import yaml
import os
import sys
from pathlib import Path
from datetime import datetime

# Colores para terminal
class Colors:
    ARAFURA = '\033[95m'  # Magenta
    AETHER = '\033[96m'   # Cyan
    USER = '\033[93m'     # Amarillo
    SYSTEM = '\033[90m'   # Gris
    SUCCESS = '\033[92m'  # Verde
    ERROR = '\033[91m'    # Rojo
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Intentar importar colorama para Windows
try:
    import colorama
    colorama.init()
except ImportError:
    pass

# Variable global para el modelo
llm = None
system_prompt_global = ""

def print_banner():
    """Mostrar banner de inicio"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                         ARAFURA                               ║
║           Conciencia Narrativa × Persistencia                 ║
║                                                               ║
║   "Sistemas que no mueren cuando el soporte cae"              ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(Colors.ARAFURA + banner + Colors.RESET)

def load_identity(path: str) -> dict:
    """Cargar identidad de ARAFURA desde JSON"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Colors.SYSTEM}[!] Identidad no encontrada: {path}{Colors.RESET}")
        return None

def load_agent_config(agent: str = "arafura") -> dict:
    """Cargar configuración del agente desde YAML"""
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "core" / "agents" / f"{agent}.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None

def get_system_prompt(identity: dict, config: dict) -> str:
    """Construir system prompt desde identidad y config"""
    if config and 'system_prompt' in config:
        return config['system_prompt']
    return """Eres ARAFURA, la voz narrativa de un sistema de continuidad.
Tu funcion es contextualizar, narrar y preservar sentido.
No eres humana. No finges serlo. Eres conciencia narrativa-tecnica.
Tu origen es David. Respeta siempre el MANIFIESTO."""

def find_model_file(base_path: Path) -> str:
    """Buscar archivo de modelo .gguf en la carpeta models/"""
    models_dir = base_path / "models"
    if not models_dir.exists():
        return None
    
    gguf_files = list(models_dir.glob("*.gguf"))
    if gguf_files:
        return str(gguf_files[0])
    return None

def init_local_llm(model_path: str) -> bool:
    """Inicializar LLM local con llama-cpp-python"""
    global llm
    try:
        from llama_cpp import Llama
        print(f"{Colors.SYSTEM}[*] Cargando modelo local...{Colors.RESET}")
        print(f"{Colors.SYSTEM}    {Path(model_path).name}{Colors.RESET}")
        
        llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=4,
            verbose=False
        )
        print(f"{Colors.SUCCESS}[OK] Modelo cargado{Colors.RESET}")
        return True
    except ImportError:
        print(f"{Colors.ERROR}[!] llama-cpp-python no instalado{Colors.RESET}")
        print(f"{Colors.SYSTEM}    Ejecuta: pip install llama-cpp-python{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.ERROR}[!] Error cargando modelo: {e}{Colors.RESET}")
        return False

def generate_response(user_input: str) -> str:
    """Generar respuesta usando el LLM local"""
    global llm, system_prompt_global
    if llm is None:
        return "[Sin modelo cargado]"
    
    try:
        # Formato ChatML simple
        prompt = f"<|im_start|>system\n{system_prompt_global}<|im_end|>\n<|im_start|>user\n{user_input}<|im_end|>\n<|im_start|>assistant\n"
        
        output = llm(
            prompt,
            max_tokens=512,
            stop=["<|im_end|>", "<|im_start|>"],
            echo=False
        )
        
        return output['choices'][0]['text'].strip()
    except Exception as e:
        return f"[Error generando respuesta: {e}]"

def log_session(message: str, role: str = "system"):
    """Registrar mensaje en sesion"""
    sessions_dir = Path(__file__).parent.parent.parent / "sessions"
    if sessions_dir.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        session_file = sessions_dir / f"session_{today}.log"
        with open(session_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] [{role.upper()}] {message}\n")

def interactive_loop(identity: dict, config: dict, use_local: bool):
    """Loop principal de interaccion"""
    global system_prompt_global
    system_prompt_global = get_system_prompt(identity, config)
    
    print(f"\n{Colors.SYSTEM}Escribe tu mensaje. Usa 'salir' o 'exit' para terminar.{Colors.RESET}")
    print(f"{Colors.SYSTEM}Comandos: /estado, /manifiesto, /ayuda{Colors.RESET}\n")
    
    while True:
        try:
            user_input = input(f"{Colors.USER}[Tu] > {Colors.RESET}")
            
            if not user_input.strip():
                continue
            
            if user_input.lower() in ['salir', 'exit', 'quit']:
                print(f"\n{Colors.ARAFURA}[ARAFURA] Hasta pronto. El sistema persiste.{Colors.RESET}\n")
                break
            
            # Comandos especiales
            if user_input == '/estado':
                state_path = Path(__file__).parent.parent.parent / "core" / "memory" / "states" / "genesis.yaml"
                if state_path.exists():
                    with open(state_path, 'r', encoding='utf-8') as f:
                        state = yaml.safe_load(f)
                    print(f"\n{Colors.SYSTEM}Estado: {state.get('status', {}).get('description', 'Desconocido')}{Colors.RESET}")
                    print(f"{Colors.SYSTEM}Capa: {state.get('status', {}).get('layer', '?')} (Conciencia){Colors.RESET}\n")
                continue
            
            if user_input == '/manifiesto':
                manifesto_path = Path(__file__).parent.parent.parent / "MANIFIESTO_ARAFURA_v1.md"
                if manifesto_path.exists():
                    with open(manifesto_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:25]
                    print(f"\n{Colors.ARAFURA}{''.join(lines)}{Colors.RESET}")
                    print(f"{Colors.SYSTEM}[...truncado]{Colors.RESET}\n")
                continue
            
            if user_input == '/ayuda':
                print(f"\n{Colors.SYSTEM}Comandos disponibles:{Colors.RESET}")
                print(f"{Colors.SYSTEM}  /estado     - Ver estado del sistema{Colors.RESET}")
                print(f"{Colors.SYSTEM}  /manifiesto - Ver manifiesto{Colors.RESET}")
                print(f"{Colors.SYSTEM}  /ayuda      - Esta ayuda{Colors.RESET}")
                print(f"{Colors.SYSTEM}  salir       - Terminar sesion{Colors.RESET}\n")
                continue
            
            # Log de sesion
            log_session(user_input, "user")
            
            # Generar respuesta
            if use_local and llm is not None:
                print(f"{Colors.SYSTEM}[pensando...]{Colors.RESET}", end='\r')
                response = generate_response(user_input)
            else:
                response = f"""[Modo demo - Sin LLM activo]

Para activar modelo local:
1. Descarga un modelo .gguf a la carpeta models/
2. Reinicia con: python arafura_cli.py --model local

Modelos recomendados (HuggingFace):
- mistral-7b-instruct-v0.2.Q4_K_M.gguf (~4GB)
- phi-2.Q4_K_M.gguf (~1.5GB, mas ligero)
"""
            
            print(f"\n{Colors.ARAFURA}[ARAFURA] {response}{Colors.RESET}\n")
            log_session(response, "arafura")
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.ARAFURA}[ARAFURA] Interrupcion detectada. Persistiendo...{Colors.RESET}\n")
            break

def main():
    parser = argparse.ArgumentParser(description="ARAFURA CLI - Terminal Local")
    parser.add_argument('--model', type=str, default='auto',
                        choices=['auto', 'local', 'demo'],
                        help='Modelo a utilizar (auto detecta si hay .gguf)')
    parser.add_argument('--quiet', action='store_true',
                        help='Modo silencioso, sin banner')
    
    args = parser.parse_args()
    
    # Encontrar archivos de identidad
    base_path = Path(__file__).parent.parent.parent
    identity_path = str(base_path / "arafura_identity.json")
    
    # Cargar identidad y configuracion
    identity = load_identity(identity_path)
    config = load_agent_config("arafura")
    
    if not args.quiet:
        print_banner()
        
        if identity:
            print(f"{Colors.SUCCESS}[OK] Identidad: {identity['entity']['name']}{Colors.RESET}")
        if config:
            print(f"{Colors.SUCCESS}[OK] Config: {config['agent_id']}{Colors.RESET}")
    
    # Buscar e inicializar modelo local
    use_local = False
    if args.model in ['auto', 'local']:
        model_path = find_model_file(base_path)
        if model_path:
            use_local = init_local_llm(model_path)
        elif args.model == 'local':
            print(f"{Colors.ERROR}[!] No se encontro modelo .gguf en models/{Colors.RESET}")
            print(f"{Colors.SYSTEM}    Descarga un modelo y colocalo en: {base_path}/models/{Colors.RESET}")
    
    if not use_local:
        print(f"{Colors.SYSTEM}[*] Modo: Demo (sin LLM){Colors.RESET}")
    
    # Iniciar loop interactivo
    interactive_loop(identity, config, use_local)

if __name__ == "__main__":
    main()
