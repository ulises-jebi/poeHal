"""Excepciones de poeHal.

El CLI las atrapa e imprime; como libreria se dejan propagar.
"""


class PoEHalError(Exception):
    """Base de todos los errores de poeHal."""


class ConfigError(PoEHalError):
    """Falta configuracion, o el archivo tiene permisos inseguros."""


class ConnectionFailed(PoEHalError):
    """El switch no responde por SNMP, o el login web fue rechazado."""
