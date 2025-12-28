@echo off
REM ARAFURA - Script de Inicialización Windows
REM Uso: Ejecutar desde cualquier ubicación

echo.
echo ========================================
echo        ARAFURA - Inicializacion
echo ========================================
echo.

REM Obtener directorio del script y subir un nivel (raíz del proyecto)
pushd "%~dp0.."
echo [*] Directorio: "%CD%"

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
if not exist "venv\Scripts\python.exe" (
    echo [!] No se pudo encontrar el entorno virtual - saltando
    goto :dependencies
)

REM Manual activation to avoid activate.bat path issues with ampersands
set "VIRTUAL_ENV=%CD%\venv"
set "PATH=%VIRTUAL_ENV%\Scripts;%PATH%"
set "PYTHONHOME="
echo [OK] Entorno activado (Manual Sync)

:dependencies
REM Instalar dependencias
if not exist "terminals\cli\requirements.txt" (
    echo [!] requirements.txt no encontrado - saltando
    goto :dotenv
)

echo [*] Instalando dependencias...
pip install -r "terminals\cli\requirements.txt"
pip install pyautogui pywin32
echo [OK] Dependencias instaladas

:dotenv

REM Crear .env si no existe
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creando .env desde ejemplo...
        copy ".env.example" ".env" >nul
        echo [OK] .env creado - edita con tus claves API
    )
)

REM Crear directorio de sesiones
if not exist "sessions" (
    mkdir sessions
    echo. > "sessions\.gitkeep"
    echo [OK] Directorio sessions creado
)

echo.
echo ========================================
echo    ARAFURA inicializado correctamente
echo ========================================
echo.
echo [1] Ejecutar ARAFURA CLI
echo [2] Salir (entorno activado)
echo [3] Mapear Coordenadas (Debug Mouse)
echo.
set /p choice="Elige opcion (1-3): "

if "%choice%"=="1" (
    echo.
    echo [*] Iniciando ARAFURA CLI...
    echo.
    python "terminals\cli\arafura_cli.py"
)

if "%choice%"=="3" (
    echo.
    echo [*] Iniciando Debug Mouse...
    echo.
    python "scripts\debug_mouse.py"
)

echo.
echo Entorno virtual activo. Usa 'deactivate' para salir.
echo Directorio: "%CD%"
cmd /k
