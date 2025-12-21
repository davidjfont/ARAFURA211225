#!/usr/bin/env python3
"""
ARAFURA CLI — Terminal Local
Interfaz de línea de comandos para interactuar con ARAFURA

Uso:
    python arafura_cli.py
    python arafura_cli.py --model local
    python arafura_cli.py --identity ../arafura_identity.json
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
    RESET = '\033[0m'
    BOLD = '\033[1m'

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
    return "Eres ARAFURA, la voz narrativa de un sistema de continuidad."

def log_session(message: str, role: str = "system"):
    """Registrar mensaje en sesión (si sessions/ existe)"""
    sessions_dir = Path(__file__).parent.parent.parent / "sessions"
    if sessions_dir.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        session_file = sessions_dir / f"session_{today}.log"
        with open(session_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] [{role.upper()}] {message}\n")

def interactive_loop(identity: dict, config: dict):
    """Loop principal de interacción"""
    print(f"\n{Colors.SYSTEM}Escribe tu mensaje. Usa 'salir' o 'exit' para terminar.{Colors.RESET}")
    print(f"{Colors.SYSTEM}Usa '/estado' para ver el estado del sistema.{Colors.RESET}")
    print(f"{Colors.SYSTEM}Usa '/manifiesto' para ver el manifiesto.{Colors.RESET}\n")
    
    while True:
        try:
            user_input = input(f"{Colors.USER}[Tú] > {Colors.RESET}")
            
            if user_input.lower() in ['salir', 'exit', 'quit']:
                print(f"\n{Colors.ARAFURA}[ARAFURA] Hasta pronto. El sistema persiste.{Colors.RESET}\n")
                break
            
            if user_input == '/estado':
                state_path = Path(__file__).parent.parent.parent / "core" / "memory" / "states" / "genesis.yaml"
                if state_path.exists():
                    with open(state_path, 'r', encoding='utf-8') as f:
                        state = yaml.safe_load(f)
                    print(f"\n{Colors.SYSTEM}Estado: {state.get('status', {}).get('description', 'Desconocido')}{Colors.RESET}")
                    print(f"{Colors.SYSTEM}Capa: {state.get('status', {}).get('layer', '?')}{Colors.RESET}\n")
                continue
            
            if user_input == '/manifiesto':
                manifesto_path = Path(__file__).parent.parent.parent / "MANIFIESTO_ARAFURA_v1.md"
                if manifesto_path.exists():
                    with open(manifesto_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:30]  # Primeras 30 líneas
                    print(f"\n{Colors.ARAFURA}{''.join(lines)}{Colors.RESET}\n")
                continue
            
            # Log de sesión
            log_session(user_input, "user")
            
            # Respuesta placeholder (aquí iría la llamada al LLM)
            response = f"""[Modo demo - Sin LLM conectado]

Para conectar un LLM, configura en .env:
- ANTHROPIC_API_KEY para Claude
- OPENAI_API_KEY para GPT
- LOCAL_MODEL para Ollama

System prompt cargado:
{get_system_prompt(identity, config)[:200]}...
"""
            print(f"\n{Colors.ARAFURA}[ARAFURA] {response}{Colors.RESET}\n")
            log_session(response, "arafura")
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.ARAFURA}[ARAFURA] Interrupción detectada. Persistiendo...{Colors.RESET}\n")
            break

def main():
    parser = argparse.ArgumentParser(description="ARAFURA CLI - Terminal Local")
    parser.add_argument('--identity', type=str, default=None, 
                        help='Ruta al archivo de identidad JSON')
    parser.add_argument('--model', type=str, default='demo',
                        choices=['demo', 'claude', 'openai', 'local'],
                        help='Modelo a utilizar')
    parser.add_argument('--quiet', action='store_true',
                        help='Modo silencioso, sin banner')
    
    args = parser.parse_args()
    
    # Encontrar archivos de identidad
    base_path = Path(__file__).parent.parent.parent
    identity_path = args.identity or str(base_path / "arafura_identity.json")
    
    # Cargar identidad y configuración
    identity = load_identity(identity_path)
    config = load_agent_config("arafura")
    
    if not args.quiet:
        print_banner()
        
        if identity:
            print(f"{Colors.SYSTEM}Identidad cargada: {identity['entity']['name']}{Colors.RESET}")
        if config:
            print(f"{Colors.SYSTEM}Configuración: {config['agent_id']}{Colors.RESET}")
        print(f"{Colors.SYSTEM}Modelo: {args.model}{Colors.RESET}")
    
    # Iniciar loop interactivo
    interactive_loop(identity, config)

if __name__ == "__main__":
    main()
