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
echo Demo de consola terminada. Presiona una tecla para abrir el
echo panel operativo en el navegador ^(Ctrl+C aqui para salir sin
echo abrirlo^).
pause >nul

echo.
echo [5/5] Abriendo el panel operativo...
echo        En la pestana "Leads que llegan" dale a "Cargar leads
echo        por defecto" para sembrar el CRM en vivo.
echo        Para cerrar el panel: Ctrl+C en esta ventana.
echo ------------------------------------------------------------
streamlit run streamlit_app.py

endlocal
