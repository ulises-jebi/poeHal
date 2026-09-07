"""poeHal - monitoreo y control de cubos PoE.

Switch PLANET IGS-4215-8UP2T2S. Los cubos son los puertos PoE que los
alimentan: cube1 .. cube5.

Un solo modo de llamado:

    import poeHal as hal
    from poeHal import cube1, switch, ON, OFF, RESTART, STATUS, POWER

    hal.component(cube1, ON)          # encender
    hal.component(cube1, OFF)         # apagar
    hal.component(cube1, RESTART)     # off, espera, on
    hal.component(cube1, STATUS)      # dict con todo el cubo
    hal.component(cube1, POWER)       # 10.7
    hal.component(switch, POWER)      # 44

Tambien acepta texto, util al leer de un archivo o de la linea de
comandos:

    hal.component("cube1", "ON")

Las credenciales no viven en el codigo: se leen de /etc/poeHal/config.ini
o de las variables POEHAL_*. Ver config.ini.example.
"""

from .clients import SNMPClient, WebPoEClient, connect
from .components import (
    ACTIONS, CUBE_PARAMETERS, CUBE_STATUS_ORDER, CUBES, DEVICES, NUM_CUBES,
    SWITCH_PARAMETERS, SWITCH_STATUS_ORDER,
    cube1, cube2, cube3, cube4, cube5, switch,
    ON, OFF, RESTART, STATUS,
    POWER, CURRENT, ENABLED, DELIVERING, MAXPOWER, PRIORITY,
    PDCLASS, PDTYPE, INLINE, EXTEND,
    NOMINAL, CONSUMED, PERCENT, PSE, TEMPERATURE, BUDGET,
    DESCR, NAME, UPTIME,
    applies_to, describe_parameter, is_cube, normalize_device,
    normalize_parameter, parameters_for,
)
from .config import SWITCH_CONFIG, load_config
from .errors import ConfigError, ConnectionFailed, PoEHalError

__version__ = "3.0.0"


# --------------------------------------------------------------
# Sesion compartida y perezosa: 'import poeHal' no toca la red.
# --------------------------------------------------------------
_session = None
_last_poe = None
_last_snmp = None


def _connect_once():
    global _session
    if _session is None:
        _session = connect(verbose=False)
    return _session


def reset():
    """Descarta la sesion y la ultima lectura. El proximo llamado reconecta."""
    global _session, _last_poe, _last_snmp
    _session = None
    _last_poe = None
    _last_snmp = None


def configure(**kwargs):
    """Sobreescribe la configuracion en runtime y fuerza reconexion.

        hal.configure(host="192.168.1.50")

    Solo afecta a este proceso; no escribe en el archivo."""
    unknown = set(kwargs) - set(SWITCH_CONFIG)
    if unknown:
        raise ValueError("Claves desconocidas: " + ", ".join(sorted(unknown)))
    SWITCH_CONFIG.update(kwargs)
    reset()


def _poe_data(refresh=True):
    """La pagina PoE parseada. refresh=False reutiliza la ultima lectura."""
    global _last_poe
    if refresh or _last_poe is None:
        data = _connect_once()[1].fetch_poe_data()
        if not data:
            raise ConnectionFailed(
                "No se pudo leer la pagina PoE de " + SWITCH_CONFIG["host"])
        _last_poe = data
    return _last_poe


def _snmp_data(refresh=True):
    """Los agregados SNMP. refresh=False reutiliza la ultima lectura."""
    global _last_snmp
    if refresh or _last_snmp is None:
        _last_snmp = _connect_once()[0].get_poe_general()
    return _last_snmp


def _cube_frame(device, refresh=True):
    """El dict del puerto que corresponde a un cubo."""
    index = CUBES.index(device)
    ports = _poe_data(refresh)["ports"]
    if index >= len(ports):
        raise ConnectionFailed(
            "El switch reporto " + str(len(ports)) + " puertos: "
            + device + " no existe en el equipo")
    return ports[index]


def _switch_frame(refresh=True):
    """Los agregados del switch, en un solo dict."""
    snmp = _snmp_data(refresh)
    poe = _poe_data(refresh)
    nominal = snmp.get("pethMainPsePower", 0)
    consumed = snmp.get("pethMainPseConsumptionPower", 0)
    percent = 0.0
    if isinstance(nominal, int) and isinstance(consumed, int) and nominal > 0:
        percent = round(consumed / nominal * 100, 1)
    info = _connect_once()[0].get_system_info()
    return {
        "pse":          snmp.get("pethMainPseOperStatus", "N/A"),
        "nominal_W":    nominal,
        "consumed_W":   consumed,
        "percent":      percent,
        "budget_W":     poe["powerBudget"],
        "temperatures": [poe["temperature0"], poe["temperature1"]],
        "descr":        info.get("sysDescr"),
        "name":         info.get("sysName"),
        "uptime":       info.get("sysUpTime"),
    }


# ==============================================================
# LA API
# ==============================================================
def component(device, parameter=STATUS, refresh=True, wait=5):
    """Lee un parametro de un dispositivo, o ejecuta una accion sobre el.

        hal.component(cube1, ON)        -> True si se confirmo el cambio
        hal.component(cube1, OFF)       -> True
        hal.component(cube1, RESTART)   -> True   (wait=5 por defecto)
        hal.component(cube1, POWER)     -> 10.7
        hal.component(cube1, STATUS)    -> dict con todos los parametros
        hal.component(switch, POWER)    -> 44
        hal.component(cube1)            -> igual que STATUS

    device     cube1..cube5 o switch. Tambien acepta el numero del cubo
               (1..5) y texto en cualquier caja. Ver hal.devices().
    parameter  constante de components.py, o su nombre como texto.
               STATUS, el valor por defecto, devuelve todo en un dict.
               ON, OFF y RESTART escriben; el resto lee.
    refresh    True trae una lectura fresca. False reutiliza la anterior,
               util para pedir varios parametros del mismo instante sin
               volver a consultar el switch.
    wait       segundos que RESTART deja el cubo apagado.

    Lanza ValueError si el dispositivo o el parametro no existen, o si se
    pide una accion sobre el switch. ConfigError si faltan credenciales y
    ConnectionFailed si el switch no responde."""
    dev = normalize_device(device)
    if dev is None:
        raise ValueError(
            "Dispositivo desconocido: " + repr(device)
            + ". Disponibles: " + ", ".join(sorted(DEVICES)))

    param = normalize_parameter(parameter)
    if param is None:
        raise ValueError(
            "Parametro desconocido: " + repr(parameter)
            + ".\nDisponibles para " + dev + ": "
            + ", ".join(parameters_for(dev)))

    # Validar que el parametro aplique a este dispositivo antes de abrir
    # la conexion: un error de nombre no debe esperar por la red.
    if not applies_to(dev, param):
        raise ValueError(
            param + " no aplica a '" + dev + "'. Disponibles: "
            + ", ".join(parameters_for(dev)))

    # --- acciones ---
    if param in ACTIONS:
        if not is_cube(dev):
            raise ValueError(
                param + " no aplica a '" + dev + "': solo los cubos se "
                "encienden y apagan. Disponibles: " + ", ".join(CUBES))
        number = CUBES.index(dev) + 1
        web = _connect_once()[1]
        # Cualquier escritura invalida la lectura cacheada.
        global _last_poe
        _last_poe = None
        if param == ON:
            return web.set_port_state(number, True)
        if param == OFF:
            return web.set_port_state(number, False)
        return web.restart_port(number, wait)

    # --- lecturas ---
    if is_cube(dev):
        frame = _cube_frame(dev, refresh)
        if param == STATUS:
            return {n: CUBE_PARAMETERS[n]["get"](frame)
                    for n in CUBE_STATUS_ORDER}
        return CUBE_PARAMETERS[param]["get"](frame)

    frame = _switch_frame(refresh)
    if param == STATUS:
        return {n: SWITCH_PARAMETERS[n]["get"](frame)
                for n in SWITCH_STATUS_ORDER}
    return SWITCH_PARAMETERS[param]["get"](frame)


def devices():
    """Los dispositivos que se pueden consultar: {clave: descripcion}."""
    return dict(DEVICES)


def parameters(device=cube1):
    """Los parametros validos para un dispositivo, en orden de listado."""
    dev = normalize_device(device)
    if dev is None:
        raise ValueError("Dispositivo desconocido: " + repr(device))
    return list(parameters_for(dev))


def describe(parameter, device=cube1):
    """Etiqueta y unidad de un parametro."""
    dev = normalize_device(device)
    if dev is None:
        raise ValueError("Dispositivo desconocido: " + repr(device))
    param = normalize_parameter(parameter)
    info = describe_parameter(dev, param) if param else None
    if info is None:
        raise ValueError("Parametro desconocido: " + repr(parameter))
    return info


# --------------------------------------------------------------
# Las funciones sueltas de la 2.x ya no existen: el llamado ahora es
# component(dispositivo, parametro). Se avisa con el equivalente exacto
# en vez de dejar un AttributeError seco.
# --------------------------------------------------------------
_REMOVED = {
    "status":      "component(switch, STATUS)",
    "power":       "component(switch, POWER)",
    "cubes":       "[hal.component(c, STATUS) for c in hal.CUBES]",
    "cube":        "component(cube1, STATUS)",
    "system":      "component(switch, DESCR)",
    "cubeOn":      "component(cube1, ON)",
    "cubeOff":     "component(cube1, OFF)",
    "cubeRestart": "component(cube1, RESTART)",
}


def __getattr__(name):
    if name in _REMOVED:
        reemplazo = _REMOVED[name]
        if not reemplazo.startswith(("[", "hal.")):
            reemplazo = "hal." + reemplazo
        raise AttributeError(
            "hal." + name + "() ya no existe. Usa: " + reemplazo)
    for n in range(1, NUM_CUBES + 1):
        for accion, param in (("On", "ON"), ("Off", "OFF"),
                              ("Restart", "RESTART")):
            if name == "cube" + str(n) + accion:
                raise AttributeError(
                    "hal." + name + "() ya no existe. Usa: "
                    "hal.component(cube" + str(n) + ", " + param + ")")
    raise AttributeError("module 'poeHal' has no attribute '" + name + "'")


__all__ = [
    # la API
    "component", "devices", "parameters", "describe",
    # dispositivos
    "cube1", "cube2", "cube3", "cube4", "cube5", "switch",
    "CUBES", "DEVICES", "NUM_CUBES",
    # acciones
    "ON", "OFF", "RESTART",
    # parametros de lectura
    "STATUS", "POWER", "CURRENT", "ENABLED", "DELIVERING", "MAXPOWER",
    "PRIORITY", "PDCLASS", "PDTYPE", "INLINE", "EXTEND",
    "NOMINAL", "CONSUMED", "PERCENT", "PSE", "TEMPERATURE", "BUDGET",
    "DESCR", "NAME", "UPTIME",
    # sesion y configuracion
    "configure", "reset", "connect", "SWITCH_CONFIG", "load_config",
    "SNMPClient", "WebPoEClient",
    # errores
    "PoEHalError", "ConfigError", "ConnectionFailed",
    "__version__",
]
