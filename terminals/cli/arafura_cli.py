#!/usr/bin/env python3
"""
ARAFURA CLI — TUI Premium con Rich & Concurrencia
"""
import argparse
import json
import yaml
import os
import sys
import threading
import time
import queue
from pathlib import Path
from datetime import datetime

# Importaciones TUI
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    from rich.table import Table
    from rich.box import ROUNDED, HEAVY
    from rich.style import Style
    from rich.markdown import Markdown
    from rich import box
except ImportError:
    print("Error: 'rich' no está instalado. Ejecuta: pip install rich")
    sys.exit(1)

# Importaciones Sistema
if os.name == 'nt':
    import msvcrt
else:
    # Fallback básico para sistemas no-windows
    msvcrt = None

# ==========================================
# INPUT NO BLOQUEANTE (WINDOWS)
# ==========================================
class InputBuffer:
    def __init__(self):
        self.buffer = ""
        self.ready_commands = queue.Queue()
        self.cursor_visible = True
        self.last_blink = time.time()

    def check_input(self):
        """Revisar si hay teclas presionadas y actualizar buffer"""
        if os.name == 'nt':
            # Leemos todas las teclas pendientes en el buffer
            while msvcrt.kbhit():
                try:
                    ch = msvcrt.getwch()
                    if ch == '\r': # Enter
                        if self.buffer.strip():
                            self.ready_commands.put(self.buffer.strip())
                        self.buffer = ""
                    elif ch == '\b': # Backspace
                        self.buffer = self.buffer[:-1]
                    elif ch == '\x03': # Ctrl+C
                        raise KeyboardInterrupt
                    elif ch == '\xe0' or ch == '\x00': # Special keys
                        try:
                            # Consumir el byte extra de teclas especiales
                            msvcrt.getwch() 
                        except: pass
                    else:
                        # Aceptamos cualquier caracter imprimible
                        if ch.isprintable(): 
                            self.buffer += ch
                except Exception:
                    pass

    def get_renderable(self):
        # Blink cursor
        if time.time() - self.last_blink > 0.5:
            self.cursor_visible = not self.cursor_visible
            self.last_blink = time.time()
        
        cursor = "█" if self.cursor_visible else " "
        # Color más brillante si hay texto
        color = "bold yellow" if self.buffer else "dim yellow"
        return Text(f" {self.buffer}{cursor}", style=color)

# ==========================================
# GESTOR DE MEMORIA
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
        self.evolution_file = self.memory_dir / "evolution.jsonl"
        self._load_evolution()

    def _load_evolution(self):
        self.evolution_summary = []
        if self.evolution_file.exists():
            try:
                with open(self.evolution_file, 'r', encoding='utf-8') as f:
                    for line in f.readlines()[-3:]:
                        try:
                            self.evolution_summary.append(json.loads(line).get('summary', ''))
                        except: pass
            except: pass

    def log(self, role: str, content: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        self.current_log.append(entry)
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            path = self.sessions_dir / f"session_{date_str}.jsonl"
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except: pass

    def get_context(self, limit=5):
        hist = []
        for msg in self.current_log:
            if msg['role'] not in ['system_hidden']:
                role_name = "User" if msg['role'] == 'user' else "Arafura"
                hist.append(f"{role_name}: {msg['content']}")
        return "\n".join(hist[-limit:])

    def close_and_evolve(self, llm_wrapper=None):
        pass 

# ==========================================
# CLASE PRINCIPAL TUI
# ==========================================
class ArafuraCortex:
    def __init__(self):
        self.console = Console()
        self.input = InputBuffer()
        
        self.base_path = Path(__file__).resolve().parent.parent.parent
        sys.path.append(str(self.base_path))
        
        # CORE: Inicializamos el Orquestador
        # (El cerebro central que maneja Router, Memoria y Visión)
        from core.orchestrator import ArafuraOrchestrator
        self.orchestrator = ArafuraOrchestrator(self.base_path)
        
        # Estado TUI (View State)
        self.chat_history = []
        self.scroll_offsets = {
            'chat': 0,
            'vision': 0,
            'thought': 0
        }
        
    def setup_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        layout["left"].split_column(
            Layout(name="chat_panel", ratio=1)
        )
        layout["right"].split_column(
            Layout(name="vision_panel", ratio=1),
            Layout(name="thought_panel", ratio=1)
        )
        return layout

    def render_header(self):
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        
        # Estado del modelo activo obtenible del router si quisiéramos
        model_name = "Core Orchestrator v4.1"
        
        grid.add_row(
            "[b magenta]ARAFURA[/] [cyan]Core System v4.1[/]",
            f"[dim]System: Online | {datetime.now().strftime('%H:%M:%S')}[/]"
        )
        return Panel(grid, style="white on black", box=box.HEAVY_EDGE)

    def _get_viewport(self, items, offset, height):
        """Helper para scrolling manual"""
        total = len(items)
        if total == 0: return [], 0
        end = total - offset
        start = max(0, end - height)
        if end < 0: end = 0
        return items[start:end], total

    def render_chat(self):
        # 1. Height calculation
        # H - header(3) - footer(3) - border(2) - buffer(2) = H - 10
        # Being conservative ensures the BOTTOM line is visible.
        avail_h = max(5, self.console.height - 10) 
        
        # 2. Width calculation (Layout ratio 2:1 -> 2/3 of width)
        # padding(2) + border(2) + buffer(2) approx
        panel_w = int(self.console.width * 0.66) - 6
        
        # 3. Backwards collection respecting word wrap
        lines_used = 0
        subset = []
        
        # Start from end - offset
        history_len = len(self.chat_history)
        start_idx = history_len - 1 - self.scroll_offsets['chat']
        
        for i in range(start_idx, -1, -1):
            msg = self.chat_history[i]
            # Estimate lines this message takes
            # msg is Rich Text, len(msg) gives char count
            content_len = len(msg)
            # Ceiling division for lines + 1 safety buffer for rough wrap estimation
            msg_lines = max(1, (content_len + panel_w - 1) // panel_w)
            # Rich often wraps a bit earlier than strict char count, so let's add penalty for long lines
            if content_len > panel_w: msg_lines += 1
            
            if lines_used + msg_lines > avail_h:
                # If we're at the very start (newest msg) and it's huge, show what we can
                if lines_used == 0:
                     subset.append(msg)
                break
            
            subset.append(msg)
            lines_used += msg_lines
            
        # We collected backwards, so reverse for display
        subset.reverse()
        
        text = Text()
        for msg in subset:
            text.append(msg)
            text.append("\n")
            
        title = "[b]INTERACCIÓN[/]"
        if self.scroll_offsets['chat'] > 0:
            title += f" [dim](Historial -{self.scroll_offsets['chat']})[/]"
            
        return Panel(text, title=title, border_style="blue", box=ROUNDED)

    def render_vision(self):
        # Datos vienen del Orquestador
        visual_log = self.orchestrator.visual_log
        
        active_window = getattr(self.orchestrator.visual, 'active_window', None)
        target_name = active_window.title if active_window else "Ninguno"
        
        content = f"Estado: {'[bold green]ACTIVO[/]' if active_window else '[dim]Inactivo[/]'}\n"
        content += f"Target: [cyan]{target_name}[/]\n\n"
        content += "[b]Percepción Reciente (Phi-2):[/]\n"
        
        # Calcular altura disponible aproximada
        # Main area = H - 6. Vision es la mitad -> (H-6)/2
        # Menos cabecera del panel (4 lineas aprox)
        avail_h = max(3, int((self.console.height - 8) / 2) - 5)
        
        visible_lines = avail_h
        subset, total = self._get_viewport(visual_log, self.scroll_offsets['vision'], visible_lines)
        
        for log in subset:
             # Truncate visually for TUI if too long, let Rich wrap, but maybe limit distinct lines
             clean = log.replace('\n', ' ')
             # user asked for NO truncation, so we let it wrap.
             content += f"{clean}\n"
        
        return Panel(content, title="[b]VISUAL CORTEX (LIFE)[/]", border_style="magenta", box=ROUNDED)

    def render_thoughts(self):
        # Datos vienen del Orquestador
        thought_log = self.orchestrator.thought_log
        
        content = ""
        
        # (H - 6) / 2 - border
        avail_h = max(3, int((self.console.height - 8) / 2) - 2)
        visible_lines = avail_h
        
        # Auto-scroll si no hay offset manual
        if self.scroll_offsets['thought'] == 0:
            subset = thought_log[-visible_lines:]
            total = len(thought_log)
        else:
            subset, total = self._get_viewport(thought_log, self.scroll_offsets['thought'], visible_lines)
        
        for t in subset:
            # Full text
            cleaned = t.replace('\n', ' ')
            content += f"> {cleaned}\n"
        
        # Title info
        title = f"[b]FLUJO COGNITIVO[/]"
        if total > visible_lines and self.scroll_offsets['thought'] > 0:
            pos = total - self.scroll_offsets['thought']
            title += f" [dim][{pos}/{total}][/]"
        elif total > visible_lines:
             # Bottom
             title += f" [dim][Auto][/]"
            
        ind = "[bold blink yellow]thinking...[/]" if self.orchestrator.lock.locked() else ""
        if ind: title += f" {ind}"
        
        return Panel(content, title=title, border_style="cyan", box=ROUNDED)

    def render_input(self):
        return Panel(self.input.get_renderable(), title="[b]COMANDO[/]", border_style="yellow", box=HEAVY)

    def log_chat(self, role, text, color="white"):
        timestamp = datetime.now().strftime("%H:%M")
        t = Text(f"[{timestamp}] ", style="dim")
        t.append(f"{role}: ", style="bold " + color)
        t.append(text)
        self.chat_history.append(t)

    def process_command(self, cmd):
        # Scroll meta-commands
        if cmd == '/up':
            self.scroll_offsets['chat'] += 5
            return True
        if cmd == '/down':
            self.scroll_offsets['chat'] = max(0, self.scroll_offsets['chat'] - 5)
            return True
            
        self.log_chat("USER", cmd, "yellow")
        
        if cmd.lower() in ['salir', 'exit', 'quit']:
            return False
            
        # Delegar TODO al Orquestador
        # (El comando se ejecuta en thread aparte para no bloquear UI)
        threading.Thread(target=self._async_process, args=(cmd,)).start()
        return True

    def _async_process(self, cmd):
        try:
            # El orchestrator maneja /ventana, chat, routing, etc.
            response = self.orchestrator.process_input(cmd)
            self.log_chat("ARAFURA", response, "magenta")
        except Exception as e:
            self.log_chat("ERR", str(e), "red")

    def update_layout(self, layout):
        layout["header"].update(self.render_header())
        layout["chat_panel"].update(self.render_chat())
        layout["vision_panel"].update(self.render_vision())
        layout["thought_panel"].update(self.render_thoughts())
        layout["footer"].update(self.render_input())

    def select_model(self):
        models_dir = self.base_path / "models"
        if not models_dir.exists(): models_dir.mkdir(parents=True)
        # 1. Local GGUF
        local_models = sorted(list(models_dir.glob("*.gguf")), key=lambda x: x.stat().st_size)
        
        # 2. Ollama Options
        ollama_models = [
            {"name": "DeepSeek-R1 (Ollama)", "source": "ollama", "id": "deepseek-r1"},
            {"name": "Phi-2 (Ollama)", "source": "ollama", "id": "phi"}
        ]
        
        all_options = local_models + ollama_models

        self.console.print(Panel(f"[bold magenta]ARAFURA TUI v2[/]\n[dim]Modelos Locales + Ollama[/]", box=ROUNDED))

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Modelo")
        table.add_column("Tipo")

        for i, m in enumerate(all_options):
            if isinstance(m, dict):
                table.add_row(str(i+1), m["name"], "[magenta]API[/]")
            else:
                size_gb = m.stat().st_size / (1024**3)
                table.add_row(str(i+1), m.name, f"[green]Local ({size_gb:.2f}GB)[/]")
        
        table.add_row("0", "Demo Mode (Sin LLM)", "-")
        self.console.print(table)

        while True:
            choice = self.console.input("[bold yellow]Selecciona modelo principal (0-{}): [/]".format(len(all_options)))
            if choice.strip() == '0':
                return
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(all_options):
                    selected = all_options[idx]
                    
                    if isinstance(selected, dict):
                        # Ollama Selection
                        self.orchestrator.router.roles_config['chat']['model_match'] = selected["id"]
                        self.orchestrator.router.roles_config['chat']['source'] = 'ollama'
                        self.console.print(f"[green]Seleccionado: {selected['name']}[/]")
                    else:
                        # Local Selection
                        self.orchestrator.router.roles_config['chat']['model_match'] = selected.name
                        self.orchestrator.router.roles_config['chat']['source'] = 'local'
                        self.console.print(f"[green]Seleccionado: {selected.name}[/]")
                    return
            except:
                pass
            self.console.print("[red]Selección inválida.[/]")

    def select_interface(self):
        self.console.print(Panel(f"[bold cyan]ARAFURA LAUNCHER[/]\n[dim]Selecciona interfaz de operación[/]", box=ROUNDED))
        table = Table(show_header=True, header_style="bold green")
        table.add_column("#", width=4)
        table.add_column("Modo")
        table.add_column("Descripción")
        
        table.add_row("1", "TUI Legacy", "Interfaz de terminal clásica")
        table.add_row("2", "Web Modern", "Dashboard en Navegador (localhost:8000)")
        table.add_row("3", "Hybrid (Recomendado)", "Servidor Web + Control TUI")
        
        self.console.print(table)
        while True:
            choice = self.console.input("[bold yellow]Opción [/]: ")
            if choice.strip() in ['1', '2', '3']:
                return int(choice.strip())
            self.console.print("[red]Opción inválida.[/]")

    def run(self):
        # 1. Selector de modelo
        self.select_model()
        
        # 2. Selector de Interfaz (Launcher)
        mode = self.select_interface()

        # 3. Start Core System
        # Esto cargará 'chat' (con el modelo seleccionado) y 'reflexion' (Ollama)
        self.orchestrator.start()

        # Configuración según modo
        if mode == 1: # TUI ONLY
             self._run_tui()
        elif mode == 2: # WEB ONLY
             self._run_web(open_browser=True)
             # Bucle infinito para mantener vivo (CLI actúa como log server)
             self.console.print("[bold green]Web Server Running... Press Ctrl+C to stop.[/]")
             try:
                 while True: time.sleep(1)
             except KeyboardInterrupt: pass
        elif mode == 3: # HYBRID
             self._run_web(open_browser=True)
             self._run_tui()

    def _run_web(self, open_browser=False):
        """Lanza el servidor web en un hilo aparte"""
        try:
            from server.api import start_server
            import webbrowser
            
            # Start Server Thread
            t = threading.Thread(target=start_server, args=(self.orchestrator,), kwargs={"port": 8000}, daemon=True)
            t.start()
            
            if open_browser:
                time.sleep(2) # Give it a moment
                webbrowser.open("http://localhost:8000")
                
            self.console.print("[bold green]Web Server Online at http://localhost:8000[/]")
        except Exception as e:
            self.console.print(f"[red]Error starting Web Server: {e}[/]")

    def _run_tui(self):
        """Lanza el bucle TUI (Rich Live)"""
        # Hook para logs del orquestador si queremos que se impriman en TUI
        # En modo TUI, el orquestador ya escribe a sus logs y la TUI los lee (polling)
        # Así que no necesitamos callback extra, salvo para notificaciones
        
        layout = self.setup_layout()
        self.log_chat("SYS", "Conectando al Núcleo ARAFURA...", "cyan")
        self.log_chat("SYS", "Sistema Online.", "green")
        self.update_layout(layout)
        
        # Live Loop
        with Live(layout, refresh_per_second=10, screen=True) as live:
            while True:
                self.update_layout(layout)
                
                # Check input
                for _ in range(10):
                    self.input.check_input()
                    try:
                        cmd = self.input.ready_commands.get_nowait()
                        if not self.process_command(cmd):
                            return 
                    except queue.Empty:
                        pass
                    time.sleep(0.005)

if __name__ == "__main__":
    app = ArafuraCortex()
    app.run()
