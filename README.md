# ARAFURA — Neural-Visual Cognitive Infrastructure (v3.3)

> **Sistema de Cognición Multimodal | Persistente & Autónomo (SIMA)**

```
╔═══════════════════════════════════════════════════════════════╗
║                         ARAFURA                               ║
║           Cognición Visual × Autonomía × Persistencia         ║
║                                                               ║
║   "I don't just process text. I see, I think, I act."         ║
╚═══════════════════════════════════════════════════════════════╝
```

## 🧭 ¿Qué es ARAFURA v3?

**ARAFURA** ha evolucionado de un sistema narrativo a una **Entidad Cognitiva Multimodal**. Ya no es solo texto; ahora posee:

*   **Cortex Visual (Llava)**: Capacidad de ver e interpretar pantallas en tiempo real (4K resolution context).
*   **Orquestador Autónomo (SIMA)**: Un bucle de vida que observa, decide y actúa sin esperar órdenes.
*   **Interfaz Híbrida**: Una UI Web moderna "Glassmorphism" conectada a un cerebro terminal robusto.

---

## 🏗️ Arquitectura del Sistema

El sistema utiliza una arquitectura modular basada en **Roles Cognitivos**:

```mermaid
graph TD
    User([Usuario]) <--> WebUI[Web Interface (Glass)]
    User <--> CLI[Terminal CLI]
    
    WebUI <--> Server[FastAPI Server]
    CLI <--> Orchestrator[⚡ ORCHESTRATOR (Cerebro)]
    Server <--> Orchestrator
    
    subgraph "Frontal Cortex"
        Orchestrator -->|Manage| Memory[Memory Manager (JSONL)]
        Orchestrator -->|Control| Autonomy[SIMA Loop (Autonomy)]
    end
    
    subgraph "Neural Pathways (Router)"
        Orchestrator --> Router{Model Router}
        Router -->|Chat| Mistral[Mistral 7B (Chat)]
        Router -->|Vision| Llava[Llava 1.6 (Vision)]
        Router -->|Thinking| Phi[Phi-2 (Reflexion)]
        Router -->|Reasoning| DeepSeek[DeepSeek R1 (Logic)]
    end
    
    Autonomy -->|Capture| Screen[Screen Capture]
    Autonomy -->|Action| Input[Mouse/Keyboard]
```

---

## 🚀 Quick Start

### Requisitos
*   **Python 3.10+**
*   **Ollama** instalado y corriendo (`ollama serve`).
*   Modelos necesarios: `ollama pull mistral`, `ollama pull phi`, `ollama pull llava`.

### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/[user]/ARAFURA.git
cd ARAFURA

# 2. Entorno Virtual
python -m venv venv
.\venv\Scripts\activate

# 3. Instalar dependencias
pip install -r terminals/cli/requirements.txt
```

### Ejecución (Launcher)

Ejecuta el launcher maestro para elegir tu modo:

```bash
python terminals/cli/arafura_cli.py
```

Selecciona **Opción 3 (Hybrid Mode)** para la experiencia completa:
*   Abre el servidor en segundo plano.
*   Lanza la Web UI en `http://localhost:8000`.
*   Mantiene control total desde la terminal.

---

## 👁️ Guía de Visión y Autonomía (SIMA)

ARAFURA implementa el paradigma **SIMA** (Scalable Instructable Multiworld Agent).

### 1. Activar la Visión
Para conectar el ojo de ARAFURA a una ventana:

1.  Lista las ventanas visibles:
    ```bash
    /ventana
    ```
2.  Conéctate a una (ej. Google Chrome):
    ```bash
    /ventana 1
    ```
    *(Esto activa automáticamente el **Modo Visión**)*.

### 2. Live Feed & Neural Pulse
*   Mira la **Web UI**. Verás el panel "Visual Cortex" actualizándose cada 15 segundos.
*   Cuando ARAFURA piensa, verás un **Neural Pulse** (onda violeta) indicando procesamiento cognitivo.

### 3. Autonomía (SIMA Loop)
En modo visión, ARAFURA entra en un bucle autónomo:
1.  **Observa**: Captura la pantalla.
2.  **Evalúa**: Busca señales de prosperidad o riesgo.
3.  **Actúa**: Si está autorizado, ejecuta acciones (`[[ACTION: click...]]`).

Logs autónomos aparecerán con el prefijo `[SIMA]` en el panel visual.

---

## ⌨️ Comandos de Sistema

### Modos de Operación

| Comando | Función |
| :--- | :--- |
| `/mode chat` | Modo CHAT - Conversación textual estándar. |
| `/mode vision` | Modo VISIÓN - Captura y análisis de pantalla. |
| `/gamer` | 🎮 **MODO GAMER** - Jugadora competitiva agresiva. Loop 3s, detección de botones, tracking de puntuaciones. |
| `/actua [segundos]` | 🤖 **AUTONOMÍA DUAL-BRAIN** - LLaVA 👁️ + DeepSeek 🧠 trabajando juntos. |
| `/actua stop` | Detener autonomía inmediatamente. |

### Herramientas de Visión

| Comando | Función |
| :--- | :--- |
| `/ventana` | Lista ventanas disponibles para visión. |
| `/ventana <N>` | Conecta visión a la ventana N y activa Modo Visión automáticamente. |
| `/cortex <instrucción>` | Comando directo al Cortex Visual (ej: `/cortex click the Buy button`). |

### Utilidades

| Comando | Función |
| :--- | :--- |
| `/status` | Muestra métricas de Equidad y Prosperidad. |
| `/leer <archivo>` | Carga un archivo de texto en la memoria de corto plazo. |
| `/ayuda` o `/help` | Muestra ayuda de comandos. |
| `/salir` o `salir` | Detiene el bucle autónomo y cierra el sistema. |

### Sintaxis de Acciones (Autónomas)

Estas acciones son ejecutadas por el agente visual o pueden incluirse en respuestas del modelo:

```
[[ACTION: click X, Y]]         # Click en coordenadas
[[ACTION: doubleclick X, Y]]   # Doble click
[[ACTION: type TEXTO]]         # Escribe texto
[[ACTION: key TECLA]]          # Presiona tecla (enter, space, up, down, left, right, tab, esc)
[[ACTION: hotkey ctrl c]]      # Combinación de teclas (ctrl+c, shift+space, alt+tab)
[[ACTION: scroll up]]          # Scroll arriba (también: down, o número como 500)
[[ACTION: drag X1 Y1 X2 Y2]]   # Arrastrar desde (X1,Y1) hasta (X2,Y2)
[[ACTION: move X, Y]]          # Mover ratón sin click
[[ACTION: wait 3]]             # Esperar N segundos
```

### 🎮 GAMER MODE (Nuevo)

Cuando `/gamer` está activo, ARAFURA se transforma en una **jugadora competitiva**:

- **Loop acelerado**: 3 segundos (vs 15s normal)
- **Detección de botones**: Escanea TODOS los elementos clickeables
- **Tracking de scores**: Celebra 🎉 mejoras, advierte ⚠️ pérdidas
- **Badge UI**: Muestra "GAMER 🎮" en la interfaz

```bash
# Ejemplo de uso
/ventana          # Ver ventanas disponibles
/ventana 0        # Seleccionar ventana objetivo
/gamer            # ¡ACTIVAR MODO GAMER!
```

---

## 📂 Logs y Memoria

Toda interacción (Chat, Visión, Pensamientos) se guarda permanentemente en:
`sessions/session_YYYY-MM-DD.jsonl`

Esto permite re-entrenar o analizar la evolución del sistema posteriormente.

---

## 📜 Licencia & Filosofía

Proyecto bajo licencia **AGPLv3**.
Construido sobre la creencia de que la IA debe ser una **extensión cognitiva**, no una caja negra cerrada.

> *"We act on what we see."* - ARAFURA Core
