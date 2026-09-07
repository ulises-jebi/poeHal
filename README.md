# poeHal

CLI y librería Python para monitoreo y control de cubos PoE en el switch **PLANET IGS-4215-8UP2T2S**.

Los 8 puertos PoE++ se exponen como **cube1 .. cube8**.

Usa SNMP + Web Scraping para obtener datos en tiempo real de consumo, corriente, temperatura y estado de cada cubo.

---

## Instalación en Linux (Ubuntu / Raspberry Pi OS)

```bash
git clone https://github.com/ulises-jebi/poeHal.git
cd poeHal
chmod +x install.sh uninstall.sh
sudo ./install.sh
```

El instalador automáticamente:
- Verifica que haya un Python compatible (**3.8 a 3.11**)
- Instala el paquete en tu home con `pip install --user`
- Deja disponibles el comando `poeHal` **y** el `import poeHal`
- Limpia la instalación antigua (`/opt/poeHal` y su wrapper)
- Crea `/etc/poeHal/config.ini` con permisos `600`
- Copia `examples/minimo.py` al home como **`~/poeTest.py`**, para tener una
  prueba rápida a mano sin entrar a la carpeta del proyecto

Después de instalar, **editar las credenciales** y ejecutar desde cualquier
directorio:
```bash
sudo nano /etc/poeHal/config.ini
poeHal -r status
```

### Desinstalación Linux
```bash
sudo ./uninstall.sh
```

---

## Instalación en Windows

1. Instalar [Python 3.11](https://www.python.org/downloads/) (marcar "Add to PATH")
2. Abrir una terminal en la carpeta del proyecto e instalar el paquete:
```cmd
py -3.11 -m pip install --user .
```

Eso deja el comando `poeHal` y el `import poeHal` disponibles. Después,
desde cualquier directorio:
```cmd
poeHal -r status
```

Las credenciales van en `%USERPROFILE%\.config\poeHal\config.ini`, o en las
variables `POEHAL_USER` / `POEHAL_PASS`.

---

## Uso

```bash
# Lectura
poeHal -r status              # Resumen rápido
poeHal -r cubes               # Tabla detallada de cubos
poeHal -r cube3               # Detalle del cubo 3
poeHal -r power               # Datos de potencia
poeHal -r system              # Info del sistema
poeHal -r watch,5             # Monitor en vivo cada 5s
poeHal -r csv                 # Exportar snapshot a CSV
poeHal -r log                 # Agregar línea al log continuo

# Escritura
poeHal -w cube3,1             # Encender cubo 3
poeHal -w cube3,0             # Apagar cubo 3
poeHal -w cube3,r             # Reiniciar cubo 3 (off/on 5s)
poeHal -w cube3,r,10          # Reiniciar con espera de 10s
poeHal -w cube1,1 cube5,0     # Múltiples cubos a la vez

# Ayuda
poeHal help
```

> La sintaxis vieja `portN` ya no existe. Si la usas, poeHal te indica el
> `cubeN` equivalente.

## Uso como librería Python

```python
import poeHal as hal

hal.cube1On()               # encender
hal.cube1Off()              # apagar
hal.cube1Restart()          # off, espera 5s, on
hal.cube1Restart(wait=10)   # con espera propia
```

Están las 24 variantes, de `cube1On()` a `cube8Restart()`. También las
genéricas, útiles para iterar:

```python
for n in range(5, 9):
    hal.cubeOff(n)
```

Lectura:

```python
hal.power()      # {'pse': 'ON', 'nominal_W': 360, 'consumed_W': 47, 'percent': 13.1}
hal.cubes()      # lista de los 8 cubos: mA, W, prioridad, clase PD...
hal.cube(3)      # solo el cubo 3
hal.status()     # potencia + temperaturas + los 8 cubos
hal.system()     # descripción, nombre y uptime por SNMP
```

Las credenciales salen de la configuración normal, así que no hay que pasarlas.
Para apuntar a otro switch en runtime:

```python
hal.configure(host="192.168.1.50")
hal.reset()      # fuerza reconexión
```

### Ejemplos ejecutables

En `examples/` hay dos scripts listos para correr en el RevPi:

```bash
python3 ~/poeTest.py                          # copia que deja el instalador
python3 examples/minimo.py                    # 4 lineas: on, espera, off
python3 examples/prueba_paquete.py            # recorre toda la API, solo lectura
python3 examples/prueba_paquete.py --cube 5   # + prueba escritura en el cubo 5
```

`prueba_paquete.py` es seguro por defecto: solo lee. La escritura hay que
pedirla con `--cube N`, y se niega a tocar los cubos 1 a 4 (que suelen tener
dispositivos conectados) salvo que agregues `--force`. Después de escribir
compara los otros 7 cubos contra un snapshot previo, que es la comprobación
que importa: cada escritura reenvía la configuración de los 8 puertos.

### Errores

La librería **lanza excepciones**, no termina el proceso:

```python
try:
    hal.cube1On()
except hal.ConfigError:
    ...   # faltan credenciales, o el config tiene permisos inseguros
except hal.ConnectionFailed:
    ...   # el switch no responde, o el login fue rechazado
```

Ambas heredan de `hal.PoEHalError`. La conexión es perezosa: `import poeHal`
no toca la red, la primera llamada real es la que conecta.

## Requisitos

- **Python 3.8 a 3.11** (`pysnmp` 4.4.12 no funciona en 3.12+)
- Acceso de red al switch (192.168.1.103)
- SNMP habilitado en el switch (community: public)
- **Linux:** Ubuntu / Debian / Raspberry Pi OS (64-bit)
- **Windows:** Windows 10/11 con Python 3.11 instalado

## Configuración y credenciales

**El código no contiene credenciales.** Se leen de un archivo fuera del
repositorio, protegido con permisos `600` (solo root).

El instalador crea la plantilla automáticamente. Solo hay que editarla:

```bash
sudo nano /etc/poeHal/config.ini
```

```ini
[switch]
host       = 192.168.1.103
snmp_port  = 161
community  = public
timeout    = 5
retries    = 2

web_user   = jebi
web_pass   = TU_PASSWORD
```

### Orden de búsqueda

| Prioridad | Origen |
|---|---|
| 1 | Variables de entorno `POEHAL_USER`, `POEHAL_PASS`, `POEHAL_HOST`, `POEHAL_COMMUNITY` |
| 2 | `$POEHAL_CONFIG` (ruta explícita) |
| 3 | `~/.config/poeHal/config.ini` |
| 4 | `/etc/poeHal/config.ini` |

Alternativa sin archivo, útil para scripts:

```bash
export POEHAL_USER='jebi'
export POEHAL_PASS='tu-password'
poeHal -r status
```

### Protecciones

- `config.ini` está en `.gitignore`: no puede subirse a git por accidente.
- poeHal **se niega a arrancar** si el archivo es legible por otros usuarios,
  e indica el `chmod` exacto para corregirlo.
- Sin credenciales válidas, aborta con instrucciones en vez de fallar de forma
  silenciosa.
- `poeHal help` funciona siempre, incluso sin configuración, y muestra de dónde
  se están leyendo los datos.

> **Nota sobre el transporte:** la interfaz web del switch usa HTTP plano y SNMP
> v2c usa community en texto claro. Proteger el archivo evita que la contraseña
> se filtre por el repositorio o el disco, pero **no** la protege en la red. Usar
> este equipo solo en un segmento OT aislado.

## Pruebas

### Sin switch ni red

Verifica la capa de configuración y credenciales. No necesita el switch, ni red,
ni `pysnmp`: las dependencias se stubean, así que corre en cualquier Python 3.8+.

```bash
python3 tests/test_config.py
```

Comprueba, entre otras cosas, que `help` funciona sin configuración, que un
comando real aborta con instrucciones cuando faltan credenciales, que un
`config.ini` legible por otros usuarios (`644` o `640`) es rechazado, que las
variables de entorno tienen prioridad sobre el archivo, y que el código fuente
no contiene credenciales.

### Contra el switch real

Requiere Python 3.8-3.11 y acceso de red al switch. Verificar primero que el
paquete quedó bien instalado:

```bash
python3 -c "import poeHal, pysnmp.hlapi; print('OK', poeHal.__version__)"
```

Luego, la prueba de credenciales:

```bash
poeHal -r cubes
```

> **Ojo:** si `-r cubes` no imprime nada, es un **fallo**, no un éxito. El
> comando no muestra nada cuando el scraping falla, así que la salida vacía
> significa que el login fue rechazado.

Para los comandos de escritura, usar solo cubos sin dispositivos conectados:
cada escritura reenvía la configuración de los 8 puertos, así que conviene
comparar `poeHal -r cubes` antes y después para confirmar que solo cambió el
cubo que se tocó.

## Estructura del proyecto

```
poeHal/
├── poeHal/
│   ├── __init__.py     # API publica: cubeNOn/Off/Restart, status, power, cubes
│   ├── cli.py          # Comandos y punto de entrada del CLI
│   ├── clients.py      # SNMPClient, WebPoEClient, connect()
│   ├── config.py       # Carga de configuración y credenciales
│   ├── display.py      # Salida en texto plano
│   └── errors.py       # PoEHalError, ConfigError, ConnectionFailed
├── pyproject.toml      # Metadata del paquete y entry point del CLI
├── config.ini.example  # Plantilla de configuración (sin credenciales reales)
├── requirements.txt    # Dependencias (equivalente a las del pyproject)
├── install.sh          # Instalador Linux (pip --user + config 600)
├── uninstall.sh        # Desinstalador Linux
├── .gitignore          # Protege config.ini y artefactos locales
├── examples/
│   ├── minimo.py       # Ejemplo minimo: on / off
│   └── prueba_paquete.py  # Recorrido completo de la API
├── tests/
│   └── test_config.py  # Pruebas sin switch ni red
└── README.md
```
