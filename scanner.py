import ipaddress
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


def ping(ip: str, timeout_ms: int = 500) -> bool:
    """Envia um ping ICMP e retorna True se o host respondeu."""
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def scan_network(cidr: str, max_workers: int = 100):
    """Varre um bloco CIDR (ex: 10.0.0.0/24) e retorna a lista de IPs ativos."""
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = [str(ip) for ip in network.hosts()]
    alive = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping, ip): ip for ip in hosts}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                if future.result():
                    alive.append(ip)
            except Exception:
                pass

    return sorted(alive, key=lambda x: tuple(int(p) for p in x.split(".")))


def ping_hosts(ip_list, max_workers: int = 50):
    """Pinga uma lista específica de IPs em paralelo e retorna {ip: True/False}."""
    results = {}
    if not ip_list:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping, ip): ip for ip in ip_list}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                results[ip] = future.result()
            except Exception:
                results[ip] = False

    return results
