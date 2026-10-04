#!/usr/bin/env python3
"""Simple web frontend to configure feeding (stdlib only).

Serves a form to set the ESP32 STA IP, daily feed times and motor-on
duration, then runs the same run -> wait -> stop schedule in-process.

Usage:
  python3 client/feed_ui.py
  python3 client/feed_ui.py --ui-port 8080 --times 07:00,18:00
  FEEDER_IP=10.0.0.128 python3 client/feed_ui.py

Then open http://localhost:8080 in a browser.

Pages/API (all on the UI port):
  GET  /            form + status (IP, times, duration, running, next feed)
  POST /save        save config (also writes client/schedule.json)
  POST /start       start the scheduler
  POST /stop        stop the scheduler
  POST /feed-now    feed once immediately
  GET  /status      JSON status (for polling)
"""

import argparse
import datetime
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

STATE = {
    "ip": "10.0.0.128",
    "port": 80,
    "duration": 6.0,
    "times": ["07:00", "18:00"],
    "running": False,
    "next": "-",
    "last": "-",
}
LOCK = threading.Lock()
STOP_EVENT = threading.Event()
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule.json")


def esp_post(base: str, path: str, timeout: float = 5.0) -> tuple[int, str]:
    req = urllib.request.Request(base + path, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return exc.code, body


def do_feed(base: str, duration: float) -> str:
    try:
        code, body = esp_post(base, "/motor/run")
    except Exception as exc:
        return f"run failed: {exc}"
    if code == 409:
        return "skipped (busy)"
    if code != 200 or '"ok":true' not in body.replace(" ", ""):
        return f"run failed: {code} {body}"
    stop_ok = False
    stop_err = ""
    try:
        time.sleep(duration)
    finally:
        try:
            scode, sbody = esp_post(base, "/motor/stop")
        except Exception as exc:
            stop_err = f"running, but STOP FAILED: {exc}"
        else:
            stop_ok = scode == 200 and '"ok":true' in sbody.replace(" ", "")
            if not stop_ok:
                stop_err = f"run ok, STOP NOT CONFIRMED: {scode} {sbody}"
    return "ok" if stop_ok else stop_err


def parse_times(raw: str) -> list[str]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        hh, mm = part.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError(part)
        out.append(f"{int(hh):02d}:{int(mm):02d}")
    if not out:
        raise ValueError("empty")
    return sorted(out)


def next_fire(times: list[str], now: datetime.datetime) -> datetime.datetime:
    today = now.date()
    for t in times:
        cand = datetime.datetime.combine(
            today, datetime.time(int(t[:2]), int(t[3:])))
        if cand > now:
            return cand
    t0 = times[0]
    return datetime.datetime.combine(
        today + datetime.timedelta(days=1),
        datetime.time(int(t0[:2]), int(t0[3:])))


def scheduler_loop() -> None:
    while not STOP_EVENT.is_set():
        with LOCK:
            running, times = STATE["running"], list(STATE["times"])
            base = f"http://{STATE['ip']}:{STATE['port']}"
            duration = STATE["duration"]
        if running:
            nxt = next_fire(times, datetime.datetime.now())
            with LOCK:
                STATE["next"] = nxt.strftime("%Y-%m-%d %H:%M")
            if datetime.datetime.now() >= nxt:
                # nudge past this slot so we don't double-fire
                time.sleep(61)
                result = do_feed(base, duration)
                with LOCK:
                    STATE["last"] = (
                        f"{datetime.datetime.now().strftime('%H:%M')} {result}")
        STOP_EVENT.wait(5)


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cat-Feeding-Inator</title>
<style>body{font-family:sans-serif;max-width:560px;margin:2em auto;padding:0 1em}
.card{border:1px solid #ccc;border-radius:8px;padding:1em;margin-bottom:1em}
label{display:block;margin:.4em 0}input{padding:.3em;font-size:1em;width:100%;box-sizing:border-box}
.row{display:flex;gap:.5em;margin-top:.6em;flex-wrap:wrap}
button{padding:.5em 1em;font-size:1em;cursor:pointer}
#msg{white-space:pre-wrap;background:#f4f4f4;padding:.5em;border-radius:4px;min-height:1.2em}</style>
</head><body>
<h1>Cat-Feeding-Inator</h1>
<div class="card"><h3>Status</h3>
<div id="status">loading…</div></div>
<div class="card"><h3>Configure feed</h3>
<form method="POST" action="/save">
<label>ESP32 STA IP <input name="ip" value="__IP__"></label>
<label>Daily times (HH:MM, comma-separated) <input name="times" value="__TIMES__"></label>
<label>Motor-on seconds <input name="duration" type="number" step="0.5" min="1" value="__DURATION__"></label>
<div class="row"><button type="submit">Save</button></div>
</form></div>
<div class="card"><h3>Control</h3>
<div class="row">
<button onclick="act('/start')">Start schedule</button>
<button onclick="act('/stop')">Stop schedule</button>
<button onclick="act('/feed-now')">Feed now</button>
</div>
<div id="msg"></div></div>
<script>
async function refresh(){try{const r=await fetch('/status');const s=await r.json();
document.getElementById('status').innerHTML=
'Running: <b>'+s.running+'</b><br>Next feed: <b>'+s.next+'</b><br>Last: '+s.last+
'<br>Target: '+s.ip+':'+s.port+' @ '+s.duration+'s ['+s.times+']';}catch(e){}}
async function act(p){const m=document.getElementById('msg');m.textContent='…';
try{const r=await fetch(p,{method:'POST'});m.textContent=await r.text();refresh();}catch(e){m.textContent='error: '+e;}}
setInterval(refresh,5000);refresh();</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "FeedUI/1.0"

    def log_message(self, *a):
        pass

    def _send(self, code: int, body: str, ctype: str = "text/html") -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/status":
            with LOCK:
                snap = dict(STATE)
            self._send(200, json.dumps(snap), "application/json")
            return
        if self.path in ("/", "/index.html"):
            with LOCK:
                snap = dict(STATE)
            page = PAGE.replace("__IP__", snap["ip"]).replace(
                "__TIMES__", ",".join(snap["times"])).replace(
                "__DURATION__", str(snap["duration"]))
            self._send(200, page)
            return
        self._send(404, "not found", "text/plain")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode())
        get = lambda k, d="": form.get(k, [d])[0].strip()

        if self.path == "/save":
            try:
                times = parse_times(get("times"))
                ip = get("ip") or STATE["ip"]
                duration = float(get("duration") or STATE["duration"])
                if duration <= 0:
                    raise ValueError("duration")
            except (ValueError, IndexError):
                self._send(400, "Bad times (use HH:MM,HH:MM) or duration.")
                return
            with LOCK:
                STATE["ip"], STATE["times"], STATE["duration"] = ip, times, duration
            try:
                with open(CONFIG_FILE, "w") as fh:
                    json.dump({"ip": ip, "times": times,
                               "duration": duration}, fh, indent=2)
            except OSError:
                pass
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if self.path == "/start":
            with LOCK:
                STATE["running"] = True
            self._send(200, "scheduler started", "text/plain")
            return

        if self.path == "/stop":
            with LOCK:
                STATE["running"] = False
                STATE["next"] = "-"
            self._send(200, "scheduler stopped", "text/plain")
            return

        if self.path == "/feed-now":
            with LOCK:
                base = f"http://{STATE['ip']}:{STATE['port']}"
                duration = STATE["duration"]
            threading.Thread(target=lambda: do_feed(base, duration),
                             daemon=True).start()
            self._send(200, "feed triggered (runs in background)", "text/plain")
            return

        self._send(404, "not found", "text/plain")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-port", type=int, default=8080)
    parser.add_argument("--times", default="")
    parser.add_argument("--ip", default=os.environ.get("FEEDER_IP", "10.0.0.128"))
    parser.add_argument("--duration", type=float, default=6.0)
    args = parser.parse_args()

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as fh:
                cfg = json.load(fh)
            STATE.update({k: cfg[k] for k in ("ip", "times", "duration") if k in cfg})
        except (OSError, ValueError):
            pass
    if args.times:
        STATE["times"] = parse_times(args.times)
    if "--ip" in sys.argv or "FEEDER_IP" in os.environ:
        STATE["ip"] = args.ip
    if "--duration" in sys.argv:
        STATE["duration"] = args.duration

    threading.Thread(target=scheduler_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", args.ui_port), Handler)
    print(f"Feed UI at http://localhost:{args.ui_port} (ESP32 {STATE['ip']})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    STOP_EVENT.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
