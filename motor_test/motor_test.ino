#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

// Motor driver over HTTP POST: ESP32 -> motor driver, spin <= 2 seconds.
//
// Wiring (generic 2-pin H-bridge like L298N / TB6612 / DRV8833 / MX1508):
//   GPIO0 -> IN1
//   GPIO1 -> IN2
//   GND   -> driver GND (common ground required)
// Motor power comes from the driver supply, not the ESP32.
//
// Usage:
//   1. Flash, connect to WiFi AP "ESP32-Motor-Test" (pass: motor12345)
//   2. POST http://192.168.4.1/motor  -> spins default 2000ms
//      POST http://192.168.4.1/motor?duration=1000 -> spins 1000ms (clamped to <=2000)
//      curl -X POST http://192.168.4.1/motor
//      curl -X POST "http://192.168.4.1/motor?duration=1500"
//   3. GET http://192.168.4.1/status -> {"running":false,...}

static const int MOTOR_IN1 = 0; // GPIO0
static const int MOTOR_IN2 = 1; // GPIO1

static const unsigned long MOTOR_MAX_MS = 2000; // hard limit: never run longer
static const unsigned long MOTOR_DEFAULT_MS = 2000;

const char *AP_SSID = "ESP32-Motor-Test";
const char *AP_PASSWORD = "motor12345";

WebServer server(80);

static bool motorRunning = false;
static unsigned long motorStart = 0;
static unsigned long motorDuration = 0;

void motorStop() {
    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, LOW);
}

// Returns false if a run is already in progress.
bool motorStartRun(unsigned long ms) {
    if (motorRunning) {
        return false;
    }
    if (ms == 0) {
        ms = MOTOR_DEFAULT_MS;
    }
    if (ms > MOTOR_MAX_MS) {
        ms = MOTOR_MAX_MS; // clamp: never exceed 2s
    }
    motorDuration = ms;
    motorStart = millis();
    motorRunning = true;

    // Run: IN1=HIGH, IN2=HIGH
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, HIGH);

    Serial.print("Motor started for ");
    Serial.print(motorDuration);
    Serial.println("ms");
    return true;
}

void handleMotor() {
    if (!motorRunning) {
        return;
    }
    if (motorDuration == 0) {
        return; // latched run: only stop endpoint stops it.
    }
    if (millis() - motorStart >= motorDuration) {
        motorStop();
        motorRunning = false;
        Serial.println("Motor stopped (timeout).");
    }
}

// Latched run: IN1=HIGH, IN2=HIGH until stopped.
bool motorStartLatched() {
    if (motorRunning) {
        return false;
    }
    motorDuration = 0;
    motorStart = millis();
    motorRunning = true;

    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, HIGH);

    Serial.println("Motor running (latched HIGH/HIGH). Send stop.");
    return true;
}

void motorStopNow() {
    motorStop();
    motorDuration = 0;
    if (motorRunning) {
        motorRunning = false;
        Serial.println("Motor stopped.");
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(MOTOR_IN1, OUTPUT);
    pinMode(MOTOR_IN2, OUTPUT);
    motorStop(); // safe state first

    Serial.println();
    Serial.println("=== ESP32 Motor POST Test ===");

    WiFi.mode(WIFI_AP);
    bool started = WiFi.softAP(AP_SSID, AP_PASSWORD, 6, false, 4);
    if (!started) {
        Serial.println("SoftAP failed.");
        return;
    }
    WiFi.setTxPower(WIFI_POWER_8_5dBm);

    Serial.print("SSID: ");
    Serial.println(AP_SSID);
    Serial.print("IP: ");
    Serial.println(WiFi.softAPIP());

    server.on("/", HTTP_GET, []() {
        server.send(200, "text/html",
            "<h1>Motor Test</h1>"
            "<form method=\"POST\" action=\"/motor\">"
            "<button type=\"submit\">Spin 2s</button>"
            "</form>"
            "<form method=\"POST\" action=\"/motor?duration=1000\">"
            "<button type=\"submit\">Spin 1s</button>"
            "</form>"
            "<form method=\"POST\" action=\"/motor/run\">"
            "<button type=\"submit\">Run motor</button>"
            "</form>"
            "<form method=\"POST\" action=\"/motor/stop\">"
            "<button type=\"submit\">Stop motor</button>"
            "</form>"
            "<p><a href=\"/status\">status</a></p>");
    });

    server.on("/status", HTTP_GET, []() {
        String r = String("{\"running\":") + (motorRunning ? "true" : "false") +
            ",\"max_ms\":" + MOTOR_MAX_MS + "}";
        server.send(200, "application/json", r);
    });

    // POST /motor[?duration=ms] — duration clamped to <= 2000
    server.on("/motor", HTTP_POST, []() {
        unsigned long want = MOTOR_DEFAULT_MS;
        if (server.hasArg("duration")) {
            want = (unsigned long)server.arg("duration").toInt();
        } else if (server.hasArg("plain")) {
            // tiny JSON support: {"duration":1500}
            String body = server.arg("plain");
            int idx = body.indexOf("duration");
            if (idx >= 0) {
                int colon = body.indexOf(':', idx);
                if (colon >= 0) {
                    want = (unsigned long)body.substring(colon + 1).toInt();
                }
            }
        }
        if (want == 0) {
            want = MOTOR_DEFAULT_MS;
        }
        if (want > MOTOR_MAX_MS) {
            want = MOTOR_MAX_MS;
        }

        if (!motorStartRun(want)) {
            server.send(409, "application/json", "{\"ok\":false,\"error\":\"busy\"}");
            return;
        }
        String r = String("{\"ok\":true,\"duration_ms\":") + want + "}";
        server.send(200, "application/json", r);
    });

    auto handleRun = []() {
        if (!motorStartLatched()) {
            server.send(409, "application/json", "{\"ok\":false,\"error\":\"busy\"}");
            return;
        }
        server.send(200, "application/json",
            "{\"ok\":true,\"action\":\"motor_run\",\"in1\":\"HIGH\",\"in2\":\"HIGH\"}");
    };

    auto handleStop = []() {
        motorStopNow();
        server.send(200, "application/json", "{\"ok\":true,\"action\":\"motor_stop\"}");
    };

    server.on("/motor/run", HTTP_POST, handleRun);
    server.on("/motor/stop", HTTP_POST, handleStop);
    server.on("/run", HTTP_POST, handleRun);
    server.on("/stop", HTTP_POST, handleStop);

    server.begin();
    Serial.println("HTTP server started. POST /motor to spin.");
}

void loop() {
    server.handleClient();
    handleMotor(); // non-blocking auto-stop guarantees <= 2s

    // Serial fallback: 'r' = run 2s, 'R' = latched run, 's' = stop
    if (Serial.available()) {
        char c = (char)Serial.read();
        if (c == 'r') {
            if (!motorStartRun(MOTOR_DEFAULT_MS)) {
                Serial.println("Busy: motor already running.");
            }
        } else if (c == 'R') {
            if (!motorStartLatched()) {
                Serial.println("Busy: motor already running.");
            }
        } else if (c == 's' || c == 'S') {
            motorStopNow();
        }
    }
    delay(5);
}
