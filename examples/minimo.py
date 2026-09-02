#!/usr/bin/env python3
"""El ejemplo mas corto posible: prender y apagar un cubo."""

import time

import poeHal as hal

hal.cube5On()
time.sleep(3)
hal.cube5Off()

print(hal.cube(5))
