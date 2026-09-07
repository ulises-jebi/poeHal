#!/usr/bin/env python3
"""El ejemplo mas corto posible: apagar y prender un cubo.

Termina con el cubo ENCENDIDO, para no dejar nada apagado por haber
corrido una prueba.
"""

import time

import poeHal as hal
from poeHal import cube5, OFF, ON, STATUS

hal.component(cube5, OFF)
time.sleep(3)
hal.component(cube5, ON)

print(hal.component(cube5, STATUS))
