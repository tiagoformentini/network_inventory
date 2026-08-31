import json
import os
import threading

from flask import Flask, render_template, jsonify, request, redirect, url_for

import database
import monitor
from scanner import scan_network
from wmi_collector import collect_machine_info

app = Flask(__name__)
app.secret_key = "troque-esta-chave-secreta"

database.init_db()

# Evita iniciar duas threads de monitor quando o Flask roda com debug=True
# (o reloader do Werkzeug sobe um processo "watcher" extra).
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    monitor.start_monitor()

scan_status = {
    "running": False,
    "total": 0,
    "done": 0,
    "current_ip": "",
    "errors": [],
}


def run_scan(cidr, username, password, domain):
    scan_status.update(
        {"running": True, "total": 0, "done": 0, "current_ip": "", "errors": []}
    )

    alive_ips = scan_network(cidr)
    scan_status["total"] = len(alive_ips)

    for ip in alive_ips:
        scan_status["current_ip"] = ip
        try:
            info = collect_machine_info(ip, username, password, domain)
            info["disks_json"] = json.dumps(info["disks_json"], ensure_ascii=False)
            info["network_json"] = json.dumps(info["network_json"], ensure_ascii=False)
            database.upsert_machine(info)
        except Exception as e:
            scan_status["errors"].append(f"{ip}: {e}")
        scan_status["done"] += 1

    # O status online/offline não é mais decidido aqui: o monitor de ping em
    # background (monitor.py) cuida disso continuamente para TODAS as
    # máquinas do banco, independente do range escaneado nesta varredura.
    scan_status["running"] = False


@app.route("/")
def dashboard():
    machines = database.get_all_machines()
    for m in machines:
        m["disks"] = json.loads(m["disks_json"]) if m["disks_json"] else []
        m["network"] = json.loads(m["network_json"]) if m["network_json"] else []
    return render_template("dashboard.html", machines=machines, scan_status=scan_status)


@app.route("/machine/<ip>")
def machine_detail(ip):
    m = database.get_machine(ip)
    if not m:
        return redirect(url_for("dashboard"))
    m["disks"] = json.loads(m["disks_json"]) if m["disks_json"] else []
    m["network"] = json.loads(m["network_json"]) if m["network_json"] else []
    return render_template("machine_detail.html", m=m)


@app.route("/scan", methods=["POST"])
def start_scan():
    if scan_status["running"]:
        return jsonify({"ok": False, "msg": "Já existe uma varredura em andamento."})

    cidr = request.form.get("cidr", "10.0.33.0/24")
    username = request.form.get("username")
    password = request.form.get("password")
    domain = request.form.get("domain") or None

    thread = threading.Thread(
        target=run_scan, args=(cidr, username, password, domain), daemon=True
    )
    thread.start()
    return jsonify({"ok": True})


@app.route("/scan/status")
def scan_status_view():
    return jsonify(scan_status)


@app.route("/api/machines")
def api_machines():
    return jsonify(database.get_all_machines())


@app.route("/api/monitor")
def api_monitor():
    return jsonify(monitor.get_monitor_state())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
