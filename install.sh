#!/bin/bash
set -e

# ============================================
#  poeHal - Instalador para Debian / Ubuntu / RevPi
#  PLANET IGS-4215-8UP2T2S PoE++ CLI Tool + libreria
#  Requiere: Python 3.8 - 3.11
# ============================================

APP_NAME="poeHal"
CONFIG_DIR="/etc/$APP_NAME"
CONFIG_FILE="$CONFIG_DIR/config.ini"
CONFIG_EXAMPLE="config.ini.example"

# Restos de la instalacion vieja (venv en /opt + wrapper)
OLD_APP_DIR="/opt/$APP_NAME"
OLD_BIN_LINK="/usr/local/bin/$APP_NAME"

echo ""
echo "========================================"
echo "  Instalando $APP_NAME"
echo "  CLI + libreria Python"
echo "========================================"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Ejecuta el instalador con sudo:"
    echo "        sudo ./install.sh"
    exit 1
fi

if [ ! -f "pyproject.toml" ] || [ ! -d "$APP_NAME" ]; then
    echo "[ERROR] Ejecuta este script desde la carpeta del proyecto."
    exit 1
fi

if [ ! -f "$CONFIG_EXAMPLE" ]; then
    echo "[ERROR] No se encontro $CONFIG_EXAMPLE en el directorio actual."
    exit 1
fi

# --- Usuario destino: el paquete se instala en SU home, no en /root ---
TARGET_USER="${SUDO_USER:-$USER}"
if [ "$TARGET_USER" = "root" ]; then
    echo "[AVISO] No se detecto SUDO_USER: se instalara para root."
    echo "        Si querias instalarlo para tu usuario, corre:"
    echo "          sudo -u root true; sudo ./install.sh   # desde tu sesion normal"
fi
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
echo "[1/6] Usuario destino: $TARGET_USER  ($TARGET_HOME)"

# ==============================================================
# PASO 2: Python 3.8 - 3.11
#   pysnmp 4.4.12 importa asyncore, removido en Python 3.12.
#   Aceptar 3.12+ produce una instalacion que no arranca.
# ==============================================================
find_python() {
    for cmd in python3.11 python3.10 python3.9 python3.8 python3; do
        if command -v "$cmd" > /dev/null 2>&1; then
            ver=$("$cmd" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) || continue
            major=${ver%%.*}
            minor=${ver##*.}
            if [ "$major" -eq 3 ] && [ "$minor" -ge 8 ] && [ "$minor" -le 11 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

echo "[2/6] Buscando Python 3.8 - 3.11..."
PYTHON_CMD=$(find_python) || PYTHON_CMD=""

if [ -z "$PYTHON_CMD" ]; then
    echo "       No encontrado. Instalando python3.11..."
    apt update -qq
    apt install -y python3.11 python3.11-venv > /dev/null 2>&1 || true
    PYTHON_CMD=$(find_python) || PYTHON_CMD=""
fi

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo "[ERROR] No hay un Python compatible (3.8 - 3.11)."
    echo "        pysnmp 4.4.12 no funciona en Python 3.12+ porque importa"
    echo "        asyncore, que fue removido del lenguaje."
    echo "        Instala python3.11 y vuelve a ejecutar."
    exit 1
fi
echo "       $("$PYTHON_CMD" --version 2>&1) ($PYTHON_CMD)"

# --- Dependencias del sistema ---
echo "[3/6] Instalando dependencias del sistema..."
apt install -y snmp python3-pip > /dev/null 2>&1 || \
apt install -y snmp > /dev/null 2>&1 || true
echo "       OK"

# --- Limpiar la instalacion vieja (venv en /opt + wrapper) ---
echo "[4/6] Limpiando instalacion anterior..."
CLEANED=0
if [ -f "$OLD_BIN_LINK" ]; then rm -f "$OLD_BIN_LINK"; CLEANED=1; fi
if [ -d "$OLD_APP_DIR" ]; then rm -rf "$OLD_APP_DIR"; CLEANED=1; fi
if [ "$CLEANED" -eq 1 ]; then
    echo "       Removidos $OLD_BIN_LINK y $OLD_APP_DIR"
else
    echo "       Nada que limpiar"
fi

# ==============================================================
# PASO 5: Instalar el paquete en el home del usuario
#   --user      -> escribe solo en ~/.local, no toca el sistema
#   --break-system-packages -> Debian marca su Python como
#                              externally-managed (PEP 668) y bloquea pip
#                              incluso con --user. Con --user el flag no
#                              toca nada fuera de ~/.local.
#   sudo -u     -> sin esto, --user instalaria en /root/.local
# ==============================================================
echo "[5/6] Instalando el paquete para $TARGET_USER..."
PIP_ARGS="--user --upgrade"
if "$PYTHON_CMD" -m pip install --help 2>/dev/null | grep -q "break-system-packages"; then
    PIP_ARGS="$PIP_ARGS --break-system-packages"
fi

sudo -u "$TARGET_USER" "$PYTHON_CMD" -m pip install $PIP_ARGS . > /tmp/poehal-pip.log 2>&1 || {
    echo ""
    echo "[ERROR] Fallo la instalacion del paquete. Ultimas lineas:"
    tail -15 /tmp/poehal-pip.log
    exit 1
}
echo "       OK"

# --- Configuracion protegida (credenciales fuera del repositorio) ---
echo "[6/6] Configurando credenciales en $CONFIG_FILE..."
mkdir -p "$CONFIG_DIR"
chmod 755 "$CONFIG_DIR"

CONFIG_IS_NEW=""
if [ -f "$CONFIG_FILE" ]; then
    echo "       Configuracion existente conservada (no se sobreescribe)."
else
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    CONFIG_IS_NEW=1
fi

# El archivo lo lee poeHal corriendo como $TARGET_USER, asi que le pertenece.
# Modo 600: nadie mas puede leer el password.
chown "$TARGET_USER":"$TARGET_USER" "$CONFIG_FILE" 2>/dev/null || true
chmod 600 "$CONFIG_FILE"
echo "       OK (modo 600, dueño $TARGET_USER)"

# --- Verificaciones finales ---
BIN_DIR="$TARGET_HOME/.local/bin"
PATH_OK=1
sudo -u "$TARGET_USER" bash -lc 'command -v poeHal' > /dev/null 2>&1 || PATH_OK=0

echo ""
echo "========================================"
echo "  Instalacion completada!"
echo "========================================"
echo ""
echo "  Python:  $("$PYTHON_CMD" --version 2>&1)"
echo "  Usuario: $TARGET_USER"
echo "  Config:  $CONFIG_FILE (modo 600)"
echo ""

if [ "$PATH_OK" -eq 0 ]; then
    echo "  ----------------------------------------"
    echo "   AVISO: $BIN_DIR no esta en el PATH."
    echo "   Agregalo con:"
    echo ""
    echo "     echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "     source ~/.bashrc"
    echo "  ----------------------------------------"
    echo ""
fi

if [ -n "$CONFIG_IS_NEW" ]; then
    echo "  ----------------------------------------"
    echo "   ACCION REQUERIDA antes de usar poeHal:"
    echo "   Edita las credenciales del switch:"
    echo ""
    echo "     nano $CONFIG_FILE"
    echo "  ----------------------------------------"
    echo ""
fi

echo "  CLI:"
echo "    poeHal help"
echo "    poeHal -r status"
echo ""
echo "  Libreria:"
echo "    python3 -c 'import poeHal as hal; print(hal.status())'"
echo ""
echo "  Desinstalar:  sudo ./uninstall.sh"
echo ""
