#!/usr/bin/env python3
"""
Script de clima: temperatura actual y pronóstico de 10 días.
Uso: weather [ciudad]
Ejemplo: weather "Ciudad de México"
         weather "New York"
         weather  (usa tu ubicación actual por IP)
"""

import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime

# ── Colores ANSI ──────────────────────────────────────────────
R  = "\033[0m"       # reset
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RED = "\033[31m"
GREEN = "\033[32m"
WHITE = "\033[97m"
DIM = "\033[2m"
MAGENTA = "\033[35m"


def temp_color(t):
    if t >= 35:   return RED
    if t >= 25:   return YELLOW
    if t >= 15:   return GREEN
    if t >= 5:    return CYAN
    return BLUE


def get_location_by_ip():
    url = "https://ipapi.co/json/"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        return {
            "name": f"{data['city']}, {data['country_name']}",
            "lat": data["latitude"],
            "lon": data["longitude"],
        }
    except Exception as e:
        print(f"{RED}Error al obtener ubicación por IP: {e}{R}")
        sys.exit(1)


def get_location_by_name(city_name):
    query = urllib.parse.urlencode({"name": city_name, "count": 1, "language": "es", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        if not data.get("results"):
            print(f'{RED}No se encontró la ciudad: "{city_name}"{R}')
            sys.exit(1)
        result = data["results"][0]
        return {
            "name": f"{result['name']}, {result.get('country', '')}",
            "lat": result["latitude"],
            "lon": result["longitude"],
        }
    except Exception as e:
        print(f"{RED}Error al buscar la ciudad: {e}{R}")
        sys.exit(1)


def get_weather(lat, lon):
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
        "timezone": "auto",
        "forecast_days": 11,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"{RED}Error al obtener datos del clima: {e}{R}")
        sys.exit(1)


WMO_CODES = {
    0:  "☀️  Despejado", 1:  "🌤️  Mayormente despejado", 2: "⛅ Parcialmente nublado", 3: "☁️  Nublado",
    45: "🌫️  Niebla", 48: "🌫️  Niebla con escarcha",
    51: "🌦️  Llovizna ligera", 53: "🌦️  Llovizna moderada", 55: "🌧️  Llovizna densa",
    61: "🌧️  Lluvia ligera", 63: "🌧️  Lluvia moderada", 65: "🌧️  Lluvia intensa",
    71: "🌨️  Nieve ligera", 73: "🌨️  Nieve moderada", 75: "❄️  Nieve intensa",
    80: "🌦️  Chubascos ligeros", 81: "🌧️  Chubascos moderados", 82: "⛈️  Chubascos intensos",
    95: "⛈️  Tormenta eléctrica", 96: "⛈️  Tormenta con granizo", 99: "⛈️  Tormenta con granizo fuerte",
}

WMO_COLOR = {
    0: YELLOW, 1: YELLOW, 2: CYAN, 3: DIM,
    45: DIM, 48: DIM,
    51: BLUE, 53: BLUE, 55: BLUE,
    61: BLUE, 63: BLUE, 65: BLUE,
    71: WHITE, 73: WHITE, 75: WHITE,
    80: BLUE, 81: BLUE, 82: BLUE,
    95: MAGENTA, 96: MAGENTA, 99: MAGENTA,
}


def wmo_description(code):
    desc = WMO_CODES.get(code, f"Código {code}")
    color = WMO_COLOR.get(code, WHITE)
    return f"{color}{desc}{R}"


def print_weather(location, data):
    cur = data["current"]
    daily = data["daily"]

    t = cur["temperature_2m"]
    tc = temp_color(t)

    print()
    print(f"  📍 {BOLD}{CYAN}Ubicación{R}  : {BOLD}{WHITE}{location['name']}{R}")
    print(f"  🕐 {BOLD}{CYAN}Fecha/Hora{R} : {DIM}{cur['time'].replace('T', ' ')}{R}")
    print()
    print(f"  {BOLD}{YELLOW}── Clima Actual ──────────────────────────────────{R}")
    print(f"  🌡️  Temperatura  : {BOLD}{tc}{t} °C{R}")
    print(f"  🌡️  Sensación    : {tc}{cur['apparent_temperature']} °C{R}")
    print(f"  💧 Humedad      : {CYAN}{cur['relative_humidity_2m']} %{R}")
    print(f"  💨 Viento       : {GREEN}{cur['wind_speed_10m']} km/h{R}")
    print(f"  Condición      : {wmo_description(cur['weather_code'])}")
    print()
    S = f"{DIM} · {R}"  # separador de columna punteado

    print(f"  {BOLD}{YELLOW}── Pronóstico 10 días ────────────────────────────{R}")
    print(f"  {DIM}{'Fecha':<12}{R}{S}{DIM}🌡️ Máx    {R}{S}{DIM}🌡️ Mín    {R}{S}{DIM}🌧️  Precip.   {R}{S}{DIM}Condición{R}")
    print(f"  {DIM}{'·' * 72}{R}")

    for i, date in enumerate(daily["time"][1:11], start=1):
        dt = datetime.strptime(date, "%Y-%m-%d")
        label = dt.strftime("%a %d %b")
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        precip = daily["precipitation_sum"][i]
        cond = wmo_description(daily["weather_code"][i])
        pc = BLUE if precip > 0 else DIM
        print(
            f"  {WHITE}{label:<12}{R}{S}"
            f"{BOLD}{temp_color(tmax)}{tmax:>6.1f}°{R}   {S}"
            f"{temp_color(tmin)}{tmin:>6.1f}°{R}   {S}"
            f"{pc}🌧️ {precip:>5.1f} mm{R}   {S}"
            f"{cond}"
        )

    print()


def main():
    if len(sys.argv) > 1:
        city = " ".join(sys.argv[1:])
        location = get_location_by_name(city)
    else:
        location = get_location_by_ip()

    data = get_weather(location["lat"], location["lon"])
    print_weather(location, data)


if __name__ == "__main__":
    main()
