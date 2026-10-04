#!/usr/bin/env python3
"""Feed the cat via HTTP latched motor control.

Sequence:
  POST /motor/run -> sleep --duration -> POST /motor/stop

Stop is sent in a finally block so the motor never latches on if the
script is interrupted mid-run.

Usage:
  python3 client/feed.py --ip 10.0.0.42
  python3 client/feed.py --ip 10.0.0.42 --duration 2.5
  FEEDER_IP=10.0.0.42 python3 client/feed.py

  flash.py (BLE pulse feed) is left untouched; this is the HTTP path.
"""

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ip",
        default=os.environ.get("FEEDER_IP", "10.0.0.128"),
        help="ESP32 STA IP (default 10.0.0.128, or FEEDER_IP env)",
    )
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument(
        "--duration",
        type=float,
        default=6.0,
        help="seconds between run and stop (default 6.0)",
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    if not args.ip:
        print("ERROR: --ip or FEEDER_IP env is required (STA IP).", file=sys.stderr)
        return 1
    if args.duration <= 0:
        print("ERROR: --duration must be > 0.", file=sys.stderr)
        return 1

    base = f"http://{args.ip}:{args.port}"

    print(f"POST {base}/motor/run ...")
    code, body = post(base, "/motor/run", args.timeout)
    print(f"run -> {code} {body}")
    if code == 409:
        print("Feed rejected (busy).", file=sys.stderr)
        return 2
    if code != 200 or '"ok":true' not in body.replace(" ", ""):
        print("Feed run failed.", file=sys.stderr)
        return 1

    stop_ok = False
    try:
        print(f"Sleeping {args.duration:.1f}s ...")
        time.sleep(args.duration)
    finally:
        print(f"POST {base}/motor/stop ...")
        try:
            scode, sbody = post(base, "/motor/stop", args.timeout)
        except Exception as exc:  # network down mid-run: report, don't mask
            print(f"ERROR: stop request failed: {exc}", file=sys.stderr)
        else:
            print(f"stop -> {scode} {sbody}")
            stop_ok = scode == 200 and '"ok":true' in sbody.replace(" ", "")
            if not stop_ok:
                print("WARNING: stop not confirmed.", file=sys.stderr)

    if not stop_ok:
        return 1

    print("Feed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
