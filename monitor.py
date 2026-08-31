import os
import threading
import time

import database
from scanner import ping_hosts

# Intervalo entre checagens de ping, em segundos. Pode ser ajustado via
# variável de ambiente PING_INTERVAL_SECONDS sem precisar mexer no código.
PING_INTERVAL_SECONDS = int(os.environ.get("PING_INTERVAL_SECONDS", "15"))

_monitor_state = {
    "running": False,
    "last_check": None,
    "last_check_count": 0,
}


def _check_all_machines():
    machines = database.get_all_machines()
    ips = [m["ip"] for m in machines]
    if not ips:
        return

    results = ping_hosts(ips)

    for m in machines:
        is_alive = results.get(m["ip"], False)
        new_status = "online" if is_alive else "offline"
        if m.get("status") != new_status:
            database.update_status(m["ip"], new_status)

    _monitor_state["last_check"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _monitor_state["last_check_count"] = len(ips)


def _monitor_loop(interval):
    _monitor_state["running"] = True
    while True:
        try:
            _check_all_machines()
        except Exception as e:
            print(f"[monitor] erro ao checar máquinas: {e}")
        time.sleep(interval)


def start_monitor(interval: int = PING_INTERVAL_SECONDS):
    """Inicia a thread de monitoramento contínuo (chamar uma única vez, no
    startup da aplicação)."""
    thread = threading.Thread(target=_monitor_loop, args=(interval,), daemon=True)
    thread.start()
    return thread


def get_monitor_state():
    return dict(_monitor_state)
