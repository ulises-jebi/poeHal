"""Catalogo de dispositivos y parametros.

Un solo punto de verdad: de aqui salen la API (`component`), el CLI y la
ayuda. Agregar un parametro es agregar una entrada en CUBE_PARAMETERS o
en SWITCH_PARAMETERS.

    import poeHal as hal
    from poeHal import cube1, switch, ON, OFF, STATUS, POWER

    hal.component(cube1, ON)
    hal.component(cube1, STATUS)
    hal.component(cube1, POWER)
    hal.component(switch, POWER)
"""

# ==============================================================
# DISPOSITIVOS
# --------------------------------------------------------------
# Los 5 cubos alimentados por el switch, mas el switch mismo para los
# datos agregados (potencia total, temperaturas, info del sistema).
#
# El switch PLANET tiene 8 puertos PoE, pero solo los 5 primeros
# corresponden a cubos. Los puertos 6 a 8 no se exponen aqui. Ojo: eso
# es la superficie publica; por dentro, WebPoEClient.set_port_state sigue
# reenviando la configuracion de TODOS los puertos que reporta el switch,
# porque asi lo exige su CGI. Recortar eso corromperia los puertos 6-8.
# ==============================================================
NUM_CUBES = 5

cube1 = "cube1"
cube2 = "cube2"
cube3 = "cube3"
cube4 = "cube4"
cube5 = "cube5"
switch = "switch"

CUBES = ("cube1", "cube2", "cube3", "cube4", "cube5")

DEVICES = {
    "cube1":  "Cubo 1 (puerto PoE 1)",
    "cube2":  "Cubo 2 (puerto PoE 2)",
    "cube3":  "Cubo 3 (puerto PoE 3)",
    "cube4":  "Cubo 4 (puerto PoE 4)",
    "cube5":  "Cubo 5 (puerto PoE 5)",
    "switch": "PLANET IGS-4215-8UP2T2S (datos agregados)",
}


# ==============================================================
# PARAMETROS
# ==============================================================
# Acciones de escritura
ON      = "ON"
OFF     = "OFF"
RESTART = "RESTART"

# Lectura
STATUS      = "STATUS"
POWER       = "POWER"
CURRENT     = "CURRENT"
ENABLED     = "ENABLED"
DELIVERING  = "DELIVERING"
MAXPOWER    = "MAXPOWER"
PRIORITY    = "PRIORITY"
PDCLASS     = "PDCLASS"
PDTYPE      = "PDTYPE"
INLINE      = "INLINE"
EXTEND      = "EXTEND"

# Solo del switch
NOMINAL     = "NOMINAL"
CONSUMED    = "CONSUMED"
PERCENT     = "PERCENT"
PSE         = "PSE"
TEMPERATURE = "TEMPERATURE"
BUDGET      = "BUDGET"
DESCR       = "DESCR"
NAME        = "NAME"
UPTIME      = "UPTIME"

# Las que escriben. Todo lo demas lee.
ACTIONS = (ON, OFF, RESTART)


# --------------------------------------------------------------
# Parametros de un cubo. 'get' recibe el dict del puerto tal como lo
# arma WebPoEClient.fetch_poe_data().
# --------------------------------------------------------------
CUBE_PARAMETERS = {
    POWER:      {"label": "Potencia",      "unit": "W",  "get": lambda p: p["power_W"]},
    CURRENT:    {"label": "Corriente",     "unit": "mA", "get": lambda p: p["current_mA"]},
    ENABLED:    {"label": "Habilitado",    "unit": "",   "get": lambda p: p["enabled"] == "Enable"},
    DELIVERING: {"label": "Alimentando",   "unit": "",   "get": lambda p: p["current_mA"] > 0},
    MAXPOWER:   {"label": "Max asignado",  "unit": "W",  "get": lambda p: p["max_W"]},
    PRIORITY:   {"label": "Prioridad",     "unit": "",   "get": lambda p: p["priority"]},
    PDCLASS:    {"label": "Clase PD",      "unit": "",   "get": lambda p: p["pd_class"]},
    PDTYPE:     {"label": "Tipo PD",       "unit": "",   "get": lambda p: p["pd_type"]},
    INLINE:     {"label": "Inline mode",   "unit": "",   "get": lambda p: p["inline_mode"]},
    EXTEND:     {"label": "Extend mode",   "unit": "",   "get": lambda p: p["extend"]},
}

# El orden en que STATUS arma su dict, y el CLI lista.
CUBE_STATUS_ORDER = (
    ENABLED, DELIVERING, POWER, CURRENT, MAXPOWER,
    PRIORITY, PDCLASS, PDTYPE, INLINE, EXTEND,
)


# --------------------------------------------------------------
# Parametros del switch. 'get' recibe el frame que arma _switch_frame()
# en __init__.py: los agregados SNMP mas la pagina PoE.
# --------------------------------------------------------------
SWITCH_PARAMETERS = {
    PSE:         {"label": "Estado PSE",     "unit": "",  "get": lambda f: f["pse"]},
    NOMINAL:     {"label": "Potencia nominal", "unit": "W", "get": lambda f: f["nominal_W"]},
    CONSUMED:    {"label": "Consumo total",  "unit": "W", "get": lambda f: f["consumed_W"]},
    POWER:       {"label": "Consumo total",  "unit": "W", "get": lambda f: f["consumed_W"]},
    PERCENT:     {"label": "Uso",            "unit": "%", "get": lambda f: f["percent"]},
    BUDGET:      {"label": "Power budget",   "unit": "W", "get": lambda f: f["budget_W"]},
    TEMPERATURE: {"label": "Temperaturas",   "unit": "C", "get": lambda f: f["temperatures"]},
    DESCR:       {"label": "Descripcion",    "unit": "",  "get": lambda f: f["descr"]},
    NAME:        {"label": "Nombre",         "unit": "",  "get": lambda f: f["name"]},
    UPTIME:      {"label": "Uptime",         "unit": "",  "get": lambda f: f["uptime"]},
}

SWITCH_STATUS_ORDER = (
    PSE, NOMINAL, CONSUMED, PERCENT, BUDGET, TEMPERATURE,
    DESCR, NAME, UPTIME,
)


# ==============================================================
# NORMALIZACION
# ==============================================================
def normalize_device(device):
    """'CUBE1', 'cube1' o 1 -> 'cube1'. None si no existe."""
    if isinstance(device, int):
        device = "cube" + str(device)
    if not isinstance(device, str):
        return None
    key = device.strip().lower()
    return key if key in DEVICES else None


def normalize_parameter(parameter):
    """'on', 'On', ON -> 'ON'. None si no existe."""
    if not isinstance(parameter, str):
        return None
    key = parameter.strip().upper()
    if key == STATUS or key in ACTIONS:
        return key
    if key in CUBE_PARAMETERS or key in SWITCH_PARAMETERS:
        return key
    return None


def is_cube(device):
    return device in CUBES


def parameters_for(device):
    """Todos los parametros que acepta un dispositivo, en orden de listado.

    Incluye los alias que no salen en STATUS (por ejemplo POWER en el
    switch, que es lo mismo que CONSUMED). Es la lista que usan tanto la
    validacion como la ayuda, para que el CLI y la libreria acepten
    exactamente lo mismo."""
    if is_cube(device):
        orden = tuple(CUBE_STATUS_ORDER)
        extras = tuple(sorted(set(CUBE_PARAMETERS) - set(orden)))
        return (STATUS,) + orden + extras + ACTIONS
    orden = tuple(SWITCH_STATUS_ORDER)
    extras = tuple(sorted(set(SWITCH_PARAMETERS) - set(orden)))
    return (STATUS,) + orden + extras


def applies_to(device, parameter):
    """True si el parametro tiene sentido para ese dispositivo."""
    if parameter == STATUS:
        return True
    if parameter in ACTIONS:
        return is_cube(device)
    table = CUBE_PARAMETERS if is_cube(device) else SWITCH_PARAMETERS
    return parameter in table


def describe_parameter(device, parameter):
    """Etiqueta y unidad de un parametro para un dispositivo dado."""
    table = CUBE_PARAMETERS if is_cube(device) else SWITCH_PARAMETERS
    if parameter in table:
        info = dict(table[parameter])
        info.pop("get", None)
        info["name"] = parameter
        return info
    if parameter == STATUS:
        return {"name": STATUS, "label": "Todo", "unit": ""}
    if parameter in ACTIONS:
        return {"name": parameter, "label": "Accion", "unit": ""}
    return None
