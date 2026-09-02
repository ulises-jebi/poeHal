#!/bin/bash
set -e

# ============================================
#  poeHal - Desinstalador
# ============================================

APP_NAME="poeHal"
CONFIG_DIR="/etc/$APP_NAME"
CONFIG_FILE="$CONFIG_DIR/config.ini"
OLD_APP_DIR="/opt/$APP_NAME"
OLD_BIN_LINK="/usr/local/bin/$APP_NAME"

echo ""
echo "========================================"
echo "  Desinstalando $APP_NAME"
echo "========================================"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Ejecuta con sudo:"
    echo "        sudo ./uninstall.sh"
    exit 1
fi

TARGET_USER="${SUDO_USER:-$USER}"

# --- Paquete pip del usuario ---
PIP_ARGS=""
if python3 -m pip uninstall --help 2>/dev/null | grep -q "break-system-packages"; then
    PIP_ARGS="--break-system-packages"
fi

if sudo -u "$TARGET_USER" python3 -m pip uninstall -y $PIP_ARGS "$APP_NAME" > /dev/null 2>&1; then
    echo "[1/3] Paquete '$APP_NAME' desinstalado de $TARGET_USER"
else
    echo "[1/3] Paquete '$APP_NAME' no estaba instalado para $TARGET_USER"
fi

# --- Restos de la instalacion vieja (venv en /opt + wrapper) ---
CLEANED=0
if [ -f "$OLD_BIN_LINK" ]; then rm -f "$OLD_BIN_LINK"; CLEANED=1; fi
if [ -d "$OLD_APP_DIR" ]; then rm -rf "$OLD_APP_DIR"; CLEANED=1; fi
if [ "$CLEANED" -eq 1 ]; then
    echo "[2/3] Instalacion antigua removida ($OLD_APP_DIR, $OLD_BIN_LINK)"
else
    echo "[2/3] Sin restos de instalaciones antiguas"
fi

echo "[3/3] Listo"
echo ""

# --- Configuracion: no se borra sola porque contiene credenciales ---
if [ -f "$CONFIG_FILE" ]; then
    echo "  NOTA: la configuracion con las credenciales del switch"
    echo "        NO se elimino automaticamente:"
    echo ""
    echo "          $CONFIG_FILE"
    echo ""
    echo "        Para borrarla tambien:"
    echo "          sudo rm -rf $CONFIG_DIR"
    echo ""
fi
