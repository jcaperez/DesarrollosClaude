#!/usr/bin/env python3
"""
snapclean — Elimina software instalado por Snap y Flatpak.

Uso: sudo snapclean [--snap-only] [--flatpak-only] [--yes]
     --snap-only     Solo limpiar Snap
     --flatpak-only  Solo limpiar Flatpak
     --yes           No pedir confirmación (modo automático)
"""

import sys, os, subprocess, shutil

# ── Colores ANSI ──────────────────────────────────────────────
R       = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
GREEN   = "\033[32m"
WHITE   = "\033[97m"

def section(icon, title):
    print(f"\n  {BOLD}{YELLOW}{icon} {title} {'─' * (50 - len(title))}{R}")

def ok(msg):    print(f"  {GREEN}✔{R}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{R}  {msg}")
def bad(msg):   print(f"  {RED}✘{R}  {BOLD}{msg}{R}")
def info(msg):  print(f"  {CYAN}ℹ{R}  {msg}")
def dim(msg):   print(f"  {DIM}{msg}{R}")

def run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)

def confirm(prompt):
    try:
        resp = input(f"\n  {YELLOW}{prompt} [s/N]{R} ").strip().lower()
        return resp in ("s", "si", "sí", "y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        return False

def fmt_size(path):
    """Tamaño de un directorio en MB."""
    try:
        result = run(["du", "-sb", path])
        if result.returncode == 0:
            bytes_ = int(result.stdout.split()[0])
            return f"{bytes_ / 1024 / 1024:.1f} MB"
    except Exception:
        pass
    return "N/A"

# ══════════════════════════════════════════════════════════════
#  SNAP
# ══════════════════════════════════════════════════════════════

# Paquetes de sistema que no deben eliminarse (requeridos por snapd)
SNAP_CORE = {"snapd", "core", "core18", "core20", "core22", "core24", "bare"}

def snap_available():
    return shutil.which("snap") is not None

def get_snap_packages():
    result = run(["snap", "list"])
    if result.returncode != 0:
        return [], []
    lines = result.stdout.strip().splitlines()[1:]  # saltar encabezado
    user_pkgs = []
    core_pkgs = []
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        version = parts[1] if len(parts) > 1 else "N/A"
        if name in SNAP_CORE:
            core_pkgs.append((name, version))
        else:
            user_pkgs.append((name, version))
    return user_pkgs, core_pkgs

def get_snap_revisions(name):
    """Obtiene revisiones antiguas (disabled) de un paquete snap."""
    result = run(["snap", "list", "--all", name])
    revisions = []
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4 and "disabled" in line:
                revisions.append(parts[2])  # número de revisión
    return revisions

def remove_snap_old_revisions(name, auto):
    revisions = get_snap_revisions(name)
    if not revisions:
        return 0
    removed = 0
    for rev in revisions:
        result = run(["snap", "remove", name, f"--revision={rev}"])
        if result.returncode == 0:
            removed += 1
            ok(f"Revisión antigua eliminada: {name} rev.{rev}")
        else:
            warn(f"No se pudo eliminar {name} rev.{rev}: {result.stderr.strip()}")
    return removed

def remove_snap_package(name):
    result = run(["snap", "remove", "--purge", name])
    if result.returncode == 0:
        ok(f"Eliminado: {BOLD}{name}{R}")
        return True
    else:
        bad(f"Error eliminando {name}: {result.stderr.strip()}")
        return False

def clean_snap_cache():
    cache_dir = "/var/lib/snapd/cache"
    if os.path.isdir(cache_dir):
        size = fmt_size(cache_dir)
        result = run(["find", cache_dir, "-type", "f", "-delete"])
        if result.returncode == 0:
            ok(f"Caché de snap limpiado ({size})")
        else:
            warn("No se pudo limpiar el caché de snap completamente")

def handle_snap(auto):
    section("📦", "Snap")

    if not snap_available():
        dim("Snap no está instalado en este sistema.")
        return 0

    user_pkgs, core_pkgs = get_snap_packages()

    if not user_pkgs:
        ok("No hay paquetes snap de usuario instalados.")
    else:
        print(f"\n  {CYAN}Paquetes a eliminar:{R}")
        for name, version in user_pkgs:
            print(f"    {RED}✘{R} {BOLD}{name:<30}{R} {DIM}{version}{R}")

    if core_pkgs:
        print(f"\n  {CYAN}Paquetes de sistema (se conservarán):{R}")
        for name, version in core_pkgs:
            print(f"    {GREEN}●{R} {DIM}{name:<30} {version}{R}")

    # Revisiones antiguas
    all_snap_names = [n for n, _ in user_pkgs] + [n for n, _ in core_pkgs]
    old_revs = {}
    for name in all_snap_names:
        revs = get_snap_revisions(name)
        if revs:
            old_revs[name] = revs

    if old_revs:
        print(f"\n  {CYAN}Revisiones antiguas detectadas:{R}")
        for name, revs in old_revs.items():
            print(f"    {YELLOW}↩{R} {name}: revisiones {', '.join(revs)}")

    removed = 0

    # Eliminar paquetes de usuario
    if user_pkgs:
        if auto or confirm(f"¿Eliminar {len(user_pkgs)} paquete(s) snap de usuario?"):
            print()
            for name, _ in user_pkgs:
                if remove_snap_package(name):
                    removed += 1

    # Eliminar revisiones antiguas
    if old_revs:
        if auto or confirm(f"¿Eliminar revisiones antiguas de {len(old_revs)} paquete(s)?"):
            print()
            for name in old_revs:
                remove_snap_old_revisions(name, auto)

    # Limpiar caché
    if auto or confirm("¿Limpiar caché de snap?"):
        print()
        clean_snap_cache()

    return removed

# ══════════════════════════════════════════════════════════════
#  FLATPAK
# ══════════════════════════════════════════════════════════════

def flatpak_available():
    return shutil.which("flatpak") is not None

def get_flatpak_packages():
    result = run(["flatpak", "list", "--columns=application,name,version,installation"])
    if result.returncode != 0:
        return []
    pkgs = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            app_id   = parts[0].strip()
            name     = parts[1].strip()
            version  = parts[2].strip()
            install  = parts[3].strip() if len(parts) > 3 else "system"
            pkgs.append({"id": app_id, "name": name, "version": version, "install": install})
    return pkgs

def remove_flatpak_package(app_id, installation):
    flag = "--system" if installation == "system" else "--user"
    result = run(["flatpak", "uninstall", flag, "-y", app_id])
    if result.returncode == 0:
        ok(f"Eliminado: {BOLD}{app_id}{R}")
        return True
    else:
        bad(f"Error eliminando {app_id}: {result.stderr.strip()}")
        return False

def clean_flatpak_unused():
    """Elimina runtimes y extensiones sin usar."""
    result = run(["flatpak", "uninstall", "--unused", "-y"])
    if result.returncode == 0:
        out = result.stdout.strip()
        if "Nothing" in out or not out:
            ok("No hay runtimes sin usar.")
        else:
            ok("Runtimes y extensiones sin usar eliminados.")
    else:
        warn("No se pudieron eliminar componentes sin usar.")

def clean_flatpak_cache():
    cache_dirs = [
        os.path.expanduser("~/.var/app"),
        "/var/tmp/flatpak-cache",
    ]
    for d in cache_dirs:
        if os.path.isdir(d):
            size = fmt_size(d)
            try:
                shutil.rmtree(d)
                ok(f"Caché eliminado: {d} ({size})")
            except Exception as e:
                warn(f"No se pudo eliminar {d}: {e}")

def handle_flatpak(auto):
    section("📦", "Flatpak")

    if not flatpak_available():
        dim("Flatpak no está instalado en este sistema.")
        return 0

    pkgs = get_flatpak_packages()

    if not pkgs:
        ok("No hay paquetes flatpak instalados.")
        return 0

    print(f"\n  {CYAN}Paquetes a eliminar:{R}")
    for p in pkgs:
        print(f"    {RED}✘{R} {BOLD}{p['name']:<30}{R} {DIM}{p['id']}  {p['version']}{R}")

    removed = 0

    if auto or confirm(f"¿Eliminar {len(pkgs)} paquete(s) flatpak?"):
        print()
        for p in pkgs:
            if remove_flatpak_package(p["id"], p["install"]):
                removed += 1

    if auto or confirm("¿Eliminar runtimes y extensiones sin usar?"):
        print()
        clean_flatpak_unused()

    if auto or confirm("¿Limpiar datos de caché de flatpak?"):
        print()
        clean_flatpak_cache()

    return removed

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    if os.geteuid() != 0:
        print(f"\n  {RED}Este script requiere permisos de root.{R}")
        print(f"  Usa: {BOLD}sudo snapclean{R}\n")
        sys.exit(1)

    args        = sys.argv[1:]
    auto        = "--yes" in args
    snap_only   = "--snap-only" in args
    flatpak_only= "--flatpak-only" in args

    print()
    print(f"  {BOLD}{CYAN}╔══════════════════════════════════════════════════╗{R}")
    print(f"  {BOLD}{CYAN}║     🧹 snapclean — Limpieza de Snap y Flatpak   ║{R}")
    print(f"  {BOLD}{CYAN}╚══════════════════════════════════════════════════╝{R}")

    if not auto:
        warn("Este script eliminará paquetes de forma permanente.")
        warn("Los paquetes del sistema snap (core, snapd, etc.) se conservarán.")
        if not confirm("¿Deseas continuar?"):
            print(f"\n  {DIM}Cancelado.{R}\n")
            sys.exit(0)

    total = 0

    if not flatpak_only:
        total += handle_snap(auto)

    if not snap_only:
        total += handle_flatpak(auto)

    section("✅", "Resumen")
    if total > 0:
        ok(f"Paquetes eliminados: {BOLD}{total}{R}")
    else:
        info("No se eliminó ningún paquete.")
    print()


if __name__ == "__main__":
    main()
