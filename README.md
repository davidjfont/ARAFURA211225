# ARAFURA — Governed Cognitive Infrastructure (v5.1)

> **Sistema de Cognición Multimodal | Capa RAG Corporativa | Gobernanza & Autonomía (SIMA)**

```
 ╔═══════════════════════════════════════════════════════════════╗
 ║                         ARAFURA                               ║
 ║           RAG Corporativo × Visión Pro × Gobernanza           ║
 ║                                                               ║
 ║   "I don't just act on what I see; I act on what I know."     ║
 ╚═══════════════════════════════════════════════════════════════╝
```

## 🧭 ¿Qué es ARAFURA v5.1?

**ARAFURA** ha evolucionado de un agente reactivo a una **Infraestructura de Conocimiento Gobernada**. Esta versión se centra en la escalabilidad empresarial y el aprendizaje estructurado:

*   **🧠 Capa RAG Corporativa**: Estructura de conocimiento en Markdown (.md) organizada por empresas, principios globales y experiencias tácticas.
*   **⚖️ Gobernanza MD**: Sistema de "fuentes de verdad" inmutables. ARAFURA consulta sus principios de seguridad y workflows corporativos antes de cada acción crítica.
*   **🛡️ Conflict Protocol**: Mecanismo de seguridad que detiene el sistema si el conocimiento histórico (RAG) choca con la realidad visual actual.
*   **🎯 Tactical Panel v5.1**: Interfaz web optimizada con botones reactivos, visión de precisión (Lupa) y un overlay de autonomía que no obstruye la visión del Cortex.

---

## 🏗️ Arquitectura de Conocimiento (RAG)

El sistema utiliza una capa de RAG gobernada para asegurar la alineación con los objetivos humanos:

```mermaid
graph TD
    RAG[RAG Layer] --> Global[Global Principles]
    RAG --> Companies[Company Workflows]
    RAG --> Experiences[Learning Experiences]
    
    Orchestrator[⚡ Orchestrator] <--> RAG_Manager[RAG Manager]
    RAG_Manager -->|Context Query| RAG
    
    Orchestrator -->|Safety Check| Global
    Orchestrator -->|Domain Context| Companies
    
    Visual[Visual Cortex] -->|Conflict?| Orchestrator
    Orchestrator -->|Archive| Experiences
```

---

## 🚀 Quick Start

### Requisitos
*   **Python 3.10+**
*   **Ollama** instalado y corriendo (`ollama serve`).
*   Modelos recomendados: `deepseek-r1`, `llava`, `mistral`.

### Instalación & Ejecución
1. Clonar y configurar entorno: `python -m venv venv && .\venv\Scripts\activate`
2. Instalar dependencias: `pip install -r requirements.txt`
3. Lanzar arquitectura híbrida: `python terminals/cli/arafura_cli.py` (Opción 3).

---

## 👁️ Control Táctico y Autonomía

ARAFURA implementa una interfaz de control de misión avanzada con lógica de estados jerárquica:

### 🕹️ Funcionalidad de Controles

| Icono | Botón | Función Principal | Comportamiento Técnico |
| :--- | :--- | :--- | :--- |
| 👁️ | **Visión** | **"Abrir los ojos"** | Activa el pipeline de percepción (`VisionPipeline`). El sistema empieza a capturar y "entender" lo que sucede en pantalla en tiempo real (5 FPS), pero **no realiza ninguna acción**. Es un modo pasivo/observador. Inyecta el contexto visual en el chat. |
| 🤖 | **Autonomía** | **"Activar las manos"** | Inicia el bucle de agencia (`active_window` + `mouse/keyboard`). El sistema empieza a **ejecutar acciones** por sí mismo. Por defecto funciona en ciclos de **60 segundos** (timer visible en el botón). *Nota: Activa automáticamente el modo Visión.* |
| 🎮 | **Gamer** | **"Modo Competitivo"** | Cambia la personalidad del sistema (`arafura_gamer.md`) a una más agresiva y enfocada en objetivos rápidos. **Fuerza el modo Visión** y prioriza la velocidad de reacción sobre la reflexión profunda. |
| 🛑 | **STOP** | **"Kill Switch"** | Detiene **inmediatamente** cualquier bucle autónomo, cancela hilos de ejecución pendientes y devuelve el sistema al modo seguro (`CHAT`). Resetea la interfaz visual localmente. |

### 🔗 Sinergia y Jerarquía

El sistema opera bajo una **Jerarquía de Modos** interna: `AUTONOMÍA > GAMER > VISIÓN > CHAT`

1.  **Visión + Autonomía**: Son complementarios. No puedes tener Autonomía sin Visión (el botón 🤖 encenderá automáticamente el 👁️ si está apagado). Sin embargo, puedes tener Visión sin Autonomía (para que el bot te ayude o comente sin tomar el control).
2.  **Autonomía + Gamer**: Es la combinación más "letal". El sistema actúa por su cuenta (🤖) pero utilizando su personalidad competitiva y reglas de decisión rápida (🎮). Ideal para juegos o trading de alta frecuencia.
3.  **El Botón Rojo (STOP)**: Es el "Jefe". Anula cualquier combinación activa. Si estás en *Gamer + Autonomía* y pulsas 🛑, ambos se apagan y vuelves a ser un simple chat de texto.
---

## ⌨️ Comandos RAG y Operación

### Comandos de Sistema

| Comando | Función |
| :--- | :--- |
| `/actua [s]` | Lanza autonomía por N segundos. Ahora consulta el RAG para buscar guías. |
| `/leer <file>` | Carga documentos temporales en memoria. |
| `/mode [chat/vision]` | Cambia el estado cognitivo (Sincronizado con UI Web). |

### Governanza de Datos (`core/rag/`)

*   **Global**: Principios básicos de ética y seguridad (inmutables por la IA).
*   **Companies**: Workflows específicos por cliente (ej: `companies/fdfont/workflows.md`).
*   **Experiences**: Almacén de aprendizajes, sugerencias y patrones de error detectados.

---

## 📜 Filosofía v5.1 "Human-in-the-Loop"

Ninguna acción estructural se ejecuta sin revisión humana. El RAG de ARAFURA es **consultivo**, no ejecutivo. La realidad visual del **Cortex** es la verdad primordial, y la ética de los **Principios MD** es la guía absoluta.

> *"We act safely on what we know."* - ARAFURA v5.1
