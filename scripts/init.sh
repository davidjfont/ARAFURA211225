#!/bin/bash
# ARAFURA - Script de Inicialización Unix
# Uso: ./scripts/init.sh

echo ""
echo "========================================"
echo "       ARAFURA - Inicialización"
echo "========================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 no encontrado. Instala Python 3.10+"
    exit 1
fi
echo "[OK] Python encontrado: $(python3 --version)"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "[*] Creando entorno virtual..."
    python3 -m venv venv
    echo "[OK] Entorno virtual creado"
else
    echo "[OK] Entorno virtual ya existe"
fi

# Activar entorno
echo "[*] Activando entorno virtual..."
source venv/bin/activate

# Instalar dependencias
echo "[*] Instalando dependencias..."
pip install -r terminals/cli/requirements.txt -q
echo "[OK] Dependencias instaladas"

# Crear .env si no existe
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[*] Creando .env desde ejemplo..."
    cp .env.example .env
    echo "[OK] .env creado - edita con tus claves API"
fi

# Crear directorio de sesiones
if [ ! -d "sessions" ]; then
    mkdir -p sessions
    touch sessions/.gitkeep
    echo "[OK] Directorio sessions creado"
fi

echo ""
echo "========================================"
echo "   ARAFURA inicializado correctamente"
echo "========================================"
echo ""
echo "Para ejecutar:"
echo "  python terminals/cli/arafura_cli.py"
echo ""
echo "Para desactivar entorno:"
echo "  deactivate"
echo ""
