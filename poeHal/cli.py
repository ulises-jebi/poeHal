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


def cmd_ports():
    _, web = connect()
    poe_data = web.fetch_poe_data()
    if poe_data:
        header("Puertos PoE - Detalle completo")
        show_port_table(poe_data["ports"], compact=False)


def cmd_port(port_num):
    _, web = connect()
    poe_data = web.fetch_poe_data()
    if poe_data:
        idx = port_num - 1
        if 0 <= idx < len(poe_data["ports"]):
            show_port_detail(poe_data["ports"][idx])
        else:
            print("  Puerto " + str(port_num) + " no existe (rango 1-" + str(poe_data["numPorts"]) + ")")


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
        print("  Port      mA    Watts")
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
            "Puertos PoE":    poe_data["numPorts"],
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
        w.writerow(["port", "enabled", "current_mA", "power_W", "max_W",
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
                cols.extend(["p" + str(i + 1) + "_mA", "p" + str(i + 1) + "_W"])
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
    print("    poeHal -r ports               Tabla detallada de puertos")
    print("    poeHal -r port3               Detalle del puerto 3")
    print("    poeHal -r power               Solo datos de potencia")
    print("    poeHal -r system              Info del sistema")
    print("    poeHal -r watch               Refresh cada 5 segundos")
    print("    poeHal -r watch,10            Refresh cada 10 segundos")
    print("    poeHal -r csv                 Exportar snapshot a CSV")
    print("    poeHal -r log                 Agregar linea al log continuo")
    print("")
    print("  ESCRITURA (-w):")
    print("    poeHal -w port3,1             Habilitar puerto 3")
    print("    poeHal -w port3,0             Deshabilitar puerto 3")
    print("    poeHal -w port3,r             Reiniciar puerto 3 (off/on 5s)")
    print("    poeHal -w port3,r,10          Reiniciar puerto 3, espera 10s")
    print("    poeHal -w port1,1 port5,0     Multiples puertos a la vez")
    print("    poeHal -w port1,r port2,r     Reiniciar multiples puertos")
    print("")
    print("  FORMATO -w:")
    print("    port[1-8],[0|1|r]              0=disable, 1=enable, r=restart")
    print("    port[1-8],r,[seg]              restart con espera personalizada")
    print("")
    print("  AYUDA:")
    print("    poeHal help")
    print("")
    print("  EJEMPLOS:")
    print("    poeHal -r status")
    print("    poeHal -r watch,3")
    print("    poeHal -w port1,1")
    print("    poeHal -w port5,0 port6,0")
    print("    poeHal -w port3,r,15")
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
        read_cmds = ["status", "ports", "power", "system", "csv", "log"]

        # Verificar si es PortN
        port_match = re.match("port(\\d+)", cmd)

        if port_match:
            port_num = int(port_match.group(1))
            if port_num < 1 or port_num > 8:
                print("  [ERROR] Puerto " + str(port_num) + " fuera de rango (1-8)")
                return
            cmd_port(port_num)
            return
        elif cmd.startswith("watch"):
            parts = cmd.split(",")
            interval = int(parts[1]) if len(parts) > 1 else 5
            cmd_watch(interval)
            return
        elif cmd not in read_cmds:
            print("  [ERROR] '" + cmd + "' no es un comando de lectura")
            print("  Comandos -r: " + ", ".join(read_cmds) + ", port[1-8], watch[,seg]")
            return

        if cmd == "status":
            cmd_status()
        elif cmd == "ports":
            cmd_ports()
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
            print("  [ERROR] Falta el parametro de puerto")
            print("  Formato: poeHal -w port[1-8],[0|1|r]")
            print("  Ejemplo: poeHal -w port3,1")
            return

        _, web = connect()

        for arg in args:
            arg_upper = arg.upper()
            match = re.match("PORT(\\d+),(.+)", arg_upper)

            if not match:
                print("  [ERROR] Formato invalido: '" + arg + "'")
                print("  Formato: port[1-8],[0|1|r]  Ejemplo: port3,1")
                return

            port_num = int(match.group(1))
            action_str = match.group(2)

            if port_num < 1 or port_num > 8:
                print("  [ERROR] Puerto " + str(port_num) + " fuera de rango (1-8)")
                return

            if action_str == "1":
                web.set_port_state(port_num, True)
            elif action_str == "0":
                web.set_port_state(port_num, False)
            elif action_str.startswith("R"):
                parts = action_str.split(",")
                wait = int(parts[1]) if len(parts) > 1 else 5
                web.restart_port(port_num, wait)
            else:
                print("  [ERROR] Accion invalida: '" + action_str + "' en '" + arg + "'")
                print("  Acciones: 0=disable, 1=enable, r=restart")
                return

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
