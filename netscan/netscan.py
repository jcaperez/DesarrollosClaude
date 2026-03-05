#!/usr/bin/env python3
"""
netscan — Análisis de seguridad de red (auditoría defensiva).

Uso: sudo netscan [subred]
     sudo netscan              (detecta la subred automáticamente)
     sudo netscan 192.168.1.0/24

Requiere: nmap, python3-netifaces
"""

import sys, os, re, subprocess, json, socket, datetime
import xml.etree.ElementTree as ET
import netifaces

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

S = f"{DIM} · {R}"

def section(icon, title):
    print(f"\n  {BOLD}{YELLOW}{icon} {title} {'─' * (50 - len(title))}{R}")

def ok(msg):   print(f"  {GREEN}✔{R}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{R}  {msg}")
def bad(msg):  print(f"  {RED}✘{R}  {BOLD}{msg}{R}")
def info(msg): print(f"  {CYAN}ℹ{R}  {msg}")
def dim(msg):  print(f"  {DIM}{msg}{R}")

# ── Severidad ─────────────────────────────────────────────────
SEV_COLOR = {"CRÍTICA": RED, "ALTA": MAGENTA, "MEDIA": YELLOW, "BAJA": CYAN, "INFO": DIM}

def sev(level, msg):
    c = SEV_COLOR.get(level, DIM)
    print(f"  {BOLD}{c}[{level}]{R} {msg}")

# ── Detección automática de subred ────────────────────────────
def detect_subnet():
    for iface in netifaces.interfaces():
        if iface == "lo":
            continue
        addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
        for addr in addrs:
            ip      = addr.get("addr", "")
            netmask = addr.get("netmask", "")
            if ip and netmask and not ip.startswith("127."):
                # Calcular CIDR
                parts   = [int(x) for x in netmask.split(".")]
                cidr    = sum(bin(p).count("1") for p in parts)
                ip_parts = [int(x) for x in ip.split(".")]
                mask_parts = parts
                net_parts = [str(ip_parts[i] & mask_parts[i]) for i in range(4)]
                subnet  = f"{'.'.join(net_parts)}/{cidr}"
                return subnet, ip, iface
    return None, None, None

# ── Obtener fabricante desde MAC (OUI local con nmap) ─────────
def get_vendor(mac):
    if not mac or mac == "unknown":
        return "Desconocido"
    try:
        result = subprocess.run(
            ["nmap", "--script-help", "broadcast-*"],
            capture_output=True, text=True
        )
    except Exception:
        pass
    # nmap ya incluye vendor en el XML, se extrae desde ahí
    return "N/A"

# ── Escaneo de descubrimiento (ping sweep) ────────────────────
def discover_hosts(subnet):
    info(f"Escaneando subred {BOLD}{subnet}{R} ...")
    cmd = ["nmap", "-sn", "--oX", "-", subnet]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout
    except subprocess.TimeoutExpired:
        bad("Timeout en descubrimiento de hosts")
        return ""
    except Exception as e:
        bad(f"Error en descubrimiento: {e}")
        return ""

# ── Escaneo de puertos y servicios ───────────────────────────
def scan_host(ip):
    info(f"Escaneando puertos en {BOLD}{ip}{R} ...")
    cmd = [
        "nmap", "-sV", "-sC",
        "--version-intensity", "5",
        "-O", "--osscan-guess",
        "-p", "21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,"
              "1723,3306,3389,5432,5900,5901,6379,8080,8443,8888,27017",
        "--oX", "-",
        "--host-timeout", "60s",
        ip
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout
    except subprocess.TimeoutExpired:
        warn(f"Timeout escaneando {ip}")
        return ""
    except Exception as e:
        bad(f"Error escaneando {ip}: {e}")
        return ""

# ── Parser XML de nmap ────────────────────────────────────────
def parse_hosts_xml(xml_data):
    hosts = []
    try:
        root = ET.fromstring(xml_data)
        for host in root.findall("host"):
            status = host.find("status")
            if status is None or status.get("state") != "up":
                continue
            ip, mac, vendor, hostname = "", "", "", ""
            for addr in host.findall("address"):
                if addr.get("addrtype") == "ipv4":
                    ip = addr.get("addr", "")
                elif addr.get("addrtype") == "mac":
                    mac    = addr.get("addr", "")
                    vendor = addr.get("vendor", "Desconocido")
            hostnames = host.find("hostnames")
            if hostnames is not None:
                hn = hostnames.find("hostname")
                if hn is not None:
                    hostname = hn.get("name", "")
            if ip:
                hosts.append({"ip": ip, "mac": mac, "vendor": vendor, "hostname": hostname})
    except ET.ParseError:
        pass
    return hosts

def parse_ports_xml(xml_data):
    result = {"ports": [], "os": "", "scripts": []}
    try:
        root = ET.fromstring(xml_data)
        host = root.find("host")
        if host is None:
            return result
        # OS
        osmatch = host.find("os/osmatch")
        if osmatch is not None:
            result["os"] = f"{osmatch.get('name','')} ({osmatch.get('accuracy','')}%)"
        # Puertos
        ports_el = host.find("ports")
        if ports_el is not None:
            for port in ports_el.findall("port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue
                svc   = port.find("service") or {}
                portnum  = port.get("portid", "")
                protocol = port.get("protocol", "")
                name     = svc.get("name", "") if isinstance(svc, ET.Element) else ""
                product  = svc.get("product", "") if isinstance(svc, ET.Element) else ""
                version  = svc.get("version", "") if isinstance(svc, ET.Element) else ""
                extra    = svc.get("extrainfo", "") if isinstance(svc, ET.Element) else ""
                # Scripts NSE
                scripts = []
                for script in port.findall("script"):
                    scripts.append({"id": script.get("id",""), "output": script.get("output","")})
                result["ports"].append({
                    "port": portnum, "proto": protocol,
                    "name": name, "product": product,
                    "version": version, "extra": extra,
                    "scripts": scripts
                })
    except ET.ParseError:
        pass
    return result

# ── Análisis de vulnerabilidades por servicio ─────────────────
# Formato: "puerto": (título, severidad, recomendación, [referencias])
INSECURE_SERVICES = {
    "21": (
        "FTP sin cifrar", "ALTA",
        "Reemplazar con SFTP (puerto 22). FTP transmite credenciales en texto plano.",
        [
            "https://owasp.org/www-community/vulnerabilities/Cleartext_Transmission_of_Sensitive_Information",
            "https://www.techtarget.com/searchnetworking/tip/How-to-replace-FTP-with-more-secure-protocols",
            "https://man.openbsd.org/sftp",
        ]
    ),
    "23": (
        "Telnet sin cifrar", "CRÍTICA",
        "Reemplazar con SSH (puerto 22). Telnet transmite todo en texto plano, incluyendo contraseñas.",
        [
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=telnet",
            "https://www.ssh.com/academy/ssh/telnet",
            "https://owasp.org/www-community/vulnerabilities/Cleartext_Transmission_of_Sensitive_Information",
        ]
    ),
    "25": (
        "SMTP abierto", "MEDIA",
        "Verificar que no sea un open relay. Configurar autenticación SMTP y TLS obligatorio.",
        [
            "https://www.cloudflare.com/es-es/learning/email-security/smtp-security/",
            "https://www.rapid7.com/db/vulnerabilities/smtp-open-relay/",
            "https://mxtoolbox.com/problem/smtp/",
        ]
    ),
    "110": (
        "POP3 sin cifrar", "ALTA",
        "Usar POP3S (puerto 995) con TLS. El tráfico POP3 incluye credenciales en texto plano.",
        [
            "https://owasp.org/www-community/vulnerabilities/Cleartext_Transmission_of_Sensitive_Information",
            "https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml",
        ]
    ),
    "143": (
        "IMAP sin cifrar", "ALTA",
        "Usar IMAPS (puerto 993) con TLS. El tráfico IMAP incluye credenciales en texto plano.",
        [
            "https://owasp.org/www-community/vulnerabilities/Cleartext_Transmission_of_Sensitive_Information",
            "https://datatracker.ietf.org/doc/html/rfc9051",
        ]
    ),
    "445": (
        "SMB expuesto", "ALTA",
        "SMB puede ser vulnerable a EternalBlue/WannaCry. Actualizar sistema y bloquear puerto en firewall si no es necesario.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2017-0144",
            "https://www.cisa.gov/news-events/alerts/2017/05/12/indicators-associated-wannacry-ransomware",
            "https://learn.microsoft.com/es-es/windows-server/storage/file-server/troubleshoot/detect-enable-and-disable-smbv1-v2-v3",
        ]
    ),
    "3306": (
        "MySQL expuesto", "ALTA",
        "Base de datos expuesta a la red. Restringir acceso con firewall a IPs específicas. Revisar usuarios con acceso remoto.",
        [
            "https://dev.mysql.com/doc/refman/8.0/en/security-guidelines.html",
            "https://owasp.org/www-project-top-ten/",
            "https://www.cisecurity.org/benchmark/mysql",
        ]
    ),
    "3389": (
        "RDP expuesto", "ALTA",
        "Escritorio remoto expuesto públicamente. Usar VPN, restringir IPs y habilitar Network Level Authentication (NLA).",
        [
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=rdp",
            "https://www.cisa.gov/news-events/alerts/2020/08/18/remote-desktop-protocol-rdp-vulnerabilities",
            "https://learn.microsoft.com/es-es/windows-server/remote/remote-desktop-services/clients/remote-desktop-allow-access",
        ]
    ),
    "5432": (
        "PostgreSQL expuesto", "ALTA",
        "Base de datos expuesta a la red. Configurar pg_hba.conf para restringir acceso por IP.",
        [
            "https://www.postgresql.org/docs/current/auth-pg-hba-conf.html",
            "https://www.postgresql.org/docs/current/auth-methods.html",
            "https://www.cisecurity.org/benchmark/postgresql",
        ]
    ),
    "5900": (
        "VNC sin cifrar", "CRÍTICA",
        "VNC transmite video y credenciales sin cifrado. Usar VNC sobre SSH tunnel o migrar a soluciones seguras como RustDesk.",
        [
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=vnc",
            "https://www.hackingarticles.in/vnc-penetration-testing/",
            "https://www.ssh.com/academy/ssh/tunneling-example",
        ]
    ),
    "5901": (
        "VNC sin cifrar", "CRÍTICA",
        "Ver recomendaciones del puerto 5900. Mismo riesgo, display :1.",
        [
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=vnc",
            "https://www.ssh.com/academy/ssh/tunneling-example",
        ]
    ),
    "6379": (
        "Redis expuesto", "CRÍTICA",
        "Redis no tiene autenticación por defecto y permite ejecución remota de comandos. Agregar contraseña fuerte y restringir con firewall.",
        [
            "https://redis.io/docs/manual/security/",
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=redis",
            "https://www.shodan.io/search?query=product%3Aredis",
        ]
    ),
    "27017": (
        "MongoDB expuesto", "CRÍTICA",
        "MongoDB puede estar sin autenticación habilitada. Configurar autenticación y restringir acceso a red local.",
        [
            "https://www.mongodb.com/docs/manual/security/",
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=mongodb",
            "https://owasp.org/www-project-top-ten/",
        ]
    ),
    "1723": (
        "PPTP VPN", "MEDIA",
        "PPTP usa MS-CHAPv2, protocolo roto criptográficamente. Migrar a WireGuard, OpenVPN o IKEv2/IPSec.",
        [
            "https://www.cloudflare.com/es-es/learning/access-management/what-is-pptp/",
            "https://www.cvedetails.com/vulnerability-list/vendor_id-26/product_id-504/Microsoft-Pptp.html",
            "https://www.wireguard.com/",
        ]
    ),
}

# Formato: "script_id": (título, severidad, recomendación, [referencias])
RISKY_SCRIPTS = {
    "ftp-anon": (
        "FTP anónimo habilitado", "ALTA",
        "Deshabilitar acceso anónimo en la configuración del servidor FTP. Revisar archivos accesibles públicamente.",
        [
            "https://owasp.org/www-community/vulnerabilities/Improper_Authentication",
            "https://www.rapid7.com/db/vulnerabilities/ftp-anonymous-login-found/",
        ]
    ),
    "http-auth-finder": (
        "Autenticación HTTP débil", "MEDIA",
        "Verificar que se use HTTPS con TLS 1.2+ y autenticación fuerte (no Basic en claro).",
        [
            "https://owasp.org/www-project-top-ten/",
            "https://developer.mozilla.org/es/docs/Web/HTTP/Authentication",
        ]
    ),
    "smb-vuln-ms17-010": (
        "Vulnerable a EternalBlue (MS17-010)", "CRÍTICA",
        "Aplicar parche MS17-010 inmediatamente. Esta vulnerabilidad fue usada por WannaCry y NotPetya.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2017-0144",
            "https://learn.microsoft.com/es-es/security-updates/securitybulletins/2017/ms17-010",
            "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        ]
    ),
    "smb-vuln-cve2009-3103": (
        "Vulnerable a CVE-2009-3103", "CRÍTICA",
        "Vulnerabilidad en SMBv2 de Windows Vista/2008. Actualizar sistema operativo urgentemente.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2009-3103",
            "https://learn.microsoft.com/es-es/security-updates/securitybulletins/2009/ms09-050",
        ]
    ),
    "rdp-vuln-ms12-020": (
        "RDP vulnerable a MS12-020", "CRÍTICA",
        "Vulnerabilidad de DoS/RCE en RDP. Aplicar parche Microsoft MS12-020 y deshabilitar RDP si no es necesario.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2012-0002",
            "https://learn.microsoft.com/es-es/security-updates/securitybulletins/2012/ms12-020",
        ]
    ),
    "ssl-poodle": (
        "Vulnerable a POODLE (SSLv3)", "ALTA",
        "Deshabilitar SSLv3 en la configuración del servidor. Usar TLS 1.2 o superior.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2014-3566",
            "https://www.openssl.org/~bodo/ssl-poodle.pdf",
            "https://www.cloudflare.com/es-es/learning/ssl/what-is-a-poodle-attack/",
        ]
    ),
    "ssl-heartbleed": (
        "Vulnerable a Heartbleed", "CRÍTICA",
        "Actualizar OpenSSL a versión 1.0.1g o superior inmediatamente. Revocar y reemitir certificados.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2014-0160",
            "https://heartbleed.com/",
            "https://www.openssl.org/news/secadv/20140407.txt",
        ]
    ),
    "http-shellshock": (
        "Vulnerable a Shellshock", "CRÍTICA",
        "Actualizar bash a una versión parcheada. CVE-2014-6271 permite ejecución remota de comandos.",
        [
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2014-6271",
            "https://www.cloudflare.com/es-es/learning/security/shellshock-bash-bug/",
            "https://www.rapid7.com/db/vulnerabilities/CVE-2014-6271/",
        ]
    ),
    "mysql-empty-password": (
        "MySQL sin contraseña", "CRÍTICA",
        "Establecer contraseña para todas las cuentas MySQL. Ejecutar mysql_secure_installation.",
        [
            "https://dev.mysql.com/doc/refman/8.0/en/mysql-secure-installation.html",
            "https://owasp.org/www-community/vulnerabilities/Improper_Authentication",
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=mysql+empty+password",
        ]
    ),
    "mongodb-info": (
        "MongoDB sin autenticación", "CRÍTICA",
        "Habilitar autenticación en MongoDB con --auth. Crear usuarios con roles mínimos necesarios.",
        [
            "https://www.mongodb.com/docs/manual/tutorial/enable-authentication/",
            "https://owasp.org/www-community/vulnerabilities/Improper_Authentication",
            "https://www.shodan.io/search?query=product%3Amongodb",
        ]
    ),
}

def analyze_host(ip, port_data, my_ip):
    findings = []

    for p in port_data["ports"]:
        port    = p["port"]
        service = p["name"]
        product = p["product"]
        version = p["version"]

        # Servicios inseguros conocidos
        if port in INSECURE_SERVICES:
            name, severity, rec, refs = INSECURE_SERVICES[port]
            findings.append({"severity": severity, "title": name,
                             "port": port, "rec": rec, "refs": refs})

        # SSH en puerto 22 — verificar versión
        if port == "22" and version:
            match = re.search(r'OpenSSH[_ ](\d+\.\d+)', version)
            if match:
                ver = float(match.group(1))
                if ver < 7.4:
                    findings.append({
                        "severity": "ALTA",
                        "title": f"OpenSSH desactualizado (v{ver})",
                        "port": port,
                        "rec": "Actualizar OpenSSH a versión 8.0 o superior.",
                        "refs": [
                            "https://www.openssh.com/security.html",
                            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=openssh",
                        ]
                    })

        # HTTP sin HTTPS
        if port == "80" and service in ("http", ""):
            findings.append({
                "severity": "MEDIA",
                "title": "HTTP sin cifrado (puerto 80 abierto)",
                "port": port,
                "rec": "Redirigir tráfico HTTP a HTTPS. Implementar certificado TLS.",
                "refs": [
                    "https://owasp.org/www-community/vulnerabilities/Cleartext_Transmission_of_Sensitive_Information",
                    "https://letsencrypt.org/es/getting-started/",
                    "https://developer.mozilla.org/es/docs/Web/HTTP/Headers/Strict-Transport-Security",
                ]
            })

        # Scripts NSE con vulnerabilidades
        for script in p.get("scripts", []):
            sid = script["id"]
            out = script["output"]
            if sid in RISKY_SCRIPTS:
                name, severity, rec, refs = RISKY_SCRIPTS[sid]
                # Solo reportar si el script confirma la vulnerabilidad
                if "VULNERABLE" in out.upper() or "anonymous" in out.lower() or sid == "mongodb-info":
                    findings.append({"severity": severity, "title": name,
                                     "port": port, "rec": rec, "refs": refs})

    # Verificar si es el gateway (router)
    try:
        gw = netifaces.gateways().get("default", {}).get(netifaces.AF_INET, [None])[0]
    except Exception:
        gw = None

    return findings, (ip == gw)

# ── Reporte por host ──────────────────────────────────────────
def print_host_report(host, port_data, findings, is_gateway):
    ip       = host["ip"]
    mac      = host.get("mac", "N/A")
    vendor   = host.get("vendor", "Desconocido")
    hostname = host.get("hostname", "")
    os_info  = port_data.get("os", "No detectado")

    tag = f" {YELLOW}[GATEWAY/ROUTER]{R}" if is_gateway else ""
    print(f"\n  {'─'*60}")
    print(f"  {BOLD}{WHITE}🖥️  {ip}{R}{tag}")
    if hostname:
        print(f"  {DIM}Hostname : {hostname}{R}")
    if mac and mac != "N/A":
        print(f"  {DIM}MAC      : {mac}  ({vendor}){R}")
    print(f"  {DIM}OS       : {os_info}{R}")

    # Puertos abiertos
    ports = port_data.get("ports", [])
    if ports:
        print(f"\n  {CYAN}Puertos abiertos:{R}")
        for p in ports:
            svc = f"{p['product']} {p['version']}".strip() or p['name']
            print(f"    {DIM}{p['port']}/{p['proto']:<6}{R} {WHITE}{p['name']:<12}{R} {DIM}{svc}{R}")
    else:
        dim("  Sin puertos abiertos detectados en los rangos escaneados.")

    # Hallazgos de seguridad
    if findings:
        print(f"\n  {CYAN}Hallazgos de seguridad:{R}")
        order = ["CRÍTICA", "ALTA", "MEDIA", "BAJA", "INFO"]
        for level in order:
            for f in [x for x in findings if x["severity"] == level]:
                c = SEV_COLOR[level]
                print(f"\n    {BOLD}{c}▸ [{level}]{R} {BOLD}{f['title']}{R}  {DIM}(puerto {f['port']}){R}")
                print(f"    {DIM}Recomendación: {f['rec']}{R}")
                for ref in f.get("refs", []):
                    print(f"    {BLUE}↳ {ref}{R}")
    else:
        ok("Sin vulnerabilidades detectadas en este host.")

# ── Resumen ejecutivo ─────────────────────────────────────────
def print_summary(all_findings, hosts_count, start_time):
    elapsed = (datetime.datetime.now() - start_time).seconds
    counts  = {"CRÍTICA": 0, "ALTA": 0, "MEDIA": 0, "BAJA": 0}
    for findings in all_findings:
        for f in findings:
            s = f["severity"]
            if s in counts:
                counts[s] += 1

    total = sum(counts.values())

    section("📊", "Resumen Ejecutivo")
    info(f"Hosts analizados : {BOLD}{hosts_count}{R}")
    info(f"Tiempo total     : {BOLD}{elapsed}s{R}")
    info(f"Hallazgos totales: {BOLD}{total}{R}")
    print()

    if counts["CRÍTICA"] > 0:
        bad(f"Vulnerabilidades CRÍTICAS : {counts['CRÍTICA']}")
    else:
        ok(f"Vulnerabilidades CRÍTICAS : {counts['CRÍTICA']}")

    if counts["ALTA"] > 0:
        warn(f"Vulnerabilidades ALTAS    : {counts['ALTA']}")
    else:
        ok(f"Vulnerabilidades ALTAS    : {counts['ALTA']}")

    print(f"  {YELLOW}⚠{R}  Vulnerabilidades MEDIAS   : {counts['MEDIA']}")
    print(f"  {CYAN}ℹ{R}  Vulnerabilidades BAJAS    : {counts['BAJA']}")

    if total == 0:
        print(f"\n  {GREEN}{BOLD}✔ Red en buen estado. Sin vulnerabilidades detectadas.{R}")
    elif counts["CRÍTICA"] > 0:
        print(f"\n  {RED}{BOLD}✘ Atención inmediata requerida. Existen vulnerabilidades CRÍTICAS.{R}")
    elif counts["ALTA"] > 0:
        print(f"\n  {YELLOW}{BOLD}⚠ Se recomienda atención urgente a las vulnerabilidades ALTAS.{R}")
    print()

# ── Main ──────────────────────────────────────────────────────
def main():
    if os.geteuid() != 0:
        print(f"\n  {RED}Este script requiere permisos de root.{R}")
        print(f"  Usa: {BOLD}sudo netscan{R}\n")
        sys.exit(1)

    subnet = sys.argv[1] if len(sys.argv) > 1 else None

    print()
    print(f"  {BOLD}{CYAN}╔══════════════════════════════════════════════════╗{R}")
    print(f"  {BOLD}{CYAN}║        🔍 netscan — Auditoría de Red             ║{R}")
    print(f"  {BOLD}{CYAN}╚══════════════════════════════════════════════════╝{R}")
    print(f"  {DIM}{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{R}")

    start_time = datetime.datetime.now()

    # Detectar subred
    if not subnet:
        subnet, my_ip, iface = detect_subnet()
        if not subnet:
            bad("No se pudo detectar la subred automáticamente.")
            bad("Especifica la subred manualmente: sudo netscan 192.168.1.0/24")
            sys.exit(1)
        info(f"Interfaz detectada: {BOLD}{iface}{R}  IP: {BOLD}{my_ip}{R}")
    else:
        my_ip = None
        try:
            addrs = netifaces.ifaddresses(netifaces.interfaces()[0])
            my_ip = addrs.get(netifaces.AF_INET, [{}])[0].get("addr", "")
        except Exception:
            pass

    # ── Fase 1: Descubrimiento ────────────────────────────────
    section("📡", "Fase 1: Descubrimiento de Hosts")
    xml_discovery = discover_hosts(subnet)
    hosts = parse_hosts_xml(xml_discovery)

    if not hosts:
        bad("No se encontraron hosts activos en la subred.")
        sys.exit(0)

    info(f"Hosts activos encontrados: {BOLD}{GREEN}{len(hosts)}{R}")
    for h in hosts:
        tag = f"  {DIM}({h['hostname']}){R}" if h['hostname'] else ""
        mac_str = f"  {DIM}MAC: {h['mac']} ({h['vendor']}){R}" if h['mac'] else ""
        print(f"    {GREEN}●{R} {BOLD}{h['ip']:<18}{R}{tag}{mac_str}")

    # ── Fase 2: Escaneo de puertos ────────────────────────────
    section("🔬", "Fase 2: Análisis de Servicios y Vulnerabilidades")

    all_findings = []
    for host in hosts:
        ip       = host["ip"]
        xml_scan = scan_host(ip)
        port_data = parse_ports_xml(xml_scan)
        findings, is_gw = analyze_host(ip, port_data, my_ip)
        all_findings.append(findings)
        print_host_report(host, port_data, findings, is_gw)

    # ── Fase 3: Resumen ───────────────────────────────────────
    section("📊", "Fase 3: Resumen")
    print_summary(all_findings, len(hosts), start_time)


if __name__ == "__main__":
    main()
