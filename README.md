# DesarrollosClaude

Scripts de terminal desarrollados con Claude Code. Todos usan solo librerías estándar de Python (excepto `sysmon` y `dashboard` que requieren `psutil`), no requieren API keys y están listos para usar desde cualquier lugar del sistema.

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

## Requisitos

- Python 3.6+
- `psutil` (para `sysmon` y `dashboard`): `pip install psutil`
- Conexión a internet (para `weather` y `dashboard`)
- APIs utilizadas: [Open-Meteo](https://open-meteo.com/) (clima, gratuita, sin API key)
