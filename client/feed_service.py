#!/usr/bin/env python3
"""Scheduled feeding service (HTTP latched motor control).

Pushes a feed (POST /motor/run, wait --duration, POST /motor/stop)
at user-set times, every day, local time.

Usage:
  python3 client/feed_service.py --times 07:00,18:00
  python3 client/feed_service.py --times 07:00,12:30,18:00 --duration 6.0
  FEEDER_IP=10.0.0.128 python3 client/feed_service.py --times 07:00,18:00
  python3 client/feed_service.py --config client/schedule.json
  python3 client/feed_service.py --times 07:00,18:00 --once      # test now
  python3 client/feed_service.py --times 07:00,18:00 --dry-run   # show next fire
  python3 client/feed_service.py --interval 3 --duration 1      # repeat: one 3s cycle

Config file (JSON) example:
  {"ip": "10.0.0.128", "port": 80, "duration": 6.0,
   "times": ["07:00", "18:00"]}
CLI flags override config file values.

Runs in the foreground; use systemd/tmux/nohup to keep it alive.
Example systemd unit (adjust paths):
  [Unit]
  Description=Cat feeder schedule
  After=network-online.target
  [Service]
  ExecStart=/usr/bin/python3 /home/todds/Documents/Projects/esp32/cat-feeding-inator/client/feed_service.py --times 07:00,18:00
  Restart=always
  [Install]
  WantedBy=multi-user.target
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request


def post(base: str, path: str, timeout: float) -> tuple[int, str]:
    url = base + path
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return exc.code, body


def parse_times(raw: str) -> list[datetime.time]:
    out: list[datetime.time] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            hh, mm = part.split(":")
            t = datetime.time(int(hh), int(mm))
        except ValueError:
            raise ValueError(f"Bad time {part!r}: use HH:MM 24h, e.g. 07:00,18:30")
        if not (0 <= t.hour <= 23 and 0 <= t.minute <= 59):
            raise ValueError(f"Bad time {part!r}: hour 0-23, minute 0-59")
        out.append(t)
    if not out:
        raise ValueError("No feed times given. Use HH:MM[,HH:MM...]")
    return sorted(out)


def next_fire(times: list[datetime.time], now: datetime.datetime) -> datetime.datetime:
    today = now.date()
    for t in times:
        cand = datetime.datetime.combine(today, t)
        if cand > now:
            return cand
    return datetime.datetime.combine(today + datetime.timedelta(days=1), times[0])


def do_feed(base: str, duration: float, timeout: float) -> bool:
    print(f"POST {base}/motor/run ...", flush=True)
    try:
        code, body = post(base, "/motor/run", timeout)
    except Exception as exc:
        print(f"ERROR: run request failed: {exc}", flush=True)
        return False
    print(f"run -> {code} {body}", flush=True)
    if code == 409:
        print("Feed skipped (busy).", flush=True)
        return False
    if code != 200 or '"ok":true' not in body.replace(" ", ""):
        print("Feed run failed.", flush=True)
        return False

    stop_ok = False
    try:
        print(f"Motor on, waiting {duration:.1f}s ...", flush=True)
        time.sleep(duration)
    finally:
        print(f"POST {base}/motor/stop ...", flush=True)
        try:
            scode, sbody = post(base, "/motor/stop", timeout)
        except Exception as exc:
            print(f"ERROR: stop request failed: {exc}", flush=True)
        else:
            print(f"stop -> {scode} {sbody}", flush=True)
            stop_ok = scode == 200 and '"ok":true' in sbody.replace(" ", "")
            if not stop_ok:
                print("WARNING: stop not confirmed.", flush=True)
    return stop_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--times", default="",
                        help='comma-separated HH:MM list, e.g. "07:00,18:00"')
    parser.add_argument("--config", default="",
                        help="JSON config file with times/ip/port/duration")
    parser.add_argument("--ip", default=os.environ.get("FEEDER_IP", "10.0.0.128"),
                        help="ESP32 STA IP (default 10.0.0.128, or FEEDER_IP env)")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--duration", type=float, default=6.0,
                        help="motor-on seconds per feed (default 6.0)")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--interval", type=float, default=0.0,
                        help="repeat every N seconds (one cycle = N seconds); "
                             "overrides --times. E.g. --interval 3 --duration 1")
    parser.add_argument("--once", action="store_true", help="feed once now, then exit")
    parser.add_argument("--dry-run", action="store_true", help="print next fire time, exit")
    args = parser.parse_args()

    cfg: dict = {}
    if args.config:
        with open(args.config) as fh:
            cfg = json.load(fh)

    times_raw = args.times or ",".join(cfg.get("times", []))
    ip = args.ip if "--ip" in sys.argv or "FEEDER_IP" in os.environ else cfg.get("ip", args.ip)
    port = args.port if "--port" in sys.argv else cfg.get("port", args.port)
    duration = args.duration if "--duration" in sys.argv else cfg.get("duration", args.duration)
    interval = args.interval if "--interval" in sys.argv else cfg.get("interval", args.interval)

    if duration <= 0:
        raise SystemExit("--duration must be > 0")

    base = f"http://{ip}:{port}"

    if args.once:
        ok = do_feed(base, duration, args.timeout)
        return 0 if ok else 1

    if interval:
        # Repeat mode: one feed cycle every `interval` seconds.
        if interval <= 0:
            raise SystemExit("--interval must be > 0")
        if duration >= interval:
            raise SystemExit(
                f"--duration ({duration}s) must be shorter than "
                f"--interval ({interval}s): one cycle = {interval}s total.")
        print(f"Feeder repeat: every {interval:.1f}s (one cycle) "
              f"-> {base}, motor on {duration:.1f}s per cycle")
        if args.dry_run:
            return 0
        nxt = time.monotonic()
        while True:
            print(f"--- feed cycle ---", flush=True)
            try:
                do_feed(base, duration, args.timeout)
            except Exception as exc:
                print(f"ERROR during feed: {exc}", flush=True)
            nxt += interval
            delay = nxt - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                nxt = time.monotonic()  # overrun: restart cadence now
        return 0

    try:
        times = parse_times(times_raw)
    except ValueError as exc:
        raise SystemExit(str(exc))
    label = ",".join(t.strftime("%H:%M") for t in times)
    print(f"Feeder schedule: daily at {label} (local) -> {base}, {duration:.1f}s per feed")

    nxt = next_fire(times, datetime.datetime.now())
    print(f"Next feed at {nxt.strftime('%Y-%m-%d %H:%M')}")
    if args.dry_run:
        return 0

    while True:
        now = datetime.datetime.now()
        if now >= nxt:
            print(f"--- feed due ({nxt.strftime('%H:%M')}) ---", flush=True)
            try:
                do_feed(base, duration, args.timeout)
            except Exception as exc:
                print(f"ERROR during feed: {exc}", flush=True)
            nxt = next_fire(times, datetime.datetime.now())
            print(f"Next feed at {nxt.strftime('%Y-%m-%d %H:%M')}", flush=True)
        time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
