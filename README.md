# poeHal

CLI tool para monitoreo y control de puertos PoE en el switch **PLANET IGS-4215-8UP2T2S**.

Usa SNMP + Web Scraping para obtener datos en tiempo real de consumo, corriente, temperatura y estado de cada puerto PoE++.

---

## Instalación en Linux (Ubuntu / Raspberry Pi OS)

```bash
git clone https://github.com/ulises-jebi/poeHal.git
cd poeHal
chmod +x install.sh uninstall.sh
sudo ./install.sh
```

El instalador automáticamente:
- Verifica e instala Python 3.11+ si no está presente
- Crea un entorno virtual aislado en `/opt/poeHal/venv/`
- Instala todas las dependencias dentro del venv
- Registra el comando `poeHal` en el PATH del sistema
- Crea `/etc/poeHal/config.ini` con permisos `600` (solo root)

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
2. Abrir una terminal en la carpeta del proyecto e instalar dependencias:
```cmd
py -3.11 -m pip install -r requirements.txt
```
3. Agregar la carpeta del proyecto al PATH del sistema, o copiar `poeHal.bat` y `poeHal.py` a una carpeta que ya esté en el PATH (ej: `C:\Program Files\poeHal\`)

Después de instalar, ejecutar desde cualquier directorio:
```cmd
poeHal -r status
```

---

## Uso

```bash
# Lectura
poeHal -r status              # Resumen rápido
poeHal -r ports               # Tabla detallada de puertos
poeHal -r port3               # Detalle del puerto 3
poeHal -r power               # Datos de potencia
poeHal -r system              # Info del sistema
poeHal -r watch,5             # Monitor en vivo cada 5s
poeHal -r csv                 # Exportar snapshot a CSV
poeHal -r log                 # Agregar línea al log continuo

# Escritura
poeHal -w port3,1             # Habilitar puerto 3
poeHal -w port3,0             # Deshabilitar puerto 3
poeHal -w port3,r             # Reiniciar puerto 3 (off/on 5s)
poeHal -w port3,r,10          # Reiniciar con espera de 10s
poeHal -w port1,1 port5,0    # Múltiples puertos a la vez

# Ayuda
poeHal help
```

## Requisitos

- **Python 3.11+** (en Linux el instalador lo resuelve automáticamente)
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

Requiere Python 3.11 y acceso de red al switch. Verificar primero que el venv
quedó en la versión correcta:

```bash
/opt/poeHal/venv/bin/python -c "import pysnmp.hlapi; print('OK')"
```

Luego, la prueba de credenciales:

```bash
poeHal -r ports
```

> **Ojo:** si `-r ports` no imprime nada, es un **fallo**, no un éxito. El
> comando no muestra nada cuando el scraping falla, así que la salida vacía
> significa que el login fue rechazado.

Para los comandos de escritura, usar solo puertos sin dispositivos conectados:
cada escritura reenvía la configuración de los 8 puertos, así que conviene
comparar `poeHal -r ports` antes y después para confirmar que solo cambió el
puerto que se tocó.

## Estructura del proyecto

```
poeHal/
├── poeHal.py           # Script principal
├── poeHal.bat          # Launcher para Windows
├── config.ini.example  # Plantilla de configuración (sin credenciales reales)
├── requirements.txt    # Dependencias Python
├── install.sh          # Instalador Linux (venv + comando global + config 600)
├── uninstall.sh        # Desinstalador Linux
├── .gitignore          # Protege config.ini y artefactos locales
├── tests/
│   └── test_config.py  # Pruebas de la capa de configuración (sin switch)
└── README.md
```
