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
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
    echo [OK] Entorno activado
) else (
    echo [!] No se pudo activar el entorno virtual
)

REM Instalar dependencias
if exist "terminals\cli\requirements.txt" (
    echo [*] Instalando dependencias...
    pip install -r "terminals\cli\requirements.txt" -q
    echo [OK] Dependencias instaladas
) else (
    echo [!] requirements.txt no encontrado - saltando
)

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
echo.
set /p choice="Elige opcion (1/2): "

if "%choice%"=="1" (
    echo.
    echo [*] Iniciando ARAFURA CLI...
    echo.
    python "terminals\cli\arafura_cli.py"
)

echo.
echo Entorno virtual activo. Usa 'deactivate' para salir.
echo Directorio: "%CD%"
cmd /k
