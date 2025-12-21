# Guía de Instalación — ARAFURA Portable

> Cómo instalar y ejecutar ARAFURA en cualquier sistema

## Requisitos Mínimos

- Python 3.10+
- Git (opcional, para clonar)
- 100MB de espacio libre
- Conexión a internet (para APIs externas, opcional)

## Opciones de Instalación

### Opción 1: Pendrive / USB (Máxima Portabilidad)

```bash
# 1. Clonar directamente al pendrive
git clone https://github.com/[tu-usuario]/ARAFURA.git E:\ARAFURA

# 2. Navegar al directorio
cd E:\ARAFURA

# 3. Ejecutar script de inicialización
# Windows:
.\scripts\init.bat

# Linux/Mac:
chmod +x ./scripts/init.sh && ./scripts/init.sh
```

### Opción 2: Instalación Local

```bash
# 1. Clonar
git clone https://github.com/[tu-usuario]/ARAFURA.git
cd ARAFURA

# 2. Crear entorno virtual (recomendado)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r terminals/cli/requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus claves API
```

### Opción 3: Docker (Aislamiento total)

```bash
# Próximamente
docker compose up -d
```

## Configuración

### Variables de Entorno (.env)

```
# API Keys (opcional, para potencia)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Modelo local (sin internet)
LOCAL_MODEL=ollama/mistral

# Modo
ARAFURA_MODE=portable  # o 'server'
```

## Uso Básico

### CLI Local

```bash
python terminals/cli/arafura_cli.py
```

### Como Agente en otro proyecto

```python
from arafura import load_identity

identity = load_identity("arafura_identity.json")
# Usar identity.system_prompt con tu LLM
```

## Verificación

Después de instalar, verifica que todo funciona:

```bash
# Verificar estructura
python -c "import json; print(json.load(open('arafura_identity.json'))['entity']['name'])"
# Output esperado: Arafura

# Verificar YAML
python -c "import yaml; print(yaml.safe_load(open('core/agents/arafura.yaml'))['agent_id'])"
# Output esperado: arafura
```

## Actualización

```bash
git pull origin main
```

## Backup a IPFS

```bash
./scripts/backup_to_ipfs.sh
```

---

*Para más información, consulta ARQUITECTURA_ARAFURA_v1.md*
