"""Salida en texto plano para el CLI. Sin dependencias externas."""

# ==============================================================
# DISPLAY
# ==============================================================
def header(title):
    print("")
    print("=" * 72)
    print("  " + title)
    print("=" * 72)


def show_dict(data):
    mx = max(len(str(k)) for k in data) if data else 0
    for k, v in data.items():
        pad = " " * (mx - len(str(k)) + 2)
        print("  " + str(k) + pad + ": " + str(v))


def power_bar(consumed, total, width=40):
    if total <= 0:
        return
    pct = min((consumed / total) * 100, 100)
    filled = int(width * pct / 100)
    bar = "X" * filled + "." * (width - filled)
    print("  [" + bar + "] " + "{:.1f}".format(pct) + "%")
    print("  " + str(consumed) + "W de " + str(total) + "W usados")


def show_port_table(ports, compact=False):
    if not ports:
        print("  (sin datos)")
        return

    if compact:
        print("  Cube  Estado       mA   Watts")
        print("  " + "-" * 30)
        for p in ports:
            ind = ">" if p["current_mA"] > 0 else " "
            line = " " + ind
            line += str(p["port"]).ljust(6)
            line += str(p["enabled"]).ljust(9)
            line += str(p["current_mA"]).rjust(5)
            line += ("%.1f" % p["power_W"]).rjust(7)
            print(line)
        total_ma = sum(p["current_mA"] for p in ports)
        total_w = sum(p["power_W"] for p in ports)
        print("  " + "-" * 30)
        print("  TOTAL".ljust(16) + str(total_ma).rjust(5) + ("%.1f" % total_w).rjust(7))
    else:
        print("  Cube  Estado       mA    Watts    Max W Prioridad  PD Type    Inline")
        print("  " + "-" * 70)
        for p in ports:
            active = p["current_mA"] > 0 or p["power_W"] > 0
            ind = ">>>" if active else "   "
            line = ind
            line += str(p["port"]).ljust(6)
            line += str(p["enabled"]).ljust(9)
            line += str(p["current_mA"]).rjust(7)
            line += ("%.1f" % p["power_W"]).rjust(9)
            line += ("%.1f" % p["max_W"]).rjust(9)
            line += " " + str(p["priority"]).ljust(11)
            line += str(p["pd_type"]).ljust(11)
            line += str(p["inline_mode"]).ljust(8)
            print(line)
        print("  " + "-" * 70)


def show_port_detail(port):
    header("Cube " + str(port["port"]) + " - Detalle")
    show_dict({
        "Estado PoE":     port["enabled"],
        "Corriente":      str(port["current_mA"]) + " mA",
        "Potencia":       str(port["power_W"]) + " W",
        "Max asignado":   str(port["max_W"]) + " W",
        "Prioridad":      port["priority"],
        "PD Type":        port["pd_type"],
        "Inline Mode":    port["inline_mode"],
        "PD Class":       port["pd_class"],
        "Extend Mode":    port["extend"],
        "Alimentando PD": "SI" if port["current_mA"] > 0 else "NO",
    })

