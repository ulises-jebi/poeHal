"""Carga de configuracion y credenciales.

Las credenciales nunca viven en el codigo. Ver config.ini.example.
"""

import configparser
import os
import stat

from .errors import ConfigError

# ==============================================================
# CONFIGURACION
# --------------------------------------------------------------
# Las credenciales nunca viven en el codigo. Se buscan, en orden:
#   1. $POEHAL_CONFIG            (ruta explicita)
#   2. ~/.config/poeHal/config.ini
#   3. /etc/poeHal/config.ini    (instalacion estandar)
# Las variables de entorno POEHAL_* sobreescriben cualquier archivo.
# ==============================================================
DEFAULT_CONFIG = {
    "host":       "192.168.1.103",
    "snmp_port":  161,
    "community":  "public",
    "timeout":    5,
    "retries":    2,
    "web_user":   "",
    "web_pass":   "",
}

CONFIG_PATHS = [
    os.environ.get("POEHAL_CONFIG"),
    os.path.expanduser("~/.config/poeHal/config.ini"),
    "/etc/poeHal/config.ini",
]

ENV_OVERRIDES = {
    "host":      "POEHAL_HOST",
    "community": "POEHAL_COMMUNITY",
    "web_user":  "POEHAL_USER",
    "web_pass":  "POEHAL_PASS",
}

ETC_CONFIG_DIR = "/etc/poeHal"

CONFIG_SOURCE = None
CONFIG_ERROR = None
CONFIG_HINT = None


def check_permissions(path):
    """Devuelve un mensaje de error si el archivo es legible por otros."""
    mode = os.stat(path).st_mode
    if mode & 0o077:
        return ("Permisos inseguros en " + path + " ("
                + oct(stat.S_IMODE(mode)) + "): legible por otros usuarios."
                + "\n          Corrige con:  sudo chmod 600 " + path)
    return None


def load_config():
    """Carga la configuracion sin abortar: los errores quedan en CONFIG_ERROR
    para que 'poeHal help' siga funcionando sin credenciales."""
    global CONFIG_SOURCE, CONFIG_ERROR, CONFIG_HINT
    cfg = dict(DEFAULT_CONFIG)

    for path in CONFIG_PATHS:
        if not path or not os.path.isfile(path):
            continue
        if not os.access(path, os.R_OK):
            # configparser ignora en silencio lo que no puede abrir: avisar.
            CONFIG_HINT = ("El archivo " + path + " existe pero el usuario "
                           + "actual no puede leerlo.\n"
                           + "  Ejecuta el comando con sudo, o dale acceso a "
                           + "tu usuario (ver README).")
            continue
        problem = check_permissions(path)
        if problem:
            CONFIG_ERROR = problem
            break
        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error as e:
            CONFIG_ERROR = "No se pudo leer " + path + ": " + str(e)
            break
        if parser.has_section("switch"):
            for key in DEFAULT_CONFIG:
                if parser.has_option("switch", key):
                    cfg[key] = parser.get("switch", key)
        CONFIG_SOURCE = path
        break

    for key, env_name in ENV_OVERRIDES.items():
        val = os.environ.get(env_name)
        if val:
            cfg[key] = val
            if not CONFIG_SOURCE:
                CONFIG_SOURCE = "variables de entorno POEHAL_*"

    if not CONFIG_SOURCE and not CONFIG_HINT:
        if (os.path.isdir(ETC_CONFIG_DIR)
                and not os.access(ETC_CONFIG_DIR, os.R_OK | os.X_OK)):
            CONFIG_HINT = (ETC_CONFIG_DIR + " existe pero solo root puede "
                           + "entrar.\n  Ejecuta el comando con sudo, o dale "
                           + "acceso a tu usuario (ver README).")

    for key in ("snmp_port", "timeout", "retries"):
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            cfg[key] = DEFAULT_CONFIG[key]

    return cfg


SWITCH_CONFIG = load_config()



def credentials_problem():
    """Devuelve un mensaje explicando por que no hay credenciales usables,
    o None si todo esta en orden. No imprime ni termina el proceso."""
    if CONFIG_ERROR:
        return CONFIG_ERROR
    if SWITCH_CONFIG["web_user"] and SWITCH_CONFIG["web_pass"]:
        return None

    target = "/etc/poeHal/config.ini"
    # La plantilla vive junto al paquete, no en el directorio actual.
    example = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config.ini.example")

    lines = ["No hay credenciales configuradas para el switch.", ""]
    if CONFIG_HINT:
        lines += ["  AVISO: " + CONFIG_HINT, ""]
    lines += ["  Opcion A - archivo de configuracion (recomendado):",
              "    sudo mkdir -p /etc/poeHal"]
    if os.path.isfile(example):
        lines.append("    sudo cp " + example + " " + target)
    else:
        lines += ["    sudo tee " + target + " > /dev/null <<'EOF'",
                  "    [switch]",
                  "    host      = " + SWITCH_CONFIG["host"],
                  "    community = " + SWITCH_CONFIG["community"],
                  "    web_user  = tu-usuario",
                  "    web_pass  = tu-password",
                  "    EOF"]
    lines += ["    sudo chmod 600 " + target,
              "    sudo nano " + target,
              "",
              "  Opcion B - variables de entorno:",
              "    export POEHAL_USER='tu-usuario'",
              "    export POEHAL_PASS='tu-password'"]
    return "\n".join(lines)


def require_credentials():
    """Lanza ConfigError si no hay credenciales utilizables."""
    problem = credentials_problem()
    if problem:
        raise ConfigError(problem)
