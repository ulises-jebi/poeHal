"""poeHal - monitoreo y control de cubos PoE.

Switch PLANET IGS-4215-8UP2T2S. Los 8 puertos PoE se exponen como
cube1 .. cube8.

CLI:
    poeHal -r status
    poeHal -w cube3,1

Libreria:
    import poeHal as hal
    hal.cube1On()
    hal.cube1Off()
    hal.cube1Restart()
    hal.status()

Las credenciales no viven en el codigo: se leen de /etc/poeHal/config.ini
o de las variables POEHAL_*. Ver config.ini.example.
"""

from .clients import SNMPClient, WebPoEClient, connect
from .config import SWITCH_CONFIG, load_config
from .errors import ConfigError, ConnectionFailed, PoEHalError

__version__ = "2.1.0"

NUM_CUBES = 8

# --------------------------------------------------------------
# Sesion compartida y perezosa: 'import poeHal' no toca la red.
# --------------------------------------------------------------
_session = None


def _connect_once():
    global _session
    if _session is None:
        _session = connect(verbose=False)
    return _session


def _snmp():
    return _connect_once()[0]


def _web():
    return _connect_once()[1]


def reset():
    """Descarta la sesion. El proximo llamado reconecta.

    Util despues de configure(), o si el switch se reinicio."""
    global _session
    _session = None


def configure(**kwargs):
    """Sobreescribe la configuracion en runtime y fuerza reconexion.

        hal.configure(host="192.168.1.50", web_user="otro")

    Solo afecta a este proceso; no escribe en el archivo."""
    unknown = set(kwargs) - set(SWITCH_CONFIG)
    if unknown:
        raise ValueError("Claves desconocidas: " + ", ".join(sorted(unknown)))
    SWITCH_CONFIG.update(kwargs)
    reset()


def _as_cube(port):
    """Traduce la clave interna 'port' a 'cube' en la salida publica."""
    out = dict(port)
    out["cube"] = out.pop("port")
    return out


# --------------------------------------------------------------
# Lectura
# --------------------------------------------------------------
def power():
    """Potencia agregada del switch: PSE, nominal, consumo y porcentaje."""
    data = _snmp().get_poe_general()
    nominal = data.get("pethMainPsePower", 0)
    consumed = data.get("pethMainPseConsumptionPower", 0)
    percent = 0.0
    if isinstance(nominal, int) and isinstance(consumed, int) and nominal > 0:
        percent = round(consumed / nominal * 100, 1)
    return {
        "pse":        data.get("pethMainPseOperStatus", "N/A"),
        "nominal_W":  nominal,
        "consumed_W": consumed,
        "percent":    percent,
    }


def cubes():
    """Lista de los 8 cubos, cada uno un dict con mA, W, prioridad, etc."""
    data = _web().fetch_poe_data()
    if not data:
        raise ConnectionFailed(
            "No se pudo leer la pagina PoE de " + SWITCH_CONFIG["host"])
    return [_as_cube(p) for p in data["ports"]]


def cube(number):
    """El cubo indicado (1-8)."""
    if not 1 <= number <= NUM_CUBES:
        raise ValueError("Cube " + str(number) + " fuera de rango (1-"
                         + str(NUM_CUBES) + ")")
    return cubes()[number - 1]


def status():
    """Todo de una: potencia agregada, temperaturas y los 8 cubos."""
    data = _web().fetch_poe_data()
    if not data:
        raise ConnectionFailed(
            "No se pudo leer la pagina PoE de " + SWITCH_CONFIG["host"])
    result = power()
    result.update({
        "host":          SWITCH_CONFIG["host"],
        "temperature0":  data["temperature0"],
        "temperature1":  data["temperature1"],
        "power_budget_W": data["powerBudget"],
        "cubes":         [_as_cube(p) for p in data["ports"]],
    })
    return result


def system():
    """Informacion del sistema por SNMP: descripcion, nombre y uptime."""
    return _snmp().get_system_info()


# --------------------------------------------------------------
# Escritura
# --------------------------------------------------------------
def cubeOn(number):
    """Enciende el cubo indicado. Devuelve True si se confirmo el cambio."""
    if not 1 <= number <= NUM_CUBES:
        raise ValueError("Cube " + str(number) + " fuera de rango")
    return _web().set_port_state(number, True)


def cubeOff(number):
    """Apaga el cubo indicado. Devuelve True si se confirmo el cambio."""
    if not 1 <= number <= NUM_CUBES:
        raise ValueError("Cube " + str(number) + " fuera de rango")
    return _web().set_port_state(number, False)


def cubeRestart(number, wait=5):
    """Apaga el cubo, espera 'wait' segundos y lo vuelve a encender."""
    if not 1 <= number <= NUM_CUBES:
        raise ValueError("Cube " + str(number) + " fuera de rango")
    return _web().restart_port(number, wait)


# --------------------------------------------------------------
# Atajos por cubo.
# Escritos explicitos, no generados: asi el autocompletado del editor
# y los linters los ven.
# --------------------------------------------------------------
def cube1On():
    """Enciende el cubo 1."""
    return cubeOn(1)


def cube1Off():
    """Apaga el cubo 1."""
    return cubeOff(1)


def cube1Restart(wait=5):
    """Reinicia el cubo 1: off, espera, on."""
    return cubeRestart(1, wait)


def cube2On():
    """Enciende el cubo 2."""
    return cubeOn(2)


def cube2Off():
    """Apaga el cubo 2."""
    return cubeOff(2)


def cube2Restart(wait=5):
    """Reinicia el cubo 2: off, espera, on."""
    return cubeRestart(2, wait)


def cube3On():
    """Enciende el cubo 3."""
    return cubeOn(3)


def cube3Off():
    """Apaga el cubo 3."""
    return cubeOff(3)


def cube3Restart(wait=5):
    """Reinicia el cubo 3: off, espera, on."""
    return cubeRestart(3, wait)


def cube4On():
    """Enciende el cubo 4."""
    return cubeOn(4)


def cube4Off():
    """Apaga el cubo 4."""
    return cubeOff(4)


def cube4Restart(wait=5):
    """Reinicia el cubo 4: off, espera, on."""
    return cubeRestart(4, wait)


def cube5On():
    """Enciende el cubo 5."""
    return cubeOn(5)


def cube5Off():
    """Apaga el cubo 5."""
    return cubeOff(5)


def cube5Restart(wait=5):
    """Reinicia el cubo 5: off, espera, on."""
    return cubeRestart(5, wait)


def cube6On():
    """Enciende el cubo 6."""
    return cubeOn(6)


def cube6Off():
    """Apaga el cubo 6."""
    return cubeOff(6)


def cube6Restart(wait=5):
    """Reinicia el cubo 6: off, espera, on."""
    return cubeRestart(6, wait)


def cube7On():
    """Enciende el cubo 7."""
    return cubeOn(7)


def cube7Off():
    """Apaga el cubo 7."""
    return cubeOff(7)


def cube7Restart(wait=5):
    """Reinicia el cubo 7: off, espera, on."""
    return cubeRestart(7, wait)


def cube8On():
    """Enciende el cubo 8."""
    return cubeOn(8)


def cube8Off():
    """Apaga el cubo 8."""
    return cubeOff(8)


def cube8Restart(wait=5):
    """Reinicia el cubo 8: off, espera, on."""
    return cubeRestart(8, wait)


__all__ = [
    # lectura
    "status", "power", "cubes", "cube", "system",
    # escritura genericas
    "cubeOn", "cubeOff", "cubeRestart",
    # atajos por cubo
    "cube1On", "cube1Off", "cube1Restart",
    "cube2On", "cube2Off", "cube2Restart",
    "cube3On", "cube3Off", "cube3Restart",
    "cube4On", "cube4Off", "cube4Restart",
    "cube5On", "cube5Off", "cube5Restart",
    "cube6On", "cube6Off", "cube6Restart",
    "cube7On", "cube7Off", "cube7Restart",
    "cube8On", "cube8Off", "cube8Restart",
    # sesion y configuracion
    "configure", "reset", "connect", "SWITCH_CONFIG", "load_config",
    "SNMPClient", "WebPoEClient", "NUM_CUBES",
    # errores
    "PoEHalError", "ConfigError", "ConnectionFailed",
    "__version__",
]
