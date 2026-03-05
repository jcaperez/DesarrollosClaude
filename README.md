# DesarrollosClaude

Scripts de terminal desarrollados con Claude Code. Están listos para usar desde cualquier lugar del sistema.

---

## Scripts

### 🌤️ weather — Clima actual y pronóstico

Muestra la temperatura actual y el pronóstico de los próximos 10 días para tu ubicación o cualquier ciudad que especifiques.

**Instalación:**
```bash
sudo cp weather/weather.py /usr/local/bin/weather
```

**Uso:**
```bash
weather                   # ubicación actual (por IP)
weather "Santiago"
weather "Ciudad de México"
weather "Tokyo"
```

**Muestra:**
- Temperatura, sensación térmica, humedad y viento actuales
- Pronóstico de 10 días con máxima, mínima y precipitación
- Colores según temperatura e íconos por condición climática

---

### 🖥️ sysmon — Monitor de recursos del sistema

Muestra el estado actual del sistema en un único vistazo.

**Dependencia:**
```bash
pip install psutil
```

**Instalación:**
```bash
sudo cp sysmon/sysmon.py /usr/local/bin/sysmon
```

**Uso:**
```bash
sysmon
```

**Muestra:**
- CPU: núcleos, frecuencia, uso y temperatura
- Memoria RAM y Swap con barras visuales
- Disco: uso por partición
- Red: bytes enviados/recibidos por interfaz
- Top 8 procesos por consumo de CPU

---

### 📊 dashboard — Dashboard persistente

Combina el clima y el monitor de sistema en un dashboard lado a lado que se actualiza en tiempo real.

**Dependencia:**
```bash
pip install psutil
```

**Instalación:**
```bash
sudo cp dashboard/dashboard.py /usr/local/bin/dashboard
```

**Uso:**
```bash
dashboard                 # ubicación actual (por IP)
dashboard "Nueva York"
```

**Comportamiento:**
- Panel izquierdo: clima (se refresca cada 10 minutos)
- Panel derecho: sistema (se refresca cada 2 segundos)
- `Ctrl+C` para salir
- Requiere terminal de ~140 columnas o más

---

### 🔍 netscan — Auditoría de seguridad de red

Analiza la red local en busca de dispositivos activos, servicios expuestos y vulnerabilidades conocidas. Genera un reporte con severidad, recomendaciones y enlaces a fuentes oficiales (CVE, OWASP, documentación del fabricante).

> ⚠️ **Uso ético:** Este script está diseñado para auditoría defensiva de redes propias. No lo uses en redes sin autorización explícita.

**Dependencias:**
```bash
sudo apt install nmap python3-netifaces
```

**Instalación:**
```bash
sudo cp netscan/netscan.py /usr/local/bin/netscan
```

**Uso:**
```bash
sudo netscan                    # detecta la subred automáticamente
sudo netscan 192.168.1.0/24     # subred específica
```

**Fases del análisis:**
1. **Descubrimiento** — Detecta todos los hosts activos con IP, MAC y fabricante
2. **Análisis de servicios** — Escanea puertos críticos, detecta versiones y sistema operativo
3. **Detección de vulnerabilidades** — Evalúa servicios inseguros y ejecuta scripts NSE de nmap

**Detecta entre otros:**
- Servicios sin cifrado: Telnet, FTP, VNC, POP3, IMAP
- Bases de datos expuestas: MySQL, PostgreSQL, MongoDB, Redis
- Vulnerabilidades críticas: EternalBlue, Heartbleed, Shellshock, POODLE
- Software desactualizado: OpenSSH, OpenSSL
- Configuraciones inseguras: FTP anónimo, MySQL sin contraseña, MongoDB sin auth

**Cada hallazgo incluye:**
- Nivel de severidad: `CRÍTICA` / `ALTA` / `MEDIA` / `BAJA`
- Descripción del riesgo
- Recomendación de mitigación
- Enlaces a CVE, OWASP, documentación oficial y guías de solución

---

### 🧹 snapclean — Limpieza de Snap y Flatpak

Elimina de forma segura todo el software instalado por Snap y Flatpak, incluyendo revisiones antiguas, runtimes sin usar y caché. Muestra un listado de lo que se va a eliminar y pide confirmación en cada paso.

**Instalación:**
```bash
sudo cp snapclean/snapclean.py /usr/local/bin/snapclean
```

**Uso:**
```bash
sudo snapclean                  # interactivo, confirma cada paso
sudo snapclean --snap-only      # solo limpia snap
sudo snapclean --flatpak-only   # solo limpia flatpak
sudo snapclean --yes            # elimina todo sin preguntar
```

**Qué limpia:**
- **Snap:** paquetes de usuario, revisiones antiguas deshabilitadas y caché
- **Flatpak:** paquetes instalados, runtimes/extensiones sin usar y caché

> Los paquetes de sistema de snap (`core`, `snapd`, `bare`, etc.) se conservan siempre automáticamente.

---

## Requisitos

| Script       | Python | Dependencias externas                        | Internet |
|--------------|--------|----------------------------------------------|----------|
| `weather`    | 3.6+   | Ninguna (solo stdlib)                        | Sí       |
| `sysmon`     | 3.6+   | `psutil`                                     | No       |
| `dashboard`  | 3.6+   | `psutil`                                     | Sí       |
| `netscan`    | 3.6+   | `nmap`, `python3-netifaces`                  | No       |
| `snapclean`  | 3.6+   | Ninguna (usa `snap` y `flatpak` del sistema) | No       |

**Instalación de dependencias:**
```bash
pip install psutil
sudo apt install nmap python3-netifaces
```

**APIs utilizadas:** [Open-Meteo](https://open-meteo.com/) — clima gratuito, sin API key.
