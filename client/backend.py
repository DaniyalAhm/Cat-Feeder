#!/usr/bin/env python3
"""Feeder backend API (stdlib only).

JSON API for the static frontend (served separately, default :6606).
Runs the feeding scheduler in-process.

Endpoints (all under /api):
  GET  /api/status    {config..., running, next, last, esp}
  POST /api/config    {ip, port, mode, times, interval, duration} -> saved
  POST /api/start     start scheduler
  POST /api/stop      stop scheduler
  POST /api/feed-now  feed once in background
  GET  /api/events    recent event log (newest last)

Config is persisted to client/schedule.json.

Usage:
  python3 client/backend.py                       # :6607
  python3 client/backend.py --port 6607 --times 07:00,18:00
"""

import argparse
import datetime
import json
import os
import sys
import threading
import time
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feed_service import do_feed, next_fire, parse_times  # noqa: E402

CONFIG_FILE = os.path.join(HERE, "schedule.json")

STATE = {
    "ip": "10.0.0.128",
    "port": 80,
    "mode": "schedule",          # "schedule" | "interval"
    "times": ["07:00", "18:00"],
    "interval": 3.0,
    "duration": 6.0,
    "running": False,
    "next": "-",
    "last": "-",
    "version": 0,                # bumped on config/start/stop
}
EVENTS: deque = deque(maxlen=50)
LOCK = threading.Lock()
STOP_EVENT = threading.Event()


def log(msg: str) -> None:
    line = f"{datetime.datetime.now().strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOCK:
        EVENTS.append(line)


def esp_status() -> dict | None:
    with LOCK:
        ip, port = STATE["ip"], STATE["port"]
    try:
        with urllib.request.urlopen(
                f"http://{ip}:{port}/status", timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def run_feed(reason: str) -> None:
    with LOCK:
        base = f"http://{STATE['ip']}:{STATE['port']}"
        duration = STATE["duration"]
    ok = do_feed(base, duration, 5.0)
    stamp = datetime.datetime.now().strftime("%H:%M")
    with LOCK:
        STATE["last"] = f"{stamp} {reason}: {'ok' if ok else 'FAILED'}"
    log(f"feed ({reason}): {'ok' if ok else 'FAILED'}")


def scheduler_loop() -> None:
    interval_next: float | None = None
    schedule_next: datetime.datetime | None = None
    seen_version = -1
    seen_mode: str | None = None
    while not STOP_EVENT.is_set():
        with LOCK:
            running, mode = STATE["running"], STATE["mode"]
            version = STATE["version"]
            times = list(STATE["times"])
            interval = STATE["interval"]
        if not running:
            interval_next = None
            schedule_next = None
            seen_version = version
            seen_mode = mode
            STOP_EVENT.wait(1)
            continue
        # Config changed or mode switched -> recompute targets.
        if version != seen_version or mode != seen_mode:
            interval_next = None
            schedule_next = None
            seen_version = version
            seen_mode = mode
        now = datetime.datetime.now()
        if mode == "interval":
            if interval_next is None:
                interval_next = time.monotonic() + interval
            with LOCK:
                STATE["next"] = time.strftime(
                    "%H:%M:%S", time.localtime(time.time() + max(0, interval_next - time.monotonic())))
            if time.monotonic() >= interval_next:
                threading.Thread(target=run_feed, args=("cycle",), daemon=True).start()
                interval_next += interval
            STOP_EVENT.wait(1)
        else:
            if not times:
                with LOCK:
                    STATE["next"] = "-"
                STOP_EVENT.wait(5)
                continue
            try:
                parsed = [datetime.time(int(t[:2]), int(t[3:])) for t in times]
            except (ValueError, IndexError):
                with LOCK:
                    STATE["next"] = "-"
                STOP_EVENT.wait(5)
                continue
            if schedule_next is None:
                schedule_next = next_fire(parsed, now)
            with LOCK:
                STATE["next"] = schedule_next.strftime("%Y-%m-%d %H:%M")
            if now >= schedule_next:
                threading.Thread(target=run_feed, args=("schedule",), daemon=True).start()
                # Move past this slot so we don't refire; compute from now.
                schedule_next = next_fire(parsed, now + datetime.timedelta(seconds=61))
                with LOCK:
                    STATE["next"] = schedule_next.strftime("%Y-%m-%d %H:%M")
            STOP_EVENT.wait(5)


class Handler(BaseHTTPRequestHandler):
    server_version = "FeederBackend/1.0"

    def log_message(self, *a):
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, code: int, obj) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode() or "{}")
        except ValueError:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/status":
            with LOCK:
                snap = {k: v for k, v in STATE.items() if k != "version"}
            snap["esp"] = esp_status()
            self._send_json(200, snap)
            return
        if self.path == "/api/events":
            with LOCK:
                self._send_json(200, {"events": list(EVENTS)})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/api/config":
            body = self._read_json()
            try:
                ip = str(body.get("ip", STATE["ip"])).strip() or STATE["ip"]
                port = int(body.get("port", STATE["port"]))
                mode = str(body.get("mode", STATE["mode"]))
                duration = float(body.get("duration", STATE["duration"]))
                if mode not in ("schedule", "interval"):
                    raise ValueError("mode must be schedule|interval")
                if duration <= 0:
                    raise ValueError("duration must be > 0")
                if mode == "schedule":
                    times = parse_times(str(body.get("times", ",".join(STATE["times"]))))
                    times = [t.strftime("%H:%M") for t in times]
                    interval = STATE["interval"]
                else:
                    interval = float(body.get("interval", STATE["interval"]))
                    if interval <= 0:
                        raise ValueError("interval must be > 0")
                    if duration >= interval:
                        raise ValueError("duration must be shorter than interval")
                    times = STATE["times"]
            except (ValueError, AttributeError, TypeError, IndexError) as exc:
                self._send_json(400, {"ok": False, "error": str(exc) or "bad config"})
                return
            with LOCK:
                STATE.update({"ip": ip, "port": port, "mode": mode,
                              "times": times, "interval": interval,
                              "duration": duration})
                STATE["version"] += 1
            try:
                with open(CONFIG_FILE, "w") as fh:
                    json.dump({"ip": ip, "port": port, "mode": mode,
                               "times": times, "interval": interval,
                               "duration": duration}, fh, indent=2)
            except OSError as exc:
                self._send_json(500, {"ok": False, "error": f"save failed: {exc}"})
                return
            log(f"config saved: {mode} {times if mode == 'schedule' else interval}s "
                f"-> {ip}:{port} {duration}s")
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/start":
            with LOCK:
                STATE["running"] = True
                STATE["version"] += 1
            log("scheduler started")
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/stop":
            with LOCK:
                STATE["running"] = False
                STATE["next"] = "-"
                STATE["version"] += 1
            log("scheduler stopped")
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/feed-now":
            threading.Thread(target=run_feed, args=("manual",), daemon=True).start()
            self._send_json(200, {"ok": True})
            return

        self._send_json(404, {"ok": False, "error": "not found"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=6607)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--times", default="")
    parser.add_argument("--ip", default=os.environ.get("FEEDER_IP", "10.0.0.128"))
    parser.add_argument("--duration", type=float, default=6.0)
    args = parser.parse_args()

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as fh:
                cfg = json.load(fh)
            for key in ("ip", "port", "mode", "times", "interval", "duration"):
                if key in cfg:
                    STATE[key] = cfg[key]
        except (OSError, ValueError):
            pass
    if args.times:
        try:
            STATE["mode"] = "schedule"
            STATE["times"] = [t.strftime("%H:%M") for t in parse_times(args.times)]
        except ValueError as exc:
            parser.error(str(exc))
    if "--ip" in sys.argv or "FEEDER_IP" in os.environ:
        STATE["ip"] = args.ip
    if "--duration" in sys.argv:
        STATE["duration"] = args.duration

    threading.Thread(target=scheduler_loop, daemon=True).start()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Feeder backend at http://{args.host}:{args.port} "
          f"(ESP32 {STATE['ip']})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    STOP_EVENT.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
