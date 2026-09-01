# poeHal

CLI tool para monitoreo y control de puertos PoE en el switch **PLANET IGS-4215-8UP2T2S**.

Usa SNMP + Web Scraping para obtener datos en tiempo real de consumo, corriente, temperatura y estado de cada puerto PoE++.

---

## Instalación en Linux (Ubuntu / Raspberry Pi OS)

```bash
git clone https://github.com/TU-USUARIO/poeHal.git
cd poeHal
chmod +x install.sh uninstall.sh
sudo ./install.sh
```

El instalador automáticamente:
- Verifica e instala Python 3.11+ si no está presente
- Crea un entorno virtual aislado en `/opt/poeHal/venv/`
- Instala todas las dependencias dentro del venv
- Registra el comando `poeHal` en el PATH del sistema

Después de instalar, ejecutar desde cualquier directorio:
```bash
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
- Acceso de red al switch (192.168.1.90)
- SNMP habilitado en el switch (community: public)
- **Linux:** Ubuntu / Debian / Raspberry Pi OS (64-bit)
- **Windows:** Windows 10/11 con Python 3.11 instalado

## Configuración

La IP del switch y credenciales se configuran en `SWITCH_CONFIG` dentro de `poeHal.py`:

```python
SWITCH_CONFIG = {
    "host":       "192.168.1.90",
    "snmp_port":  161,
    "community":  "public",
    "web_user":   "jebi",
    "web_pass":   "***PASSWORD-PURGADO***",
}
```

## Estructura del proyecto

```
poeHal/
├── poeHal.py          # Script principal
├── poeHal.bat         # Launcher para Windows
├── requirements.txt    # Dependencias Python
├── install.sh          # Instalador Linux (crea venv + comando global)
├── uninstall.sh        # Desinstalador Linux
└── README.md
```
