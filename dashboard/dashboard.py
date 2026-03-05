#!/usr/bin/env python3
"""
Dashboard: clima + recursos del sistema, lado a lado.
Uso: dashboard [ciudad]
"""

import sys, os, re, time, unicodedata, socket, datetime, json
import urllib.request, urllib.parse
import psutil

# ── Colores ANSI ──────────────────────────────────────────────
R       = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
RED     = "\033[31m"
GREEN   = "\033[32m"
WHITE   = "\033[97m"
MAGENTA = "\033[35m"

S       = f"{DIM} · {R}"   # separador de columna punteado
ANSI_RE = re.compile(r'\033\[[0-9;]*m')

WEATHER_REFRESH = 600   # segundos entre actualizaciones del clima
SYSMON_REFRESH  = 2     # segundos entre actualizaciones del sistema

# ── Ancho visual (considera emoji y ANSI) ─────────────────────
def visual_width(s):
    text = ANSI_RE.sub('', s)
    w = 0
    chars = list(text)
    i = 0
    while i < len(chars):
        cp = ord(chars[i])
        if cp in (0xFE0F, 0xFE0E, 0x200D):     # variation selectors / ZWJ
            i += 1
            continue
        next_vs = i + 1 < len(chars) and ord(chars[i + 1]) == 0xFE0F
        eaw = unicodedata.east_asian_width(chars[i])
        if eaw in ('W', 'F'):
            w += 2
        elif 0x1F000 <= cp <= 0x1FFFF:          # bloque principal de emoji
            w += 2
        elif next_vs and cp > 0x2000:           # símbolo + VS16 → emoji ancho
            w += 2
        elif 0x2300 <= cp <= 0x2BFF and eaw == 'W':
            w += 2
        else:
            w += 1
        i += 1
    return w

def pad_to(line, width):
    vw = visual_width(line)
    return line + ' ' * max(0, width - vw)

# ══════════════════════════════════════════════════════════════
#  PANEL IZQUIERDO — CLIMA
# ══════════════════════════════════════════════════════════════
def get_location_by_ip():
    url = "https://ipapi.co/json/"
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.loads(r.read())
    return {"name": f"{data['city']}, {data['country_name']}",
            "lat": data["latitude"], "lon": data["longitude"]}

def get_location_by_name(city_name):
    q = urllib.parse.urlencode({"name": city_name, "count": 1, "language": "es", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{q}"
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.loads(r.read())
    if not data.get("results"):
        raise ValueError(f'Ciudad no encontrada: "{city_name}"')
    res = data["results"][0]
    return {"name": f"{res['name']}, {res.get('country', '')}",
            "lat": res["latitude"], "lon": res["longitude"]}

def get_weather(lat, lon):
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
        "timezone": "auto", "forecast_days": 11,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())

WMO_CODES = {
    0:  "☀️  Despejado",          1:  "🌤️  May. despejado",
    2:  "⛅ Parc. nublado",       3:  "☁️  Nublado",
    45: "🌫️  Niebla",             48: "🌫️  Niebla c/escarcha",
    51: "🌦️  Llovizna ligera",    53: "🌦️  Llovizna moderada",   55: "🌧️  Llovizna densa",
    61: "🌧️  Lluvia ligera",      63: "🌧️  Lluvia moderada",      65: "🌧️  Lluvia intensa",
    71: "🌨️  Nieve ligera",       73: "🌨️  Nieve moderada",       75: "❄️  Nieve intensa",
    80: "🌦️  Chubascos",          81: "🌧️  Chubascos mod.",       82: "⛈️  Chubascos intensos",
    95: "⛈️  Tormenta",           96: "⛈️  Tormenta c/granizo",   99: "⛈️  Tormenta fuerte",
}
WMO_COLOR = {
    0: YELLOW, 1: YELLOW, 2: CYAN, 3: DIM,
    45: DIM, 48: DIM,
    51: BLUE, 53: BLUE, 55: BLUE, 61: BLUE, 63: BLUE, 65: BLUE,
    71: WHITE, 73: WHITE, 75: WHITE,
    80: BLUE, 81: BLUE, 82: BLUE,
    95: MAGENTA, 96: MAGENTA, 99: MAGENTA,
}

def wtemp_color(t):
    if t >= 35: return RED
    if t >= 25: return YELLOW
    if t >= 15: return GREEN
    if t >= 5:  return CYAN
    return BLUE

def wmo_str(code):
    return f"{WMO_COLOR.get(code, WHITE)}{WMO_CODES.get(code, f'Código {code}')}{R}"

def render_weather(location, data):
    L = []
    cur   = data["current"]
    daily = data["daily"]
    t  = cur["temperature_2m"]
    tc = wtemp_color(t)

    L.append("")
    L.append(f"  📍 {BOLD}{CYAN}Ubicación{R}  : {BOLD}{WHITE}{location['name']}{R}")
    L.append(f"  🕐 {BOLD}{CYAN}Actualizado{R}: {DIM}{cur['time'].replace('T', ' ')}{R}")
    L.append("")
    L.append(f"  {BOLD}{YELLOW}── Clima Actual ────────────────────────────{R}")
    L.append(f"  🌡️  Temperatura  : {BOLD}{tc}{t} °C{R}")
    L.append(f"  🌡️  Sensación    : {tc}{cur['apparent_temperature']} °C{R}")
    L.append(f"  💧 Humedad      : {CYAN}{cur['relative_humidity_2m']} %{R}")
    L.append(f"  💨 Viento       : {GREEN}{cur['wind_speed_10m']} km/h{R}")
    L.append(f"  Condición      : {wmo_str(cur['weather_code'])}")
    L.append("")
    L.append(f"  {BOLD}{YELLOW}── Pronóstico 10 días ──────────────────────{R}")
    L.append(f"  {DIM}{'Fecha':<12}{R}{S}{DIM}🌡️ Máx    {R}{S}{DIM}🌡️ Mín    {R}{S}{DIM}🌧️  Precip.   {R}{S}{DIM}Cond.{R}")
    L.append(f"  {DIM}{'·' * 68}{R}")
    for i, date in enumerate(daily["time"][1:11], start=1):
        from datetime import datetime as _dt
        label  = _dt.strptime(date, "%Y-%m-%d").strftime("%a %d %b")
        tmax   = daily["temperature_2m_max"][i]
        tmin   = daily["temperature_2m_min"][i]
        precip = daily["precipitation_sum"][i]
        cond   = wmo_str(daily["weather_code"][i])
        pc     = BLUE if precip > 0 else DIM
        L.append(
            f"  {WHITE}{label:<12}{R}{S}"
            f"{BOLD}{wtemp_color(tmax)}{tmax:>6.1f}°{R}   {S}"
            f"{wtemp_color(tmin)}{tmin:>6.1f}°{R}   {S}"
            f"{pc}🌧️ {precip:>5.1f} mm{R}   {S}"
            f"{cond}"
        )
    L.append("")
    return L

# ══════════════════════════════════════════════════════════════
#  PANEL DERECHO — SISTEMA
# ══════════════════════════════════════════════════════════════
def bar(percent, width=20):
    filled = int(percent / 100 * width)
    empty  = width - filled
    color  = RED if percent >= 85 else YELLOW if percent >= 60 else GREEN
    return f"{color}{'█' * filled}{DIM}{'░' * empty}{R} {color}{percent:5.1f}%{R}"

def stemp_color(t):
    if t >= 85: return RED
    if t >= 70: return YELLOW
    if t >= 50: return CYAN
    return GREEN

def fmt_bytes(b):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024: return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def fmt_uptime(sec):
    d, h, m = int(sec // 86400), int((sec % 86400) // 3600), int((sec % 3600) // 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)

def get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        for key in ("coretemp", "k10temp", "cpu_thermal"):
            if key in temps:
                pkg = next((t for t in temps[key] if "Package" in t.label or t.label == ""), None)
                return (pkg or temps[key][0]).current
    except Exception:
        pass
    return None

def sec_title(icon, title):
    return f"\n  {BOLD}{YELLOW}{icon} {title} {'─' * (40 - len(title))}─{R}"

def render_sysmon(cpu_pct):
    L = []
    now     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uptime  = fmt_uptime(datetime.datetime.now().timestamp() - psutil.boot_time())
    freq    = psutil.cpu_freq()
    temp    = get_cpu_temp()
    mem     = psutil.virtual_memory()
    swap    = psutil.swap_memory()
    lc, pc  = psutil.cpu_count(logical=True), psutil.cpu_count(logical=False)

    L.append("")
    L.append(f"  💻 {BOLD}{CYAN}Host{R}      : {BOLD}{WHITE}{socket.gethostname()}{R}")
    L.append(f"  🕐 {BOLD}{CYAN}Fecha/Hora{R}: {DIM}{now}{R}")
    L.append(f"  ⏱️  {BOLD}{CYAN}Uptime{R}    : {DIM}{uptime}{R}")

    # CPU
    for line in sec_title("⚙️ ", "CPU").splitlines():
        L.append(line)
    freq_str = f"{freq.current:.0f} MHz" if freq else "N/A"
    L.append(f"  🖥️  Núcleos : {WHITE}{pc} físicos · {lc} lógicos{R}  {DIM}{freq_str}{R}")
    L.append(f"  📊 Uso     : {bar(cpu_pct)}")
    if temp is not None:
        L.append(f"  🌡️  Temp.   : {BOLD}{stemp_color(temp)}{temp:.1f} °C{R}")

    # Memoria
    for line in sec_title("🧠", "Memoria").splitlines():
        L.append(line)
    L.append(f"  📊 RAM  : {bar(mem.percent)}  {DIM}{fmt_bytes(mem.used)} / {fmt_bytes(mem.total)}{R}")
    L.append(f"  📊 Swap : {bar(swap.percent)}  {DIM}{fmt_bytes(swap.used)} / {fmt_bytes(swap.total)}{R}")

    # Disco
    for line in sec_title("💾", "Disco").splitlines():
        L.append(line)
    for p in psutil.disk_partitions():
        if "squashfs" in p.fstype or "loop" in p.device:
            continue
        try:
            u   = psutil.disk_usage(p.mountpoint)
            dev = os.path.basename(p.device)
            lbl = f"{p.mountpoint} ({dev})"
            L.append(f"  📊 {lbl:<18}: {bar(u.percent)}  {DIM}{fmt_bytes(u.used)}/{fmt_bytes(u.total)}{R}")
        except PermissionError:
            pass

    # Red
    for line in sec_title("🌐", "Red").splitlines():
        L.append(line)
    L.append(f"  {DIM}{'Interfaz':<16}{R}{S}{DIM}📤 Enviado      {R}{S}{DIM}📥 Recibido{R}")
    L.append(f"  {DIM}{'·' * 52}{R}")
    for name, io in psutil.net_io_counters(pernic=True).items():
        if name == "lo":
            continue
        L.append(f"  {WHITE}{name:<16}{R}{S}{GREEN}{fmt_bytes(io.bytes_sent):>12}{R}   {S}{CYAN}{fmt_bytes(io.bytes_recv):>12}{R}")

    # Procesos
    for line in sec_title("📋", "Top Procesos").splitlines():
        L.append(line)
    L.append(f"  {DIM}{'PID':<7}{R}{S}{DIM}{'Nombre':<20}{R}{S}{DIM}{'CPU':>7}{R}{S}{DIM}{'Mem':>7}{R}{S}{DIM}Estado{R}")
    L.append(f"  {DIM}{'·' * 58}{R}")
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except Exception:
            pass
    procs.sort(key=lambda x: x["cpu_percent"] or 0, reverse=True)
    for p in procs[:8]:
        cpu = p["cpu_percent"] or 0
        mp  = p["memory_percent"] or 0
        nm  = (p["name"] or "")[:19]
        cc  = RED if cpu > 50 else YELLOW if cpu > 20 else GREEN
        mc  = RED if mp > 20 else YELLOW if mp > 10 else CYAN
        L.append(
            f"  {DIM}{p['pid']:<7}{R}{S}"
            f"{WHITE}{nm:<20}{R}{S}"
            f"{BOLD}{cc}{cpu:>5.1f}%{R}  {S}"
            f"{mc}{mp:>5.1f}%{R}  {S}"
            f"{DIM}{p['status']}{R}"
        )
    L.append("")
    return L

# ══════════════════════════════════════════════════════════════
#  LAYOUT LADO A LADO
# ══════════════════════════════════════════════════════════════
def get_term_width():
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 160

def display(left, right):
    term_w  = get_term_width()
    panel_w = (term_w - 3) // 2
    sep     = f" {DIM}║{R} "
    for i in range(max(len(left), len(right))):
        l = left[i]  if i < len(left)  else ""
        r = right[i] if i < len(right) else ""
        print(f"{pad_to(l, panel_w)}{sep}{r}")

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    city = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    print(f"\n  {DIM}Obteniendo datos del clima...{R}")
    try:
        location     = get_location_by_name(city) if city else get_location_by_ip()
        weather_data = get_weather(location["lat"], location["lon"])
    except Exception as e:
        print(f"\n  {RED}Error: {e}{R}\n")
        sys.exit(1)

    last_weather = time.time()
    psutil.cpu_percent(interval=None)   # primera lectura de calibración

    try:
        while True:
            # Refrescar clima cada WEATHER_REFRESH segundos
            if time.time() - last_weather > WEATHER_REFRESH:
                try:
                    weather_data = get_weather(location["lat"], location["lon"])
                    last_weather = time.time()
                except Exception:
                    pass

            cpu_pct = psutil.cpu_percent(interval=1)    # bloquea 1 seg (mide CPU real)
            left    = render_weather(location, weather_data)
            right   = render_sysmon(cpu_pct)

            print("\033[2J\033[H", end="", flush=True)  # limpiar pantalla
            display(left, right)

            remaining = SYSMON_REFRESH - 1
            if remaining > 0:
                time.sleep(remaining)

    except KeyboardInterrupt:
        print("\033[2J\033[H", end="")
        print(f"\n  {DIM}Dashboard cerrado.{R}\n")

if __name__ == "__main__":
    main()
