#include <Arduino.h>
#include <WiFi.h>

const char *AP_SSID = "ESP32-C3-Test";
const char *AP_PASSWORD = "test12345";

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("=== ESP32-C3 SoftAP Test ===");

    WiFi.mode(WIFI_AP);

    bool started = WiFi.softAP(
        AP_SSID,
        AP_PASSWORD,
        6,
        false,
        4
    );

    if (!started) {
        Serial.println("SoftAP failed.");
        return;
    }

    // Important test for problematic C3 Super Mini boards
    WiFi.setTxPower(
        WIFI_POWER_8_5dBm
    );

    Serial.println("SoftAP started.");
    Serial.println("TX power lowered to 8.5 dBm");

    Serial.print("SSID: ");
    Serial.println(AP_SSID);

    Serial.print("IP: ");
    Serial.println(WiFi.softAPIP());
}

void loop() {
    Serial.print("Clients: ");
    Serial.println(
        WiFi.softAPgetStationNum()
    );

    delay(2000);
}
