#!/data/data/com.termux/files/usr/bin/bash

# ============================================================
# EJECUTOR DEL AGENTE DE NOTICIAS
# Termux + Python venv + Ollama
# ============================================================

PROJECT_DIR="$HOME/noticias-linux"
VENV_DIR="$PROJECT_DIR/.venv"
SCRIPT="$PROJECT_DIR/noticias_linux.py"
LOG_DIR="$PROJECT_DIR/logs"
LOCK_DIR="$PROJECT_DIR/.run_noticias.lock"

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/noticias_$(date '+%Y-%m-%d').log"


# ------------------------------------------------------------
# Evitar ejecuciones simultáneas
# ------------------------------------------------------------

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ya existe una ejecución activa." >> "$LOG_FILE"
    exit 1
fi


# ------------------------------------------------------------
# Limpieza al terminar
# ------------------------------------------------------------

cleanup() {
    if type deactivate >/dev/null 2>&1; then
        deactivate || true
    fi

    rm -rf "$LOCK_DIR"
}

trap cleanup EXIT INT TERM


# ------------------------------------------------------------
# Log
# ------------------------------------------------------------

exec >> "$LOG_FILE" 2>&1

echo
echo "============================================================"
echo "INICIO: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"


# ------------------------------------------------------------
# Validaciones
# ------------------------------------------------------------

if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: No existe $PROJECT_DIR"
    exit 1
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "ERROR: No existe el entorno virtual:"
    echo "$VENV_DIR"
    exit 1
fi

if [ ! -f "$SCRIPT" ]; then
    echo "ERROR: No existe:"
    echo "$SCRIPT"
    exit 1
fi


# ------------------------------------------------------------
# Entrar al proyecto
# ------------------------------------------------------------

cd "$PROJECT_DIR" || exit 1


# ------------------------------------------------------------
# Activar venv
# ------------------------------------------------------------

source "$VENV_DIR/bin/activate"

echo "[+] Python:"
which python

echo "[+] Versión:"
python --version


# ------------------------------------------------------------
# Comprobar Ollama
# ------------------------------------------------------------

if curl -fsS \
    --connect-timeout 5 \
    http://127.0.0.1:11434/api/tags \
    >/dev/null 2>&1
then
    echo "[+] Ollama disponible"
else
    echo "[-] ERROR: Ollama no responde en 127.0.0.1:11434"
    exit 1
fi


# ------------------------------------------------------------
# Ejecutar agente
# ------------------------------------------------------------

echo "[+] Ejecutando noticias_linux.py..."

python "$SCRIPT"

RESULTADO=$?


# ------------------------------------------------------------
# Resultado
# ------------------------------------------------------------

if [ "$RESULTADO" -eq 0 ]; then
    echo "[+] Ejecución terminada correctamente"
else
    echo "[-] noticias_linux.py terminó con código: $RESULTADO"
fi

echo "FIN: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

exit "$RESULTADO"
