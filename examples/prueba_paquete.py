#!/usr/bin/env python3
"""Prueba del paquete poeHal como libreria Python.

Por defecto SOLO LEE: es seguro correrlo en cualquier momento.
La escritura hay que pedirla explicitamente con --cube N.

Uso:
    python3 prueba_paquete.py              # solo lectura
    python3 prueba_paquete.py --cube 5     # lectura + apaga/prende el cubo 5
    python3 prueba_paquete.py --cube 5 --restart
    python3 prueba_paquete.py --cube 2 --force   # cubos 1-4: hay equipo real

Requiere el paquete instalado:
    sudo ./install.sh
"""

import argparse
import sys
import time

try:
    import poeHal as hal
    from poeHal import (
        CUBES, OFF, ON, POWER, RESTART, STATUS, switch,
    )
except ImportError:
    print("[ERROR] No se pudo importar poeHal.")
    print("        Instalalo primero:  sudo ./install.sh")
    print("        Y verifica:         pip show poeHal")
    sys.exit(1)


# Los cubos 1-4 suelen tener dispositivos conectados: apagarlos los reinicia.
CUBOS_CON_EQUIPO = (1, 2, 3, 4)

# Los campos de configuracion que NO deben cambiar al tocar otro cubo.
# La potencia y la corriente varian solas con la carga, compararlas daria
# falsos positivos.
CAMPOS_ESTABLES = ("ENABLED", "MAXPOWER", "PRIORITY", "PDTYPE", "INLINE")


def titulo(texto):
    print("")
    print("=" * 64)
    print("  " + texto)
    print("=" * 64)


def prueba_lectura():
    """Recorre la API de lectura, en el formato component()."""
    titulo("1. Version y catalogo")
    print("  poeHal version : " + hal.__version__)
    print("  switch         : " + hal.SWITCH_CONFIG["host"])
    print("  dispositivos   : " + ", ".join(hal.devices()))
    print("")
    print("  parametros de un cubo:")
    print("    " + ", ".join(hal.parameters("cube1")))
    print("  parametros del switch:")
    print("    " + ", ".join(hal.parameters(switch)))

    titulo("2. component(switch, STATUS)")
    for clave, valor in hal.component(switch, STATUS).items():
        info = hal.describe(clave, switch)
        unidad = info.get("unit") or ""
        print("  " + clave.ljust(12) + ": " + str(valor)
              + (" " + unidad if unidad else ""))

    titulo("3. Un parametro suelto")
    print("  component(switch, POWER)     = "
          + str(hal.component(switch, POWER)) + " W")
    print("  component(cube1, POWER)      = "
          + str(hal.component("cube1", POWER)) + " W")
    print("  component(cube1, 'CURRENT')  = "
          + str(hal.component("cube1", "CURRENT")) + " mA")

    titulo("4. Todos los cubos")
    print("  Cube   Habilitado  Alimentando   mA       W")
    print("  " + "-" * 46)
    for nombre in CUBES:
        # refresh solo en el primero: los demas reusan esa misma lectura,
        # asi los cinco cubos son del mismo instante y no son 5 consultas.
        primero = nombre == CUBES[0]
        est = hal.component(nombre, STATUS, refresh=primero)
        print("  " + nombre.ljust(7)
              + str(est["ENABLED"]).ljust(12)
              + str(est["DELIVERING"]).ljust(14)
              + str(est["CURRENT"]).rjust(4)
              + ("%.1f" % est["POWER"]).rjust(8))


def _snapshot():
    """Los campos estables de los 5 cubos, para comparar despues."""
    salida = {}
    for i, nombre in enumerate(CUBES):
        est = hal.component(nombre, STATUS, refresh=(i == 0))
        salida[nombre] = {c: est[c] for c in CAMPOS_ESTABLES}
    return salida


def prueba_escritura(numero, con_restart):
    """Apaga y prende un cubo, verificando que no toque a los demas."""
    nombre = "cube" + str(numero)
    titulo("5. Escritura sobre " + nombre)

    antes = _snapshot()
    print("  estado inicial : " + str(antes[nombre]["ENABLED"]))

    print("")
    print("  component(" + nombre + ", OFF) ...")
    ok = hal.component(nombre, OFF)
    time.sleep(2)
    print("    resultado    : " + ("OK" if ok else "FALLO"))
    print("    habilitado   : " + str(hal.component(nombre, "ENABLED")))

    print("")
    print("  component(" + nombre + ", ON) ...")
    ok = hal.component(nombre, ON)
    time.sleep(2)
    print("    resultado    : " + ("OK" if ok else "FALLO"))
    print("    habilitado   : " + str(hal.component(nombre, "ENABLED")))

    if con_restart:
        print("")
        print("  component(" + nombre + ", RESTART, wait=5) ...")
        ok = hal.component(nombre, RESTART, wait=5)
        print("    resultado    : " + ("OK" if ok else "FALLO"))

    # --- lo importante: los otros cubos no se movieron ---
    print("")
    print("  Verificando que los otros " + str(len(CUBES) - 1)
          + " cubos no cambiaron...")
    despues = _snapshot()
    cambios = []
    for otro in CUBES:
        if otro == nombre:
            continue
        for campo in CAMPOS_ESTABLES:
            if antes[otro][campo] != despues[otro][campo]:
                cambios.append(otro + ": " + campo + " "
                               + str(antes[otro][campo]) + " -> "
                               + str(despues[otro][campo]))
    if cambios:
        print("")
        print("    !!! EFECTO COLATERAL: se modificaron otros cubos")
        for linea in cambios:
            print("      " + linea)
        print("")
        print("    Esto significa que el scraping leyo mal la pagina y el")
        print("    POST reescribio los puertos con valores incorrectos.")
        return False
    print("    OK: los demas cubos quedaron identicos")
    return True


def main():
    ap = argparse.ArgumentParser(
        description="Prueba del paquete poeHal (por defecto solo lectura)")
    ap.add_argument("--cube", type=int, metavar="N",
                    help="prueba escritura sobre el cubo N (1-%d)" % len(CUBES))
    ap.add_argument("--restart", action="store_true",
                    help="incluye RESTART en la prueba de escritura")
    ap.add_argument("--force", action="store_true",
                    help="permite escribir en los cubos 1-4, que suelen "
                         "tener dispositivos conectados")
    args = ap.parse_args()

    if args.cube is not None:
        if not 1 <= args.cube <= len(CUBES):
            print("[ERROR] --cube debe estar entre 1 y " + str(len(CUBES)))
            return 2
        if args.cube in CUBOS_CON_EQUIPO and not args.force:
            print("")
            print("[ABORTADO] El cubo " + str(args.cube)
                  + " suele tener un dispositivo conectado:")
            print("           apagarlo lo reinicia.")
            print("")
            print("  Para probar sin riesgo, usa un cubo libre:")
            print("    python3 prueba_paquete.py --cube 5")
            print("")
            print("  Si de verdad quieres tocar el cubo "
                  + str(args.cube) + ":")
            print("    python3 prueba_paquete.py --cube "
                  + str(args.cube) + " --force")
            print("")
            return 1

    try:
        prueba_lectura()
        if args.cube is not None:
            if not prueba_escritura(args.cube, args.restart):
                titulo("FALLO")
                print("  La escritura afecto cubos que no debia.")
                print("")
                return 1
        else:
            titulo("5. Escritura")
            print("  Omitida. Para probarla, elige un cubo libre:")
            print("    python3 prueba_paquete.py --cube 5")

        titulo("Listo")
        print("  Todas las llamadas respondieron sin excepciones.")
        print("")
        return 0

    except hal.ConfigError as e:
        print("")
        print("[ERROR de configuracion]")
        print(str(e))
        print("")
        return 1
    except hal.ConnectionFailed as e:
        print("")
        print("[ERROR de conexion] " + str(e))
        print("")
        print("  Revisa que el equipo alcance el switch:")
        print("    ping -c 2 " + hal.SWITCH_CONFIG["host"])
        print("")
        return 1
    except KeyboardInterrupt:
        print("")
        print("  Interrumpido.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
