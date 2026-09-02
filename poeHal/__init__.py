"""poeHal - monitoreo y control de puertos PoE.

Switch PLANET IGS-4215-8UP2T2S.

Uso como CLI:
    poeHal -r status

Uso como libreria:
    import poeHal as hal
    hal.status()

Las credenciales no viven en el codigo: se leen de /etc/poeHal/config.ini
o de las variables POEHAL_*. Ver config.ini.example.
"""

from .clients import SNMPClient, WebPoEClient, connect
from .config import SWITCH_CONFIG, load_config
from .errors import ConfigError, ConnectionFailed, PoEHalError

__version__ = "2.0.0"

__all__ = [
    "SNMPClient", "WebPoEClient", "connect",
    "SWITCH_CONFIG", "load_config",
    "PoEHalError", "ConfigError", "ConnectionFailed",
    "__version__",
]
