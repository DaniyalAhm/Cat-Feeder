#include "wifi_manager.h"
#include "ble_manager.h"
#include "web_server.h"
#include "feeder.h"
#include "motor.h"

void setup() {
    Serial.begin(115200);

    setupFeeder();
    setupMotor();
    setupWiFi();
    setupBLE();

    bleSetStatus("BOOT:READY");
}

void loop() {
    handleWiFi();
    handleFeeder();
    handleMotor();
    handleBLE();
    handleWebServer();

    delay(20);
}
