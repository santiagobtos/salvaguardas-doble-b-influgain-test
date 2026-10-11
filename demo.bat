@echo off
setlocal

echo ============================================================
echo  Salvaguardas Doble B x Consejeria Clara -- Demo ejecutable
echo  Prueba tecnica Influgain
echo ============================================================
echo.
echo Todo es ficticio: ni la marca, ni los leads, ni las
echo inscripciones del partner existen. Nada de esto toca un
echo sistema real.
echo.

cd /d "%~dp0"

if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo Preparando Streamlit para que no pida el email de bienvenida...
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    (
        echo [general]
        echo email = ""
    ) > "%USERPROFILE%\.streamlit\credentials.toml"
)

if not exist ".venv\Scripts\activate.bat" (
    echo [1/5] No encontre un entorno virtual, creando uno nuevo...
    python -m venv .venv
    if errorlevel 1 (
        echo No se pudo crear el entorno virtual. ^Esta Python instalado y en el PATH?
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo [2/5] Instalando dependencias ^(requirements.txt^)...
    pip install -r requirements.txt --quiet
) else (
    call .venv\Scripts\activate.bat
    echo [1/5] Entorno virtual encontrado, lo activo.
    echo [2/5] Verificando dependencias...
    pip install -r requirements.txt --quiet
)

echo.
echo [3/5] Corriendo los tests...
echo ------------------------------------------------------------
pytest -q
if errorlevel 1 (
    echo.
    echo Algo fallo en los tests. Revisa el error de arriba antes
    echo de seguir.
    pause
    exit /b 1
)

echo.
echo [4/5] Corriendo la demo completa en consola ^(Ejercicios A-B-C-D^)...
echo        Nota: esto reinicia la base de datos en vivo del panel
echo        ^(data\salvaguardas.db^), igual que indica el README.
echo ------------------------------------------------------------
python cli.py demo

echo.
echo ------------------------------------------------------------
echo Demo de consola terminada. Esos 3 leads de prueba (L901/L902/
echo L903) fueron solo para mostrar el flujo en consola -- se
echo reinicia la base antes de abrir el panel, para que el
echo evaluador arranque de cero, no con eso ya montado.
echo ------------------------------------------------------------
python -c "from src import db; db.init_db(); db.reset_db()"
ping -n 6 127.0.0.1 >nul

echo.
echo [5/5] Abriendo el panel operativo en el navegador...
echo        En la pestana "Leads que llegan" dale a "Cargar leads
echo        por defecto" para sembrar el CRM en vivo.
echo        Para cerrar el panel: Ctrl+C en esta ventana.
echo ------------------------------------------------------------
streamlit run streamlit_app.py --server.headless false

endlocal
