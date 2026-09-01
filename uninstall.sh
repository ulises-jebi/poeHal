#!/bin/bash
set -e

# ============================================
#  poeHal - Desinstalador
#  PLANET IGS-4215-8UP2T2S PoE++ CLI Tool
# ============================================

APP_NAME="poeHal"
APP_DIR="/opt/$APP_NAME"
BIN_LINK="/usr/local/bin/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"
CONFIG_FILE="$CONFIG_DIR/config.ini"

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

# --- Eliminar comando global ---
if [ -f "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    echo "[1/2] Comando '$APP_NAME' eliminado de PATH"
else
    echo "[1/2] Comando '$APP_NAME' no encontrado (ya removido)"
fi

# --- Eliminar directorio de instalacion ---
if [ -d "$APP_DIR" ]; then
    rm -rf "$APP_DIR"
    echo "[2/2] Directorio $APP_DIR eliminado"
else
    echo "[2/2] Directorio $APP_DIR no encontrado (ya removido)"
fi

echo ""
echo "  $APP_NAME desinstalado."
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
