#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#include "ble_manager.h"
#include "config.h"
#include "wifi_manager.h"
#include "feeder.h"

static BLEServer *bleServer = nullptr;
static BLECharacteristic *statusChar = nullptr;
static BLECharacteristic *scanResultChar = nullptr;

static String currentStatus = "BOOT";
static String pendingStatus = "";
static bool bleReady = false;
static bool deviceConnected = false;

static void updateStatusChar(const String &s) {
    currentStatus = s;
    if (!bleReady || statusChar == nullptr) {
        // Buffer until setupBLE() finishes.
        pendingStatus = s;
        return;
    }
    statusChar->setValue(s.c_str());
    if (deviceConnected) {
        statusChar->notify();
    }
}

void bleSetStatus(const String &status) {
    updateStatusChar(status);
    Serial.print("BLE status: ");
    Serial.println(status);
}

void bleSetScanResult(const String &json) {
    if (!bleReady || scanResultChar == nullptr) {
        return;
    }
    scanResultChar->setValue(json.c_str());
    if (deviceConnected) {
        scanResultChar->notify();
    }
}

String bleGetStatus() {
    return currentStatus;
}

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer *server) override {
        deviceConnected = true;
        Serial.println("BLE client connected");
        // Re-advertise so another provisioner can find us after disconnect.
        server->getAdvertising()->start();
    }

    void onDisconnect(BLEServer *server) override {
        deviceConnected = false;
        Serial.println("BLE client disconnected");
        server->getAdvertising()->start();
    }
};

class SsidCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *c) override {
        String ssid = String(c->getValue().c_str());
        ssid.trim();
        if (ssid.length() == 0) {
            bleSetStatus("ERROR:Empty SSID");
            return;
        }
        setWiFiSSID(ssid);
        bleSetStatus("SSID:RECEIVED");
    }
};

class PasswordCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *c) override {
        // Passwords are significant: do NOT trim interior spaces.
        String password = String(c->getValue().c_str());
        setWiFiPassword(password);
        bleSetStatus("PASSWORD:RECEIVED");
    }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *c) override {
        String cmd = String(c->getValue().c_str());
        cmd.trim();
        cmd.toUpperCase();

        if (cmd == "CONNECT") {
            bleSetStatus("CONNECT:REQUESTED");
            requestWiFiConnection();
        } else if (cmd == "SCAN") {
            bleSetStatus("WIFI:SCANNING");
            requestWiFiScan();
        } else if (cmd == "FEED" || cmd == "FLASH") {
            // FLASH kept as an alias: legacy client sent FLASH.
            if (feedCat()) {
                bleSetStatus("FEED:STARTED");
            } else {
                bleSetStatus("FEED:BUSY");
            }
        } else {
            bleSetStatus("ERROR:Unknown command");
        }
    }
};

void setupBLE() {
    Serial.println("BLE setup starting...");

    BLEDevice::init(DEVICE_NAME);

    bleServer = BLEDevice::createServer();
    bleServer->setCallbacks(new ServerCallbacks());

    BLEService *service = bleServer->createService(SERVICE_UUID);

    BLECharacteristic *ssidChar = service->createCharacteristic(
        SSID_UUID, BLECharacteristic::PROPERTY_WRITE);
    ssidChar->setCallbacks(new SsidCallbacks());

    BLECharacteristic *passwordChar = service->createCharacteristic(
        PASSWORD_UUID, BLECharacteristic::PROPERTY_WRITE);
    passwordChar->setCallbacks(new PasswordCallbacks());

    BLECharacteristic *commandChar = service->createCharacteristic(
        COMMAND_UUID, BLECharacteristic::PROPERTY_WRITE);
    commandChar->setCallbacks(new CommandCallbacks());

    statusChar = service->createCharacteristic(
        STATUS_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
    statusChar->addDescriptor(new BLE2902());

    scanResultChar = service->createCharacteristic(
        SCAN_RESULT_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
    scanResultChar->addDescriptor(new BLE2902());
    scanResultChar->setValue("[]");

    service->start();

    BLEAdvertising *advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(SERVICE_UUID);
    advertising->setScanResponse(true);
    advertising->start();

    bleReady = true;

    // Flush any status set before BLE was ready (e.g. "BOOT").
    if (pendingStatus.length() > 0) {
        String s = pendingStatus;
        pendingStatus = "";
        statusChar->setValue(s.c_str());
        currentStatus = s;
    } else {
        statusChar->setValue(currentStatus.c_str());
    }

    Serial.println("BLE advertising as " DEVICE_NAME);
}

void handleBLE() {
    // Feed completion is reported here so the BLE client can poll STATUS.
    // handleFeeder() flips isFeeding() false when done; promote STARTED -> OK.
    static bool wasFeeding = false;
    bool nowFeeding = isFeeding();
    if (wasFeeding && !nowFeeding) {
        if (currentStatus == "FEED:STARTED") {
            bleSetStatus("FEED:OK");
        }
    }
    wasFeeding = nowFeeding;
}
