"""Los dos transportes hacia el switch: SNMP y scraping web."""

import re
import time
from datetime import timedelta

import requests
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity, getCmd, nextCmd,
)

from .config import SWITCH_CONFIG, require_credentials
from .errors import ConnectionFailed

PRIORITY_MAP   = {0: "Critical", 1: "High", 2: "Low"}
PD_TYPE_MAP    = {0: "Standard", 1: "Legacy", 2: "Force"}
INLINE_MAP     = {0: "End-Span", 1: "Mid-Span", 3: "BT"}
POE_MODE_MAP   = {0: "Disable", 1: "Enable", 2: "Schedule"}
PSE_STATUS_MAP = {1: "ON", 2: "OFF", 3: "FAULTY"}

SYSTEM_OIDS = {
    "sysDescr":  "1.3.6.1.2.1.1.1.0",
    "sysName":   "1.3.6.1.2.1.1.5.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
}

POE_MAIN_OIDS = {
    "pethMainPsePower":            "1.3.6.1.2.1.105.1.3.1.1.2",
    "pethMainPseOperStatus":       "1.3.6.1.2.1.105.1.3.1.1.3",
    "pethMainPseConsumptionPower": "1.3.6.1.2.1.105.1.3.1.1.4",
}


# ==============================================================
# SNMP CLIENT
# ==============================================================
class SNMPClient:
    def __init__(self, config):
        self.engine = SnmpEngine()
        self.community = CommunityData(config["community"], mpModel=1)
        self.transport = UdpTransportTarget(
            (config["host"], config["snmp_port"]),
            timeout=config["timeout"], retries=config["retries"],
        )
        self.context = ContextData()

    def get(self, oid):
        err_ind, err_st, _, var_binds = next(
            getCmd(self.engine, self.community, self.transport,
                   self.context, ObjectType(ObjectIdentity(oid))))
        if err_ind:
            raise ConnectionError("SNMP: " + str(err_ind))
        if err_st:
            raise RuntimeError("SNMP: " + err_st.prettyPrint())
        return var_binds[0][1]

    def walk(self, oid):
        results = []
        for (err_ind, err_st, _, var_binds) in nextCmd(
            self.engine, self.community, self.transport,
            self.context, ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        ):
            if err_ind or err_st:
                break
            for vb in var_binds:
                results.append((str(vb[0]), vb[1]))
        return results

    def test(self):
        try:
            return self.get(SYSTEM_OIDS["sysDescr"]) is not None
        except Exception:
            return False

    def get_system_info(self):
        info = {}
        for name, oid in SYSTEM_OIDS.items():
            try:
                val = self.get(oid)
                if name == "sysUpTime":
                    info[name] = str(timedelta(seconds=int(val) / 100))
                else:
                    info[name] = str(val)
            except Exception as e:
                info[name] = "ERROR: " + str(e)
        return info

    def get_poe_general(self):
        result = {}
        for name, base_oid in POE_MAIN_OIDS.items():
            try:
                rows = self.walk(base_oid)
                if rows:
                    val = int(rows[0][1])
                    if name == "pethMainPseOperStatus":
                        result[name] = PSE_STATUS_MAP.get(val, str(val))
                    else:
                        result[name] = val
            except Exception:
                result[name] = "N/A"
        return result


# ==============================================================
# WEB CLIENT
# ==============================================================
class WebPoEClient:
    def __init__(self, config, verbose=False):
        # verbose=True  -> imprime el progreso (lo usa el CLI)
        # verbose=False -> silencioso, solo devuelve valores (libreria)
        self.verbose = verbose
        self.base_url = "http://" + config["host"]
        self.cgi_url = self.base_url + "/cgi-bin/dispatcher.cgi"
        self.user = config["web_user"]
        self.password = config["web_pass"]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Connection": "keep-alive",
        })
        self._logged_in = False

    def login(self):
        try:
            resp = self.session.post(
                self.cgi_url + "?cmd=1",
                data={"username": self.user, "password": self.password, "login": "1"},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self.base_url,
                    "Referer": self.cgi_url + "?cmd=0",
                },
                timeout=10, allow_redirects=True,
            )
            hid = self.session.cookies.get("hid")
            if hid:
                resp_poe = self.session.get(
                    self.cgi_url + "?cmd=9216",
                    headers={"Referer": self.cgi_url + "?cmd=9"},
                    timeout=10,
                )
                if resp_poe.status_code == 200 and "poeDelivering" in resp_poe.text:
                    self._logged_in = True
                    return True
            if not self._logged_in:
                set_cookie = resp.headers.get("Set-Cookie", "")
                hid_match = re.search("hid=([0-9a-fA-F]+)", set_cookie)
                if hid_match:
                    self.session.cookies.set("hid", hid_match.group(1))
                    self._logged_in = True
                    return True
            return False
        except Exception as e:
            if self.verbose:
                print("  Error login: " + str(e))
            return False

    def _ensure_login(self):
        if not self._logged_in:
            if not self.login():
                raise ConnectionError("No se pudo hacer login web")

    def _extract_js_array(self, html, var_name):
        pattern = "var " + var_name + " = new Array\\(([^)]+)\\)"
        m = re.search(pattern, html)
        if m:
            return [v.strip() for v in m.group(1).split(",")]
        return []

    def _extract_js_var(self, html, var_name):
        pattern = "var " + var_name + " = ([^;\\n]+)"
        m = re.search(pattern, html)
        if m:
            return m.group(1).strip()
        return None

    def _get_poe_page(self):
        self._ensure_login()
        resp = self.session.get(
            self.cgi_url + "?cmd=9216",
            headers={"Referer": self.cgi_url + "?cmd=9"},
            timeout=10,
        )
        if resp.status_code == 200 and "poeDelivering" in resp.text:
            return resp.text
        self._logged_in = False
        self._ensure_login()
        resp = self.session.get(
            self.cgi_url + "?cmd=9216",
            headers={"Referer": self.cgi_url + "?cmd=9"},
            timeout=10,
        )
        if resp.status_code == 200 and "poeDelivering" in resp.text:
            return resp.text
        return None

    def fetch_poe_data(self):
        html = self._get_poe_page()
        if not html:
            return None

        data = {
            "numPorts":     int(self._extract_js_var(html, "numPorts") or 8),
            "powerBudget":  int(self._extract_js_var(html, "powerBudget") or 0),
            "poeAdmin":     int(self._extract_js_var(html, "poeAdmin") or 0),
            "poeMode":      int(self._extract_js_var(html, "poeMode") or 0),
            "maxBudget":    int(self._extract_js_var(html, "MaxBudget") or 0),
            "temperature0": self._extract_js_var(html, "poeTemperature0"),
            "temperature1": self._extract_js_var(html, "poeTemperature1"),
        }

        arrays = {}
        for name in ["poeDelivering", "poeConsumption", "poeAllocation",
                      "poeEnabled", "poePriority", "poeClass",
                      "poeInline", "poePDType", "poeExtend", "poeProfile"]:
            arrays[name] = self._extract_js_array(html, name)

        ports = []
        for i in range(data["numPorts"]):
            port = {
                "port":        i + 1,
                "enabled":     POE_MODE_MAP.get(int(arrays["poeEnabled"][i]), "?") if i < len(arrays["poeEnabled"]) else "?",
                "current_mA":  int(arrays["poeDelivering"][i]) if i < len(arrays["poeDelivering"]) else 0,
                "power_W":     int(arrays["poeConsumption"][i]) / 10 if i < len(arrays["poeConsumption"]) else 0,
                "max_W":       int(arrays["poeAllocation"][i]) / 10 if i < len(arrays["poeAllocation"]) else 0,
                "priority":    PRIORITY_MAP.get(int(arrays["poePriority"][i]), "?") if i < len(arrays["poePriority"]) else "?",
                "pd_class":    int(arrays["poeClass"][i]) if i < len(arrays["poeClass"]) else 0,
                "inline_mode": INLINE_MAP.get(int(arrays["poeInline"][i]), "?") if i < len(arrays["poeInline"]) else "?",
                "pd_type":     PD_TYPE_MAP.get(int(arrays["poePDType"][i]), "?") if i < len(arrays["poePDType"]) else "?",
                "extend":      "On" if i < len(arrays["poeExtend"]) and arrays["poeExtend"][i] == "1" else "Off",
            }
            if port["pd_class"] == 255:
                port["pd_class"] = "--"
            ports.append(port)

        data["ports"] = ports
        return data

    def set_port_state(self, port_number, enable):
        if port_number < 1 or port_number > 8:
            if self.verbose:
                print("  Cube" + str(port_number) + ": Error - puerto invalido")
            return False
        try:
            html = self._get_poe_page()
            if not html:
                if self.verbose:
                    print("  Cube" + str(port_number) + ": Error - no se pudo leer estado")
                return False

            idx = port_number - 1
            poe_enabled    = self._extract_js_array(html, "poeEnabled")
            poe_priority   = self._extract_js_array(html, "poePriority")
            poe_allocation = self._extract_js_array(html, "poeAllocation")
            poe_inline     = self._extract_js_array(html, "poeInline")
            poe_pd_type    = self._extract_js_array(html, "poePDType")
            poe_extend     = self._extract_js_array(html, "poeExtend")
            poe_profile    = self._extract_js_array(html, "poeProfile")

            old_val = poe_enabled[idx] if idx < len(poe_enabled) else "?"
            new_val = "1" if enable else "0"
            old_str = POE_MODE_MAP.get(int(old_val), old_val)
            new_str = "Enable" if enable else "Disable"
            poe_enabled[idx] = new_val

            payload = {
                "cmd":         "9217",
                "enAdmin":     self._extract_js_var(html, "poeAdmin") or "0",
                "poeMode":     self._extract_js_var(html, "poeMode") or "1",
                "opt":         self._extract_js_var(html, "OTP_config") or "150",
                "powerbudget": self._extract_js_var(html, "powerBudget") or "240",
            }

            for i in range(len(poe_enabled)):
                payload["poe_en_" + str(i)]         = poe_enabled[i]
                payload["poe_profile_" + str(i)]    = poe_profile[i] if i < len(poe_profile) else "0"
                payload["poe_inline_" + str(i)]     = poe_inline[i] if i < len(poe_inline) else "3"
                payload["poe_pd_type_" + str(i)]    = poe_pd_type[i] if i < len(poe_pd_type) else "0"
                payload["poe_extend_" + str(i)]     = poe_extend[i] if i < len(poe_extend) else "0"
                payload["poe_priority_" + str(i)]   = poe_priority[i] if i < len(poe_priority) else "0"
                alloc_raw = int(poe_allocation[i]) if i < len(poe_allocation) else 950
                payload["poe_allocation_" + str(i)] = str(int(alloc_raw / 10))

            self.session.post(
                self.cgi_url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self.base_url,
                    "Referer": self.cgi_url + "?cmd=9216",
                },
                timeout=10, allow_redirects=True,
            )

            time.sleep(1)
            html_check = self._get_poe_page()
            if html_check:
                new_enabled = self._extract_js_array(html_check, "poeEnabled")
                actual = new_enabled[idx] if idx < len(new_enabled) else "?"
                expected = "1" if enable else "0"
                if actual == expected:
                    if self.verbose:
                        print("  Cube" + str(port_number) + ": " + old_str + " -> " + new_str + " : OK")
                    return True
                else:
                    if self.verbose:
                        print("  Cube" + str(port_number) + ": " + old_str + " -> " + new_str + " : FAIL")
                    return False
            if self.verbose:
                print("  Cube" + str(port_number) + ": " + old_str + " -> " + new_str + " : OK")
            return True
        except Exception as e:
            if self.verbose:
                print("  Cube" + str(port_number) + ": Error - " + str(e))
            return False

    def restart_port(self, port_number, wait=5):
        if self.verbose:
            print("  Cube" + str(port_number) + ": Restart (espera " + str(wait) + "s)...")
        if self.set_port_state(port_number, False):
            time.sleep(wait)
            return self.set_port_state(port_number, True)
        return False



# ==============================================================
# CONEXION
# ==============================================================
def connect(verbose=False):
    """Abre los dos transportes. Lanza ConfigError o ConnectionFailed;
    nunca termina el proceso."""
    require_credentials()
    snmp = SNMPClient(SWITCH_CONFIG)
    if not snmp.test():
        raise ConnectionFailed(
            "SNMP no responde en " + SWITCH_CONFIG["host"]
            + ":" + str(SWITCH_CONFIG["snmp_port"]))
    web = WebPoEClient(SWITCH_CONFIG, verbose=verbose)
    if not web.login():
        raise ConnectionFailed(
            "Login web rechazado en http://" + SWITCH_CONFIG["host"]
            + " (usuario '" + SWITCH_CONFIG["web_user"] + "')")
    return snmp, web
