#!/usr/bin/env python3
"""Prueba del paquete poeHal como libreria Python.

Por defecto SOLO LEE: es seguro correrlo en cualquier momento.
La escritura hay que pedirla explicitamente con --cube N.

Uso:
    python3 prueba_paquete.py              # solo lectura
    python3 prueba_paquete.py --cube 5     # lectura + prende/apaga el cubo 5
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
except ImportError:
    print("[ERROR] No se pudo importar poeHal.")
    print("        Instalalo primero:  sudo ./install.sh")
    print("        Y verifica:         pip show poeHal")
    sys.exit(1)


# Los cubos 1-4 suelen tener dispositivos conectados: apagarlos los reinicia.
CUBOS_CON_EQUIPO = (1, 2, 3, 4)


def titulo(texto):
    print("")
    print("=" * 64)
    print("  " + texto)
    print("=" * 64)


def prueba_lectura():
    """Recorre toda la API de lectura."""
    titulo("1. Version y configuracion")
    print("  poeHal version : " + hal.__version__)
    print("  switch         : " + hal.SWITCH_CONFIG["host"])
    print("  usuario        : " + (hal.SWITCH_CONFIG["web_user"] or "(sin definir)"))
    print("  cubos          : " + str(hal.NUM_CUBES))

    titulo("2. hal.system()  - info del switch por SNMP")
    for clave, valor in hal.system().items():
        print("  " + clave.ljust(12) + ": " + str(valor))

    titulo("3. hal.power()  - potencia agregada")
    p = hal.power()
    print("  PSE            : " + str(p["pse"]))
    print("  nominal        : " + str(p["nominal_W"]) + " W")
    print("  consumo        : " + str(p["consumed_W"]) + " W")
    print("  uso            : " + str(p["percent"]) + " %")

    titulo("4. hal.cubes()  - los 8 cubos")
    print("  Cube  Estado    mA      W   Alimentando")
    print("  " + "-" * 44)
    for c in hal.cubes():
        alimentando = "SI" if c["current_mA"] > 0 else "no"
        print("  " + str(c["cube"]).ljust(6)
              + str(c["enabled"]).ljust(10)
              + str(c["current_mA"]).rjust(4)
              + ("%.1f" % c["power_W"]).rjust(7)
              + "   " + alimentando)

    titulo("5. hal.cube(1)  - un cubo puntual")
    for clave, valor in hal.cube(1).items():
        print("  " + str(clave).ljust(12) + ": " + str(valor))

    titulo("6. hal.status()  - todo junto")
    s = hal.status()
    print("  host           : " + str(s["host"]))
    print("  temperaturas   : " + str(s["temperature0"]) + " C / "
          + str(s["temperature1"]) + " C")
    print("  power budget   : " + str(s["power_budget_W"]) + " W")
    print("  cubos en la respuesta: " + str(len(s["cubes"])))


def prueba_escritura(numero, con_restart):
    """Prende y apaga un cubo, verificando el estado despues de cada paso."""
    titulo("7. Escritura sobre el cubo " + str(numero))

    # Snapshot de los 8 cubos: cada escritura reenvia la configuracion
    # completa, asi que hay que poder probar que solo cambio el que tocamos.
    snapshot = {c["cube"]: c for c in hal.cubes()}
    antes = snapshot[numero]
    print("  estado inicial : " + str(antes["enabled"])
          + "  (" + str(antes["current_mA"]) + " mA)")

    # --- apagar ---
    print("")
    print("  hal.cube" + str(numero) + "Off() ...")
    ok = hal.cubeOff(numero)
    time.sleep(2)
    ahora = hal.cube(numero)
    print("    resultado    : " + ("OK" if ok else "FALLO"))
    print("    estado ahora : " + str(ahora["enabled"]))

    # --- prender ---
    print("")
    print("  hal.cube" + str(numero) + "On() ...")
    ok = hal.cubeOn(numero)
    time.sleep(2)
    ahora = hal.cube(numero)
    print("    resultado    : " + ("OK" if ok else "FALLO"))
    print("    estado ahora : " + str(ahora["enabled"]))

    if con_restart:
        print("")
        print("  hal.cube" + str(numero) + "Restart(wait=5) ...")
        ok = hal.cubeRestart(numero, wait=5)
        print("    resultado    : " + ("OK" if ok else "FALLO"))

    # --- lo importante: los otros cubos no se movieron ---
    print("")
    print("  Verificando que los otros " + str(hal.NUM_CUBES - 1)
          + " cubos no cambiaron...")
    # Solo campos de configuracion. mA y W varian solos segun la carga,
    # compararlos daria falsos positivos.
    campos = ("enabled", "max_W", "priority", "pd_type", "inline_mode")
    cambios = []
    for c in hal.cubes():
        n = c["cube"]
        if n == numero:
            continue
        for campo in campos:
            if c[campo] != snapshot[n][campo]:
                cambios.append("cubo " + str(n) + ": " + campo + " "
                               + str(snapshot[n][campo]) + " -> "
                               + str(c[campo]))
    if cambios:
        print("")
        print("    !!! EFECTO COLATERAL: se modificaron otros cubos")
        for linea in cambios:
            print("      " + linea)
        print("")
        print("    Esto significa que el scraping leyo mal la pagina y el")
        print("    POST reescribio los 8 puertos con valores incorrectos.")
        return False
    print("    OK: los demas cubos quedaron identicos")
    return True


def main():
    ap = argparse.ArgumentParser(
        description="Prueba del paquete poeHal (por defecto solo lectura)")
    ap.add_argument("--cube", type=int, metavar="N",
                    help="prueba escritura sobre el cubo N (1-8)")
    ap.add_argument("--restart", action="store_true",
                    help="incluye cubeNRestart() en la prueba de escritura")
    ap.add_argument("--force", action="store_true",
                    help="permite escribir en los cubos 1-4, que suelen "
                         "tener dispositivos conectados")
    args = ap.parse_args()

    if args.cube is not None:
        if not 1 <= args.cube <= hal.NUM_CUBES:
            print("[ERROR] --cube debe estar entre 1 y " + str(hal.NUM_CUBES))
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
            titulo("7. Escritura")
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
        print("  Revisa que el RevPi alcance el switch:")
        print("    ping -c 2 " + hal.SWITCH_CONFIG["host"])
        print("")
        return 1
    except KeyboardInterrupt:
        print("")
        print("  Interrumpido.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
