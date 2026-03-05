#!/usr/bin/env python3
"""
Monitor de recursos del sistema.
Uso: sysmon
"""

import psutil
import socket
import datetime
import os

# ── Colores ANSI ──────────────────────────────────────────────
R      = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
RED    = "\033[31m"
GREEN  = "\033[32m"
WHITE  = "\033[97m"
MAGENTA= "\033[35m"

S = f"{DIM} · {R}"  # separador de columna punteado


def bar(percent, width=20):
    filled = int(percent / 100 * width)
    empty = width - filled
    if percent >= 85:   color = RED
    elif percent >= 60: color = YELLOW
    else:               color = GREEN
    return f"{color}{'█' * filled}{DIM}{'░' * empty}{R} {color}{percent:5.1f}%{R}"


def temp_color(t):
    if t >= 85:  return RED
    if t >= 70:  return YELLOW
    if t >= 50:  return CYAN
    return GREEN


def fmt_bytes(b):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def fmt_uptime(seconds):
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
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
                if pkg:
                    return pkg.current
                return temps[key][0].current
    except Exception:
        pass
    return None


def get_main_disks():
    disks = []
    for p in psutil.disk_partitions():
        if "squashfs" in p.fstype or "loop" in p.device:
            continue
        try:
            usage = psutil.disk_usage(p.mountpoint)
            disks.append((p.mountpoint, p.device, usage))
        except PermissionError:
            pass
    return disks


def get_net_interfaces():
    stats = psutil.net_io_counters(pernic=True)
    ifaces = []
    for name, io in stats.items():
        if name == "lo":
            continue
        ifaces.append((name, io.bytes_sent, io.bytes_recv))
    return ifaces


def get_top_processes(n=8):
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu_percent"] or 0, reverse=True)
    return procs[:n]


def print_section(title, icon):
    print(f"\n  {BOLD}{YELLOW}{icon} {title} {'─' * (44 - len(title))}─{R}")


def main():
    # ── Muestreo inicial de CPU ──────────────────────────────
    psutil.cpu_percent(interval=None)
    import time; time.sleep(0.5)

    now      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = socket.gethostname()
    uptime   = fmt_uptime(datetime.datetime.now().timestamp() - psutil.boot_time())
    cpu_pct  = psutil.cpu_percent(interval=None)
    cpu_freq = psutil.cpu_freq()
    cpu_temp = get_cpu_temp()
    mem      = psutil.virtual_memory()
    swap     = psutil.swap_memory()
    cpu_count_l = psutil.cpu_count(logical=True)
    cpu_count_p = psutil.cpu_count(logical=False)

    print()
    print(f"  💻 {BOLD}{CYAN}Host{R}       : {BOLD}{WHITE}{hostname}{R}")
    print(f"  🕐 {BOLD}{CYAN}Fecha/Hora{R} : {DIM}{now}{R}")
    print(f"  ⏱️  {BOLD}{CYAN}Uptime{R}     : {DIM}{uptime}{R}")

    # ── CPU ──────────────────────────────────────────────────
    print_section("CPU", "⚙️ ")
    freq_str = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A"
    print(f"  🖥️  Núcleos    : {WHITE}{cpu_count_p} físicos · {cpu_count_l} lógicos{R}   {DIM}{freq_str}{R}")
    print(f"  📊 Uso        : {bar(cpu_pct)}")
    if cpu_temp is not None:
        tc = temp_color(cpu_temp)
        print(f"  🌡️  Temperatura : {BOLD}{tc}{cpu_temp:.1f} °C{R}")

    # ── Memoria ──────────────────────────────────────────────
    print_section("Memoria", "🧠")
    print(f"  📊 RAM        : {bar(mem.percent)}  {DIM}{fmt_bytes(mem.used)} / {fmt_bytes(mem.total)}{R}")
    print(f"  📊 Swap       : {bar(swap.percent)}  {DIM}{fmt_bytes(swap.used)} / {fmt_bytes(swap.total)}{R}")

    # ── Disco ────────────────────────────────────────────────
    print_section("Disco", "💾")
    for mount, device, usage in get_main_disks():
        dev_short = os.path.basename(device)
        label = f"{mount} ({dev_short})"
        print(f"  📊 {label:<18}: {bar(usage.percent)}  {DIM}{fmt_bytes(usage.used)} / {fmt_bytes(usage.total)}{R}")

    # ── Red ──────────────────────────────────────────────────
    print_section("Red", "🌐")
    ifaces = get_net_interfaces()
    if ifaces:
        print(f"  {DIM}{'Interfaz':<16}{R}{S}{DIM}📤 Enviado         {R}{S}{DIM}📥 Recibido{R}")
        print(f"  {DIM}{'·' * 55}{R}")
        for name, sent, recv in ifaces:
            print(f"  {WHITE}{name:<16}{R}{S}{GREEN}{fmt_bytes(sent):>14}{R}   {S}{CYAN}{fmt_bytes(recv):>14}{R}")

    # ── Procesos ─────────────────────────────────────────────
    print_section("Top Procesos", "📋")
    procs = get_top_processes()
    print(f"  {DIM}{'PID':<7}{R}{S}{DIM}{'Nombre':<22}{R}{S}{DIM}{'CPU':>8}{R}{S}{DIM}{'Memoria':>8}{R}{S}{DIM}Estado{R}")
    print(f"  {DIM}{'·' * 60}{R}")
    for p in procs:
        cpu  = p["cpu_percent"] or 0
        mem_p = p["memory_percent"] or 0
        name = (p["name"] or "")[:21]
        status = p["status"] or ""
        cc = RED if cpu > 50 else YELLOW if cpu > 20 else GREEN
        mc = RED if mem_p > 20 else YELLOW if mem_p > 10 else CYAN
        print(
            f"  {DIM}{p['pid']:<7}{R}{S}"
            f"{WHITE}{name:<22}{R}{S}"
            f"{BOLD}{cc}{cpu:>6.1f}%{R}  {S}"
            f"{mc}{mem_p:>6.1f}%{R}  {S}"
            f"{DIM}{status}{R}"
        )

    print()


if __name__ == "__main__":
    main()
