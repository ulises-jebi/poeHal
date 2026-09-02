"""Interfaz de linea de comandos."""

import csv
import os
import re
import sys
import time
from datetime import datetime

from .clients import connect as _connect
from .config import CONFIG_ERROR, CONFIG_SOURCE, SWITCH_CONFIG
from .display import (
    header, power_bar, show_dict, show_port_detail, show_port_table,
)
from .errors import PoEHalError

LOG_FILE = "poe_log.csv"

# ==============================================================
# COMMANDS
# ==============================================================
def connect():
    """El CLI siempre habla, asi que verbose=True."""
    return _connect(verbose=True)


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
        show_port_table(poe_data["ports"])


def cmd_cubes():
    _, web = connect()
    poe_data = web.fetch_poe_data()
    if poe_data:
        header("Cubos PoE - Detalle completo")
        show_port_table(poe_data["ports"], compact=False)


def cmd_cube(port_num):
    _, web = connect()
    poe_data = web.fetch_poe_data()
    if poe_data:
        idx = port_num - 1
        if 0 <= idx < len(poe_data["ports"]):
            show_port_detail(poe_data["ports"][idx])
        else:
            print("  Cube " + str(port_num) + " no existe (rango 1-" + str(poe_data["numPorts"]) + ")")


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
        for p in poe_data["ports"]:
            ind = ">" if p["power_W"] > 0 else " "
            line = " " + ind + str(p["port"]).ljust(7)
            line += str(p["current_mA"]).rjust(7)
            line += ("%.1f" % p["power_W"]).rjust(9)
            print(line)
        total_w = sum(p["power_W"] for p in poe_data["ports"])
        total_ma = sum(p["current_mA"] for p in poe_data["ports"])
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
            "Cubos PoE":      poe_data["numPorts"],
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
                show_port_table(poe_data["ports"])
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
        for p in poe_data["ports"]:
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
            for i in range(poe_data["numPorts"]):
                cols.extend(["cube" + str(i + 1) + "_mA",
                             "cube" + str(i + 1) + "_W"])
            w.writerow(cols)
        row = [now,
               poe_snmp.get("pethMainPseConsumptionPower", 0),
               poe_snmp.get("pethMainPsePower", 0),
               poe_data["temperature0"],
               poe_data["temperature1"]]
        for p in poe_data["ports"]:
            row.extend([p["current_mA"], p["power_W"]])
        w.writerow(row)
    print("  Registrado en " + LOG_FILE + ": " + now)


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
    print("  LECTURA (-r):")
    print("    poeHal -r status              Resumen rapido")
    print("    poeHal -r cubes               Tabla detallada de cubos")
    print("    poeHal -r cube3               Detalle del cubo 3")
    print("    poeHal -r power               Solo datos de potencia")
    print("    poeHal -r system              Info del sistema")
    print("    poeHal -r watch               Refresh cada 5 segundos")
    print("    poeHal -r watch,10            Refresh cada 10 segundos")
    print("    poeHal -r csv                 Exportar snapshot a CSV")
    print("    poeHal -r log                 Agregar linea al log continuo")
    print("")
    print("  ESCRITURA (-w):")
    print("    poeHal -w cube3,1             Habilitar cubo 3")
    print("    poeHal -w cube3,0             Deshabilitar cubo 3")
    print("    poeHal -w cube3,r             Reiniciar cubo 3 (off/on 5s)")
    print("    poeHal -w cube3,r,10          Reiniciar cubo 3, espera 10s")
    print("    poeHal -w cube1,1 cube5,0     Multiples cubos a la vez")
    print("    poeHal -w cube1,r cube2,r     Reiniciar multiples cubos")
    print("")
    print("  FORMATO -w:")
    print("    cube[1-8],[0|1|r]              0=disable, 1=enable, r=restart")
    print("    cube[1-8],r,[seg]              restart con espera personalizada")
    print("")
    print("  AYUDA:")
    print("    poeHal help")
    print("")
    print("  EJEMPLOS:")
    print("    poeHal -r status")
    print("    poeHal -r watch,3")
    print("    poeHal -w cube1,1")
    print("    poeHal -w cube5,0 cube6,0")
    print("    poeHal -w cube3,r,15")
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

        cmd = sys.argv[2].lower()
        args = sys.argv[3:]
        read_cmds = ["status", "cubes", "power", "system", "csv", "log"]

        # Sintaxis vieja: portN se renombro a cubeN
        legacy = re.match("port(\\d+)$", cmd)
        if legacy:
            print("  [ERROR] 'port" + legacy.group(1) + "' ya no existe: "
                  + "los puertos se llaman cubos.")
            print("  Usa: poeHal -r cube" + legacy.group(1))
            return

        cube_match = re.match("cube(\\d+)$", cmd)

        if cube_match:
            cube_num = int(cube_match.group(1))
            if cube_num < 1 or cube_num > 8:
                print("  [ERROR] Cube " + str(cube_num) + " fuera de rango (1-8)")
                return
            cmd_cube(cube_num)
            return
        elif cmd.startswith("watch"):
            parts = cmd.split(",")
            interval = int(parts[1]) if len(parts) > 1 else 5
            cmd_watch(interval)
            return
        elif cmd not in read_cmds:
            print("  [ERROR] '" + cmd + "' no es un comando de lectura")
            print("  Comandos -r: " + ", ".join(read_cmds) + ", cube[1-8], watch[,seg]")
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
            print("  [ERROR] Falta el parametro de cubo")
            print("  Formato: poeHal -w cube[1-8],[0|1|r]")
            print("  Ejemplo: poeHal -w cube3,1")
            return

        # Primero validar TODO, despues conectar: asi un error de sintaxis
        # no espera por la red, y no se ejecuta media orden.
        plan = []
        for arg in args:
            arg_upper = arg.upper()

            legacy = re.match("PORT(\\d+),", arg_upper)
            if legacy:
                print("  [ERROR] 'port" + legacy.group(1) + "' ya no existe: "
                      + "los puertos se llaman cubos.")
                print("  Usa: " + arg.lower().replace("port", "cube", 1))
                return

            match = re.match("CUBE(\\d+),(.+)", arg_upper)
            if not match:
                print("  [ERROR] Formato invalido: '" + arg + "'")
                print("  Formato: cube[1-8],[0|1|r]  Ejemplo: cube3,1")
                return

            cube_num = int(match.group(1))
            action_str = match.group(2)

            if cube_num < 1 or cube_num > 8:
                print("  [ERROR] Cube " + str(cube_num) + " fuera de rango (1-8)")
                return

            if action_str == "1":
                plan.append((cube_num, "on", 0))
            elif action_str == "0":
                plan.append((cube_num, "off", 0))
            elif action_str.startswith("R"):
                parts = action_str.split(",")
                try:
                    wait = int(parts[1]) if len(parts) > 1 else 5
                except ValueError:
                    print("  [ERROR] Espera invalida en '" + arg + "'")
                    return
                plan.append((cube_num, "restart", wait))
            else:
                # mostrar la accion como la escribio el usuario, no en mayusculas
                shown = arg.split(",", 1)[1] if "," in arg else action_str
                print("  [ERROR] Accion invalida: '" + shown
                      + "' en '" + arg + "'")
                print("  Acciones: 0=disable, 1=enable, r=restart")
                return

        _, web = connect()

        for cube_num, action, wait in plan:
            if action == "on":
                web.set_port_state(cube_num, True)
            elif action == "off":
                web.set_port_state(cube_num, False)
            else:
                web.restart_port(cube_num, wait)

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
