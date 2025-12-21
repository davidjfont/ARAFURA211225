@echo off
REM ARAFURA - Script de Inicialización Windows
REM Uso: .\scripts\init.bat

echo.
echo ========================================
echo        ARAFURA - Inicializacion
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python encontrado

REM Crear entorno virtual si no existe
if not exist "venv" (
    echo [*] Creando entorno virtual...
    python -m venv venv
    echo [OK] Entorno virtual creado
) else (
    echo [OK] Entorno virtual ya existe
)

REM Activar entorno
echo [*] Activando entorno virtual...
call venv\Scripts\activate.bat

REM Instalar dependencias
echo [*] Instalando dependencias...
pip install -r terminals\cli\requirements.txt -q
echo [OK] Dependencias instaladas

REM Crear .env si no existe
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creando .env desde ejemplo...
        copy .env.example .env >nul
        echo [OK] .env creado - edita con tus claves API
    )
)

REM Crear directorio de sesiones
if not exist "sessions" (
    mkdir sessions
    echo. > sessions\.gitkeep
    echo [OK] Directorio sessions creado
)

echo.
echo ========================================
echo    ARAFURA inicializado correctamente
echo ========================================
echo.
echo Para ejecutar:
echo   python terminals\cli\arafura_cli.py
echo.
echo Para desactivar entorno:
echo   deactivate
echo.
pause
