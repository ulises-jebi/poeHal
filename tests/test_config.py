#!/usr/bin/env python3
"""
Pruebas de la capa de configuracion de poeHal.

No requiere el switch, ni red, ni pysnmp: se stubean las dependencias.
Corre en cualquier Python 3.8+.

Uso:  python3 tests/test_config.py [/ruta/a/poeHal]
"""
import os
import re
import subprocess
import sys
import tempfile
import textwrap

REPO = (sys.argv[1] if len(sys.argv) > 1
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(REPO, "poeHal.py")

results = []


def make_stubs(d):
    """Stubs minimos para pysnmp y requests, que no estan instalados aqui."""
    os.makedirs(os.path.join(d, "pysnmp"), exist_ok=True)
    open(os.path.join(d, "pysnmp", "__init__.py"), "w").close()
    with open(os.path.join(d, "pysnmp", "hlapi.py"), "w") as f:
        f.write(textwrap.dedent("""
            class _X:
                def __init__(self, *a, **k): pass
            SnmpEngine = CommunityData = UdpTransportTarget = ContextData = _X
            ObjectType = ObjectIdentity = _X
            def getCmd(*a, **k): return iter([])
            def nextCmd(*a, **k): return iter([])
        """))
    with open(os.path.join(d, "requests.py"), "w") as f:
        f.write(textwrap.dedent("""
            class _C:
                def get(self, k): return None
                def set(self, k, v): pass
            class Session:
                def __init__(self): self.headers = {}; self.cookies = _C()
                def post(self, *a, **k): raise RuntimeError("stub")
                def get(self, *a, **k): raise RuntimeError("stub")
        """))


def run(stub_dir, args, env_extra=None, code=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = stub_dir
    for k in ("POEHAL_USER", "POEHAL_PASS", "POEHAL_HOST",
              "POEHAL_COMMUNITY", "POEHAL_CONFIG"):
        env.pop(k, None)
    env.update(env_extra or {})
    if code:
        cmd = [sys.executable, "-c", code]
        env["PYTHONPATH"] = stub_dir + os.pathsep + REPO
    else:
        cmd = [sys.executable, SCRIPT] + args
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=REPO)
    return p.returncode, p.stdout + p.stderr


def check(name, condition, detail=""):
    results.append((name, condition))
    mark = "PASS" if condition else "FAIL"
    line = "  [" + mark + "] " + name
    if detail and not condition:
        line += "\n         " + detail.strip().replace("\n", "\n         ")
    print(line)


def main():
    if not os.path.isfile(SCRIPT):
        print("No se encontro " + SCRIPT)
        return 1

    tmp = tempfile.mkdtemp(prefix="poehal-test-")
    stub = os.path.join(tmp, "stub")
    os.makedirs(stub, exist_ok=True)
    make_stubs(stub)

    cfg = os.path.join(tmp, "config.ini")
    with open(cfg, "w") as f:
        f.write(textwrap.dedent("""
            [switch]
            host = 10.0.0.5
            snmp_port = 1610
            community = secreto
            web_user = usuario-archivo
            web_pass = pass-archivo
        """))

    print("\n=== Capa de configuracion ===")

    # 1. help debe funcionar sin ninguna configuracion
    rc, out = run(stub, ["help"], {"POEHAL_CONFIG": "/nonexistent"})
    check("help funciona sin configuracion",
          rc == 0 and "PoE CLI Tool" in out, out)

    # 2. sin credenciales, un comando real aborta con instrucciones
    rc, out = run(stub, ["-r", "status"], {"POEHAL_CONFIG": "/nonexistent"})
    check("sin credenciales aborta con exit!=0",
          rc != 0 and "No hay credenciales" in out, out)
    check("el mensaje de error explica como arreglarlo",
          "POEHAL_USER" in out and "chmod 600" in out, out)

    # 3. el codigo fuente no contiene credenciales
    #    Generico a proposito: no se escribe ningun password real en este
    #    archivo, porque tambien se sube al repositorio.
    src = open(SCRIPT, encoding="utf-8").read()
    hardcoded = [v for v in
                 re.findall(r'"web_(?:user|pass)"\s*:\s*"([^"]+)"', src)
                 if not v.startswith("POEHAL_")]   # ENV_OVERRIDES no son credenciales
    check("poeHal.py no tiene credenciales hardcodeadas",
          not hardcoded,
          "encontrado: " + repr(hardcoded))
    check("poeHal.py lee las credenciales de la configuracion",
          "POEHAL_USER" in src and "configparser" in src)

    # 4. permisos 600 -> aceptado
    os.chmod(cfg, 0o600)
    rc, out = run(stub, ["help"], {"POEHAL_CONFIG": cfg})
    check("config con permisos 600 es aceptada",
          rc == 0 and "10.0.0.5" in out, out)

    # 5. permisos 644 -> rechazado
    os.chmod(cfg, 0o644)
    rc, out = run(stub, ["-r", "ports"], {"POEHAL_CONFIG": cfg})
    check("config con permisos 644 es rechazada",
          rc != 0 and "Permisos inseguros" in out, out)
    check("el rechazo indica el chmod exacto", "chmod 600" in out, out)

    # 6. permisos 640 (grupo) -> tambien rechazado
    os.chmod(cfg, 0o640)
    rc, out = run(stub, ["-r", "ports"], {"POEHAL_CONFIG": cfg})
    check("config legible por grupo (640) es rechazada",
          rc != 0 and "Permisos inseguros" in out, out)

    # 7. los valores del archivo se cargan de verdad
    os.chmod(cfg, 0o600)
    probe = ("import poeHal, json;"
             "print(json.dumps(poeHal.SWITCH_CONFIG))")
    rc, out = run(stub, [], {"POEHAL_CONFIG": cfg}, code=probe)
    check("valores del archivo cargados",
          '"host": "10.0.0.5"' in out and '"web_pass": "pass-archivo"' in out, out)
    check("snmp_port convertido a entero", '"snmp_port": 1610' in out, out)

    # 8. las variables de entorno ganan sobre el archivo
    rc, out = run(stub, [], {"POEHAL_CONFIG": cfg,
                             "POEHAL_USER": "usuario-env",
                             "POEHAL_PASS": "pass-env"}, code=probe)
    check("variables de entorno sobreescriben el archivo",
          '"web_user": "usuario-env"' in out and '"web_pass": "pass-env"' in out, out)
    check("el archivo sigue aportando lo no sobreescrito",
          '"host": "10.0.0.5"' in out, out)

    # 9. valor invalido no revienta, cae al default
    bad = os.path.join(tmp, "bad.ini")
    with open(bad, "w") as f:
        f.write("[switch]\nsnmp_port = no-es-numero\nweb_user = u\nweb_pass = p\n")
    os.chmod(bad, 0o600)
    rc, out = run(stub, [], {"POEHAL_CONFIG": bad}, code=probe)
    check("snmp_port invalido cae al default 161",
          rc == 0 and '"snmp_port": 161' in out, out)

    # 10. .gitignore protege config.ini
    gi = os.path.join(REPO, ".gitignore")
    check(".gitignore existe", os.path.isfile(gi))
    if os.path.isfile(gi):
        check(".gitignore incluye config.ini",
              "config.ini" in open(gi, encoding="utf-8").read())

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("\n  " + str(passed) + "/" + str(total) + " pruebas pasaron\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
