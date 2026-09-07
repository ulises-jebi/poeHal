"""Interfaz de linea de comandos."""

import csv
import os
import re
import sys
import time
from datetime import datetime

from . import component as _component
from .clients import connect as _connect
from .components import (
    ACTIONS, CUBES, DEVICES, NUM_CUBES, STATUS,
    applies_to, describe_parameter, is_cube, normalize_device,
    normalize_parameter, parameters_for,
)
from .config import CONFIG_ERROR, CONFIG_SOURCE, SWITCH_CONFIG
from .display import (
    header, power_bar, show_dict, show_port_table,
)
from .errors import PoEHalError

LOG_FILE = "poe_log.csv"

# ==============================================================
# COMMANDS
# ==============================================================
def connect():
    """El CLI siempre habla, asi que verbose=True."""
    return _connect(verbose=True)


def _cubes_of(poe_data):
    """Los puertos que corresponden a cubos.

    El switch reporta 8 puertos, pero solo los primeros NUM_CUBES son
    cubos. Toda ESCRITURA sigue reenviando la configuracion de los 8
    (lo exige el CGI del switch); esto solo recorta lo que se muestra.
    """
    return poe_data["ports"][:NUM_CUBES]


def cmd_status():
    snmp, web = connect()
    poe_snmp = snmp.get_poe_general()
    nominal = poe_snmp.get("pethMainPsePower", 0)
    consumo = poe_snmp.get("pethMainPseConsumptionPower", 0)
    poe_data = web.fetch_poe_data()
    pct = 0
    if isinstance(nominal, int) and isinstance(consumo, int) and nominal > 0:
        pct = consumo / nominal * 100
    temp0 = poe_data["temperature0"] if poe_data else "?"
    temp1 = poe_data["temperature1"] if poe_data else "?"
    header("PoE Status - " + SWITCH_CONFIG["host"])
    pse = poe_snmp.get("pethMainPseOperStatus", "N/A")
    print("  PSE: " + str(pse) + "  |  Consumo: " + str(consumo) + "W de " + str(nominal)
          + "W usando el " + "%.1f" % pct + "% y Temp: " + str(temp0) + "C / " + str(temp1) + "C")
    if poe_data:
        show_port_table(_cubes_of(poe_data))


def cmd_cubes():
    _, web = connect()
    poe_data = web.fetch_poe_data()
    if poe_data:
        header("Cubos PoE - Detalle completo")
        show_port_table(_cubes_of(poe_data), compact=False)


def cmd_power():
    snmp, web = connect()
    poe_snmp = snmp.get_poe_general()
    nominal = poe_snmp.get("pethMainPsePower", 0)
    consumo = poe_snmp.get("pethMainPseConsumptionPower", 0)
    header("Consumo de Potencia")
    show_dict({
        "PSE Status":       poe_snmp.get("pethMainPseOperStatus", "N/A"),
        "Potencia nominal": str(nominal) + " W",
        "Consumo total":    str(consumo) + " W",
    })
    if isinstance(nominal, int) and isinstance(consumo, int):
        power_bar(consumo, nominal)
    poe_data = web.fetch_poe_data()
    if poe_data:
        print("")
        print("  Cube      mA    Watts")
        print("  " + "-" * 24)
        for p in _cubes_of(poe_data):
            ind = ">" if p["power_W"] > 0 else " "
            line = " " + ind + str(p["port"]).ljust(7)
            line += str(p["current_mA"]).rjust(7)
            line += ("%.1f" % p["power_W"]).rjust(9)
            print(line)
        total_w = sum(p["power_W"] for p in _cubes_of(poe_data))
        total_ma = sum(p["current_mA"] for p in _cubes_of(poe_data))
        print("  " + "-" * 24)
        print("  Total".ljust(9) + str(total_ma).rjust(7) + ("%.1f" % total_w).rjust(9))


def cmd_system():
    snmp, web = connect()
    header("Informacion del Sistema")
    show_dict(snmp.get_system_info())
    poe_data = web.fetch_poe_data()
    if poe_data:
        print("")
        show_dict({
            "Cubos PoE":      NUM_CUBES,
            "Puertos del switch": poe_data["numPorts"],
            "Power Budget":   str(poe_data["powerBudget"]) + " W",
            "Max Budget":     str(poe_data["maxBudget"]) + " W",
            "Admin":          "Enabled" if poe_data["poeAdmin"] == 0 else "Disabled",
            "Modo":           "Consumption" if poe_data["poeMode"] == 1 else "Allocation",
            "Temperatura 0":  str(poe_data["temperature0"]) + " C",
            "Temperatura 1":  str(poe_data["temperature1"]) + " C",
        })


def cmd_watch(interval=5):
    snmp, web = connect()
    print("  Monitoreando cada " + str(interval) + "s... (Ctrl+C para detener)")
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            poe_snmp = snmp.get_poe_general()
            nominal = poe_snmp.get("pethMainPsePower", 0)
            consumo = poe_snmp.get("pethMainPseConsumptionPower", 0)
            pct = 0
            if isinstance(nominal, int) and isinstance(consumo, int) and nominal > 0:
                pct = consumo / nominal * 100
            poe_data = web.fetch_poe_data()
            temp0 = poe_data["temperature0"] if poe_data else "?"
            temp1 = poe_data["temperature1"] if poe_data else "?"
            header("PoE Watch - " + SWITCH_CONFIG["host"] + "  |  " + now)
            pse = poe_snmp.get("pethMainPseOperStatus", "?")
            print("  PSE: " + str(pse) + "  |  Consumo: " + str(consumo) + "W de " + str(nominal)
                  + "W usando el " + "%.1f" % pct + "% y Temp: " + str(temp0) + "C / " + str(temp1) + "C")
            print("  Refresh: " + str(interval) + "s  |  Ctrl+C = salir")
            if poe_data:
                show_port_table(_cubes_of(poe_data))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("")
        print("  Monitoreo detenido.")


def cmd_csv():
    snmp, web = connect()
    poe_snmp = snmp.get_poe_general()
    poe_data = web.fetch_poe_data()
    if not poe_data:
        print("  Error obteniendo datos")
        return
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "poe_export_" + now + ".csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "total_W", "budget_W", "temp0_C", "temp1_C"])
        w.writerow([now,
                     poe_snmp.get("pethMainPseConsumptionPower", 0),
                     poe_snmp.get("pethMainPsePower", 0),
                     poe_data["temperature0"],
                     poe_data["temperature1"]])
        w.writerow([])
        w.writerow(["cube", "enabled", "current_mA", "power_W", "max_W",
                     "priority", "pd_type", "inline_mode", "pd_class", "extend"])
        for p in _cubes_of(poe_data):
            w.writerow([p["port"], p["enabled"], p["current_mA"],
                        p["power_W"], p["max_W"], p["priority"],
                        p["pd_type"], p["inline_mode"], p["pd_class"], p["extend"]])
    print("  Exportado: " + filename)


def cmd_log():
    snmp, web = connect()
    poe_snmp = snmp.get_poe_general()
    poe_data = web.fetch_poe_data()
    if not poe_data:
        print("  Error obteniendo datos")
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            cols = ["timestamp", "total_W", "budget_W", "temp0", "temp1"]
            for i in range(NUM_CUBES):
                cols.extend(["cube" + str(i + 1) + "_mA",
                             "cube" + str(i + 1) + "_W"])
            w.writerow(cols)
        row = [now,
               poe_snmp.get("pethMainPseConsumptionPower", 0),
               poe_snmp.get("pethMainPsePower", 0),
               poe_data["temperature0"],
               poe_data["temperature1"]]
        for p in _cubes_of(poe_data):
            row.extend([p["current_mA"], p["power_W"]])
        w.writerow(row)
    print("  Registrado en " + LOG_FILE + ": " + now)


def cmd_components():
    """Lista lo que se puede pedir, que es la ayuda que de verdad se usa."""
    header("Dispositivos y parametros")
    print("  Formato:  poeHal -r <dispositivo>,<PARAMETRO>")
    print("            poeHal -w <cubo>,<ON|OFF|RESTART[,seg]>")
    print("")
    for dev in list(CUBES) + ["switch"]:
        print("  " + dev.ljust(8) + DEVICES[dev])
        for param in parameters_for(dev):
            info = describe_parameter(dev, param) or {}
            unidad = info.get("unit") or ""
            etiqueta = info.get("label", "")
            marca = "  (escribe)" if param in ACTIONS else ""
            print("      " + param.ljust(12) + etiqueta.ljust(18)
                  + (unidad.ljust(4) if unidad else "    ") + marca)
        print("")


def _mostrar(device, param, valor):
    """Imprime el resultado de una lectura, con etiqueta y unidad."""
    if param == STATUS and isinstance(valor, dict):
        header(device + " - " + DEVICES[device])
        ancho = max(len(k) for k in valor) if valor else 0
        for clave, v in valor.items():
            info = describe_parameter(device, clave) or {}
            unidad = info.get("unit") or ""
            texto = str(v) + (" " + unidad if unidad else "")
            print("  " + clave.ljust(ancho + 2) + ": " + texto)
        print("")
        return
    info = describe_parameter(device, param) or {}
    unidad = info.get("unit") or ""
    print("  " + device + "," + param + " = " + str(valor)
          + (" " + unidad if unidad else ""))


def cmd_component_read(device, param):
    valor = _component(device, param)
    _mostrar(device, param, valor)


def cmd_component_write(device, param, wait=5):
    antes = _component(device, "ENABLED")
    ok = _component(device, param, wait=wait)
    despues = _component(device, "ENABLED")
    texto = {True: "Enable", False: "Disable"}
    print("  " + device + ": " + texto[bool(antes)] + " -> "
          + texto[bool(despues)] + " : " + ("OK" if ok else "FALLO"))
    return ok


def cmd_help():
    print("")
    print("  PLANET IGS-4215-8UP2T2S - PoE CLI Tool (poeHal)")
    print("  Switch: " + SWITCH_CONFIG["host"])
    if CONFIG_ERROR:
        print("  Config: [ERROR] " + CONFIG_ERROR.split("\n")[0])
    elif CONFIG_SOURCE:
        creds = "con credenciales" if SWITCH_CONFIG["web_user"] else "SIN credenciales"
        print("  Config: " + CONFIG_SOURCE + " (" + creds + ")")
    else:
        print("  Config: sin archivo (ver config.ini.example)")
    print("")
    print("  FORMATO:")
    print("    poeHal -r <dispositivo>,<PARAMETRO>")
    print("    poeHal -w <cubo>,<ON|OFF|RESTART[,seg]>")
    print("")
    print("  LECTURA (-r):")
    print("    poeHal -r cube1,STATUS        Todo el cubo 1")
    print("    poeHal -r cube1,POWER         Solo la potencia")
    print("    poeHal -r cube1               Igual que cube1,STATUS")
    print("    poeHal -r switch,POWER        Consumo total del switch")
    print("    poeHal -r switch,STATUS       Agregados del switch")
    print("    poeHal -r components          Que dispositivos y parametros hay")
    print("")
    print("  VISTAS (-r):")
    print("    poeHal -r status              Resumen rapido")
    print("    poeHal -r cubes               Tabla de los cubos")
    print("    poeHal -r power               Datos de potencia")
    print("    poeHal -r system              Info del sistema")
    print("    poeHal -r watch,10            Monitor en vivo cada 10s")
    print("    poeHal -r csv                 Exportar snapshot a CSV")
    print("    poeHal -r log                 Agregar linea al log continuo")
    print("")
    print("  ESCRITURA (-w):")
    print("    poeHal -w cube3,ON            Encender cubo 3")
    print("    poeHal -w cube3,OFF           Apagar cubo 3")
    print("    poeHal -w cube3,RESTART       Reiniciar (off/on 5s)")
    print("    poeHal -w cube3,RESTART,10    Reiniciar con espera de 10s")
    print("    poeHal -w cube1,ON cube5,OFF  Varios cubos a la vez")
    print("")
    print("  DISPOSITIVOS:")
    print("    " + ", ".join(CUBES) + ", switch")
    print("")
    print("  AYUDA:")
    print("    poeHal help")
    print("    poeHal -r components          Lista completa de parametros")
    print("")


# ==============================================================
# MAIN
# ==============================================================
def main():
    if len(sys.argv) < 2:
        cmd_help()
        return

    arg1 = sys.argv[1].lower()

    if arg1 in ("help", "-h", "--help", "?"):
        cmd_help()
        return

    if arg1 not in ("-r", "-w"):
        print("  [ERROR] Bandera requerida: -r (lectura) o -w (escritura)")
        print("  Usa 'poeHal help' para ver los comandos disponibles")
        return

    flag = arg1

    if flag == "-r":
        if len(sys.argv) < 3:
            print("  [ERROR] Falta el comando despues de -r")
            print("  Usa 'poeHal help' para ver los comandos disponibles")
            return

        cmd_original = sys.argv[2]
        cmd = cmd_original.lower()
        args = sys.argv[3:]
        read_cmds = ["status", "cubes", "power", "system", "csv", "log"]

        # Sintaxis vieja: portN se renombro a cubeN
        legacy = re.match("port(\\d+)", cmd)
        if legacy:
            print("  [ERROR] 'port" + legacy.group(1) + "' ya no existe: "
                  + "los puertos se llaman cubos.")
            print("  Usa: poeHal -r cube" + legacy.group(1) + ",STATUS")
            return

        if cmd in ("components", "component", "list"):
            cmd_components()
            return

        # --- forma principal: <dispositivo>,<PARAMETRO> ---
        if "," in cmd and not cmd.startswith("watch"):
            nombre, _, _pedido_lower = cmd.partition(",")
            pedido = cmd_original.partition(",")[2]
            dev = normalize_device(nombre)
            if dev is None:
                print("  [ERROR] Dispositivo desconocido: '" + nombre + "'")
                print("  Disponibles: " + ", ".join(sorted(DEVICES)))
                return
            param = normalize_parameter(pedido)
            if param is None:
                print("  [ERROR] Parametro desconocido: '" + pedido + "'")
                print("  Para " + dev + ": " + ", ".join(parameters_for(dev)))
                return
            if param in ACTIONS:
                print("  [ERROR] " + param + " escribe: usa -w en vez de -r")
                print("  Ejemplo: poeHal -w " + dev + "," + param)
                return
            if not applies_to(dev, param):
                print("  [ERROR] " + param + " no aplica a '" + dev + "'")
                print("  Disponibles: " + ", ".join(parameters_for(dev)))
                return
            cmd_component_read(dev, param)
            return

        # Un dispositivo suelto equivale a pedirle STATUS.
        solo_dev = normalize_device(cmd)
        if solo_dev is not None:
            cmd_component_read(solo_dev, STATUS)
            return

        cube_match = re.match("cube(\\d+)$", cmd)
        if cube_match:
            print("  [ERROR] Cube " + cube_match.group(1)
                  + " fuera de rango (1-" + str(NUM_CUBES) + ")")
            return

        if cmd.startswith("watch"):
            parts = cmd.split(",")
            interval = int(parts[1]) if len(parts) > 1 else 5
            cmd_watch(interval)
            return
        elif cmd not in read_cmds:
            print("  [ERROR] '" + cmd + "' no es un comando de lectura")
            print("  Comandos -r: " + ", ".join(read_cmds)
                  + ", components, watch[,seg]")
            print("  O bien:      <dispositivo>,<PARAMETRO>   (poeHal -r components)")
            return

        if cmd == "status":
            cmd_status()
        elif cmd == "cubes":
            cmd_cubes()
        elif cmd == "power":
            cmd_power()
        elif cmd == "system":
            cmd_system()
        elif cmd == "csv":
            cmd_csv()
        elif cmd == "log":
            cmd_log()

    elif flag == "-w":
        args = sys.argv[2:]

        if not args:
            print("  [ERROR] Falta el cubo y la accion")
            print("  Formato: poeHal -w <cubo>,<ON|OFF|RESTART[,seg]>")
            print("  Ejemplo: poeHal -w cube3,ON")
            return

        # Primero validar TODO, despues conectar: asi un error de sintaxis
        # no espera por la red, y no se ejecuta media orden.
        plan = []
        for arg in args:
            legacy = re.match(r"port(\d+),(.*)", arg, re.IGNORECASE)
            if legacy:
                accion = {"1": "ON", "0": "OFF"}.get(
                    legacy.group(2).strip().upper())
                if accion is None and legacy.group(2).strip().upper().startswith("R"):
                    accion = "RESTART"
                print("  [ERROR] 'port" + legacy.group(1) + "' ya no existe: "
                      + "los puertos se llaman cubos.")
                print("  Usa: poeHal -w cube" + legacy.group(1) + ","
                      + (accion or "ON"))
                return

            if "," not in arg:
                print("  [ERROR] Falta la accion en '" + arg + "'")
                print("  Formato: <cubo>,<ON|OFF|RESTART[,seg]>")
                return

            nombre, _, resto = arg.partition(",")
            dev = normalize_device(nombre)
            if dev is None:
                print("  [ERROR] Dispositivo desconocido: '" + nombre + "'")
                print("  Disponibles: " + ", ".join(CUBES))
                return

            partes = resto.split(",")
            param = normalize_parameter(partes[0])

            # Sintaxis vieja 0/1/r
            if param is None:
                equivalente = {"1": "ON", "0": "OFF", "R": "RESTART"}.get(
                    partes[0].strip().upper())
                if equivalente:
                    print("  [ERROR] '" + partes[0] + "' ya no se usa.")
                    print("  Usa: poeHal -w " + dev + "," + equivalente)
                    return
                print("  [ERROR] Accion desconocida: '" + partes[0] + "'")
                print("  Acciones: " + ", ".join(ACTIONS))
                return

            if param not in ACTIONS:
                print("  [ERROR] " + param + " es de lectura: usa -r")
                print("  Ejemplo: poeHal -r " + dev + "," + param)
                return

            if not is_cube(dev):
                print("  [ERROR] " + param + " no aplica a '" + dev
                      + "': solo los cubos se encienden y apagan.")
                return

            wait = 5
            if len(partes) > 1:
                try:
                    wait = int(partes[1])
                except ValueError:
                    print("  [ERROR] Espera invalida en '" + arg + "'")
                    return
                if param != "RESTART":
                    print("  [ERROR] La espera solo aplica a RESTART: '"
                          + arg + "'")
                    return

            plan.append((dev, param, wait))

        for dev, param, wait in plan:
            cmd_component_write(dev, param, wait)

        print("")


def run():
    """Punto de entrada del comando 'poeHal'. Traduce las excepciones de la
    libreria al formato de salida que el CLI ya usaba."""
    try:
        main()
    except PoEHalError as e:
        print("  [ERROR] " + str(e))
        print("")
        sys.exit(1)
    except KeyboardInterrupt:
        print("")
        sys.exit(130)


if __name__ == "__main__":
    run()
