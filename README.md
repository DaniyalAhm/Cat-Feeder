# Cat-Feeding-Inator

ESP32-C3 feeder: H-bridge motor control over HTTP, BLE WiFi provisioning,
and Python clients for manual + scheduled feeding.

## Hardware

- Board: ESP32-C3 (WiFi + BLE), 4MB flash, 3.3V logic.
- Motor driver: 2-pin H-bridge (L298N / TB6612 / DRV8833 / MX1508).
- Wiring:
  - `GPIO0 -> driver IN1`, `GPIO1 -> driver IN2`
  - `ESP32 GND <-> driver GND` (common ground, required)
  - Motor power into driver `VM`, **not** from the ESP32 3V3 pin.
  - Motor run = `HIGH/HIGH`, stop = `LOW/LOW` (see `cat_feeding_inator/config.h`).
  - Feeder channels (legacy/active-low relay path): `GPIO5`, `GPIO6`, idle `HIGH`.
- ⚠️ Do not wire the motor to GPIO5/6: those idle at `HIGH/HIGH`
  (= run level), so a motor there spins continuously from boot.

## Firmware

Build with Arduino (`esp32:esp32` core). Two sketches:

- `cat_feeding_inator/` — main app: BLE provisioning + WiFi STA + HTTP server.
  - `POST /motor/run` latches the motor on (`HIGH/HIGH`).
  - `POST /motor/stop` stops it (`LOW/LOW`). Aliases: `POST /run`, `POST /stop`.
  - `POST /motor[?duration=ms]` timed spin (clamped to `MOTOR_MAX_MS` = 2000ms).
  - `POST /feed` legacy feeder pulse (GPIO5/6: 300ms / 500ms gap / 300ms).
  - `GET /status` → `{"status":"online","ip":...,"feeding":...,"motor_running":...}`.
  - HTTP server starts only after WiFi STA connects, so use the STA IP
    (e.g. `10.0.0.128`), not `192.168.4.1` (that's only the `motor_test` AP).
  - BLE service `Cat-Feeding-Inator`: write SSID/password, send `CONNECT`,
    then `FEED` triggers the legacy pulse path.
- `motor_test/` — standalone test: SoftAP `ESP32-Motor-Test` / `motor12345`,
  same `/motor`, `/motor/run`, `/motor/stop` endpoints at `http://192.168.4.1`.
  Serial fallback: `R` = latched run, `r` = 2s spin, `s` = stop.

### Partition scheme (important)

BLE + WiFi + WebServer ≈ 1.29MB. The default 4MB partition only allows
~1.2MB APP (~97-98% full). Select:

- `Tools > Partition Scheme > Minimal SPIFFS (1.9MB APP with OTA)` → ~65%,
  keeps OTA. Recommended (project uses `Preferences`/NVS, not SPIFFS).

or `Huge APP (3MB No OTA)` → ~40%, no OTA slot.

### Build / flash

```bash
arduino-cli compile -b 'esp32:esp32:esp32c3:PartitionScheme=min_spiffs' cat_feeding_inator
arduino-cli upload -b 'esp32:esp32:esp32c3:PartitionScheme=min_spiffs' -p /dev/ttyACM0 cat_feeding_inator
```

Monitor at 115200 baud. Expect:

```
Feeder GPIO initialized.
Motor GPIO initialized.
Motor IN1 = GPIO 0
Motor IN2 = GPIO 1
BLE advertising as Cat-Feeding-Inator
Wi-Fi connected! IP address: 10.0.0.128
HTTP server started
```

Note: flashing is over USB serial only. BLE cannot flash firmware
(no OTA service in this build; see notes in `ble_manager.cpp`).

## Python clients (`client/`)

Stdlib-only HTTP scripts (no extra deps). BLE scripts need `pip install -r requirements.txt`.

- `feed.py` — one feed now: `POST /motor/run`, wait, `POST /motor/stop`.
  Stop is sent in a `finally` block so the motor can't latch on.

  ```bash
  python3 client/feed.py                        # default 10.0.0.128, 6.0s
  python3 client/feed.py --ip 10.0.0.128 --duration 6.0
  FEEDER_IP=10.0.0.128 python3 client/feed.py --duration 2.5
  ```

- `feed_service.py` — scheduled feeding, daily at user-set times (local time).

  ```bash
  python3 client/feed_service.py --times 07:00,18:00
  python3 client/feed_service.py --times 07:00,12:30,18:00 --duration 6.0
  python3 client/feed_service.py --config client/schedule.json
  python3 client/feed_service.py --times 07:00,18:00 --once      # test now
  python3 client/feed_service.py --times 07:00,18:00 --dry-run   # show next fire
  ```

  Config file (JSON): `{"ip": "10.0.0.128", "port": 80, "duration": 6.0, "times": ["07:00", "18:00"]}`.
  Runs in the foreground; keep alive with `nohup`/`tmux` or the systemd
  unit sketched in the script header. `409 busy` skips that cycle;
  errors are logged without killing the service.

  Repeat mode (one feed cycle every N seconds, e.g. testing):

  ```bash
  python3 client/feed_service.py --interval 3 --duration 1
  ```

  `--duration` must be shorter than `--interval` (one cycle = N seconds
  total: motor on, then rest until the next cycle).

- `flash.py` — legacy BLE pulse feed (`FEED` command, waits `FEED:OK`). Unchanged.
- `set_wifi.py` — BLE WiFi provisioning (SSID → password → `CONNECT`).

### Web stack (frontend + backend)

Proper split UI for configuring feeding:

```bash
scripts/dev.sh [--times 07:00,18:00] [-- vite args...]  # foreground: backend + Vite dev
scripts/service.sh start [--times 07:00,18:00]   # background prod: frontend :6606, backend :6607
scripts/service.sh status
scripts/service.sh stop
```

- Frontend `http://localhost:6606` (`client/frontend/`, React + Vite + TS +
  Tailwind, `npm run build` → `dist/`, served statically): live status cards,
  schedule form (daily times or repeat-every-N mode, ESP32 IP/port, motor
  seconds) with client validation, Start/Stop/Feed-now with loading states,
  event log (polls the backend every 3s with backoff). Legacy vanilla UI kept
  in `client/frontend/legacy-vanilla/`. Dev: `npm run dev` (proxies `/api` to
  `:6607`); prod override: `VITE_API_URL=http://host:6607 npm run build`.
- Backend `http://localhost:6607` (`client/backend.py`, stdlib only):
  `GET /api/status`, `POST /api/config|start|stop|feed-now`,
  `GET /api/events`, plus a live ESP32 `/status` proxy. Runs the
  scheduler in-process, persists `client/schedule.json`.
- Env overrides: `FRONTEND_PORT`, `BACKEND_PORT`, `HOST` (default `0.0.0.0`, so
  the UI/API are reachable as `http://toddheadquarters:6606` from the LAN).
  Logs go to `.logs/`, PIDs to `.pids/`.

## Troubleshooting

- `POST /motor` silent, but serial shows `Motor started/stopped`: code ran —
  check common GND, driver `VM` supply, and `ENA`/`STBY` jumpers.
- Motor on GPIO5/6 spins forever: expected — those idle `HIGH/HIGH` = run.
  Move the motor to GPIO0/1.
- GPIO0/1 dead: measure bare pins during run (expect `0V → 3.3V → 0V` on
  both, since run is `HIGH/HIGH`). 0V bare = wrong header holes or bad
  Dupont; live bare but dead wired = harness/loading issue.
- HTTP unreachable on main app: WiFi STA not connected yet — provision via
  BLE first, then use the STA IP from `WIFI:CONNECTED:<ip>`.
- `Sketch uses ~97%`: wrong partition — switch to Minimal SPIFFS (see above).
