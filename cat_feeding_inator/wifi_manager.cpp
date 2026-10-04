#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>

#include "wifi_manager.h"
#include "ble_manager.h"
#include "web_server.h"


static Preferences preferences;

static String pendingSSID = "";
static String pendingPassword = "";

static bool connectRequested = false;
static bool wifiConnecting = false;
static bool wasConnected = false;

static unsigned long connectionStart = 0;
static unsigned long lastDropMillis = 0;

static const unsigned long WIFI_TIMEOUT = 20000;
static const unsigned long RECONNECT_DELAY = 5000;

static volatile uint8_t lastWifiDisconnectReason = 0;

static bool scanRequested = false;
static bool scanRunning = false;


// --------------------------------------------------
// Save credentials
// --------------------------------------------------

static void saveCredentials(
    const String &ssid,
    const String &password
) {
    preferences.begin(
        "wifi",
        false
    );

    preferences.putString(
        "ssid",
        ssid
    );

    preferences.putString(
        "password",
        password
    );

    preferences.end();

    Serial.println(
        "Wi-Fi credentials saved."
    );
}


// --------------------------------------------------
// Load credentials
// --------------------------------------------------

static bool loadCredentials(
    String &ssid,
    String &password
) {
    preferences.begin(
        "wifi",
        true
    );

    ssid =
        preferences.getString(
            "ssid",
            ""
        );

    password =
        preferences.getString(
            "password",
            ""
        );

    preferences.end();

    return ssid.length() > 0;
}


// --------------------------------------------------
// Wi-Fi events
// --------------------------------------------------

static void WiFiEvent(
    WiFiEvent_t event,
    WiFiEventInfo_t info
) {
    switch (event) {

      case ARDUINO_EVENT_WIFI_STA_CONNECTED:{

            Serial.println(
                "WiFi: connected to AP"
            );

            break;

        }
      case ARDUINO_EVENT_WIFI_STA_GOT_IP:{

           IPAddress ip =
                WiFi.localIP();

            Serial.print(
                "WiFi: got IP "
            );

            Serial.print(ip[0]);
            Serial.print(".");
            Serial.print(ip[1]);
            Serial.print(".");
            Serial.print(ip[2]);
            Serial.print(".");
            Serial.println(ip[3]);

            break;
        }

      case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:{

            lastWifiDisconnectReason =
                info.wifi_sta_disconnected.reason;

            Serial.print(
                "WiFi disconnected. Reason: "
            );

            Serial.println(
                lastWifiDisconnectReason
            );

            break;

        }
        default:

            break;
    }
}


// --------------------------------------------------
// Connect
// --------------------------------------------------

static void connectWiFi() {

    if (pendingSSID.length() == 0) {

        Serial.println(
            "ERROR: No SSID provided."
        );

        bleSetStatus("ERROR:No SSID");

        return;
    }


    Serial.println(
        "Resetting Wi-Fi connection..."
    );


    WiFi.setAutoReconnect(false);

    WiFi.disconnect(
        true,
        false
    );

    delay(500);


    WiFi.mode(
        WIFI_STA
    );

    delay(250);


    // Required for this ESP32-C3 board's
    // problematic antenna/RF behavior.
    WiFi.setTxPower(
        WIFI_POWER_8_5dBm
    );


    lastWifiDisconnectReason = 0;


    Serial.print(
        "Connecting to SSID: "
    );

    Serial.println(
        pendingSSID
    );

    bleSetStatus("WIFI:CONNECTING");


    WiFi.begin(
        pendingSSID.c_str(),
        pendingPassword.c_str()
    );


    wifiConnecting = true;

    connectionStart =
        millis();
}


// --------------------------------------------------
// Public setters
// --------------------------------------------------

void setWiFiSSID(
    const String &ssid
) {
    pendingSSID = ssid;
    pendingSSID.trim();
}


void setWiFiPassword(
    const String &password
) {
    pendingPassword = password;
}


void requestWiFiConnection() {

    if (wifiConnecting) {

        Serial.println(
            "Wi-Fi already connecting."
        );

        return;
    }

    connectRequested = true;
}


void requestWiFiScan() {
    scanRequested = true;
}


// --------------------------------------------------
// Setup
// --------------------------------------------------

void setupWiFi() {

    WiFi.onEvent(
        WiFiEvent
    );


    String savedSSID;
    String savedPassword;


    if (
        loadCredentials(
            savedSSID,
            savedPassword
        )
    ) {

        Serial.println(
            "Saved Wi-Fi credentials found."
        );

        pendingSSID =
            savedSSID;

        pendingPassword =
            savedPassword;

        connectRequested =
            true;
    }
}


// --------------------------------------------------
// Loop handler
// --------------------------------------------------

static String escapeJson(const String &in) {
    String out;
    out.reserve(in.length());
    for (size_t i = 0; i < in.length(); i++) {
        char c = in.charAt(i);
        if (c == '"' || c == '\\') {
            out += '\\';
            out += c;
        } else if (c >= 0x20) {
            out += c;
        }
        // Drop other control chars: they would break the BLE JSON payload.
    }
    return out;
}

static void pollScan() {
    if (scanRequested && !scanRunning && !wifiConnecting) {
        scanRequested = false;
        scanRunning = true;
        WiFi.mode(WIFI_STA);
        WiFi.scanNetworks(true, false);
        Serial.println("Wi-Fi scan started");
        return;
    }

    if (scanRunning) {
        int16_t n = WiFi.scanComplete();
        if (n < 0) {
            return;  // still scanning
        }
        scanRunning = false;

        String json = "[";
        int entries = 0;
        int count = n;
        if (count > 12) {
            count = 12;  // keep BLE payload small (MTU-friendly)
        }
        for (int i = 0; i < count; i++) {
            String entry = "{\"ssid\":\"" + escapeJson(WiFi.SSID(i)) + "\"";
            entry += ",\"rssi\":" + String(WiFi.RSSI(i));
            entry += "}";
            // BLE characteristic values top out ~512 bytes; leave margin.
            if (json.length() + entry.length() + 2 > 480) {
                break;
            }
            if (entries > 0) {
                json += ",";
            }
            json += entry;
            entries++;
        }
        json += "]";
        WiFi.scanDelete();

        bleSetScanResult(json);
        bleSetStatus("WIFI:SCAN_DONE:" + String(n));

        // If we were connected before, resume the STA connection.
        if (wasConnected && pendingSSID.length() > 0) {
            connectRequested = true;
        }
    }
}

void handleWiFi() {

    if (connectRequested) {

        connectRequested = false;

        connectWiFi();
    }

    pollScan();


    if (wifiConnecting) {

        if (
            WiFi.status() ==
            WL_CONNECTED
        ) {

            wifiConnecting = false;
            wasConnected = true;


            Serial.println(
                "Wi-Fi connected!"
            );


            Serial.print(
                "IP address: "
            );

            Serial.println(
                WiFi.localIP()
            );


            saveCredentials(
                pendingSSID,
                pendingPassword
            );


            bleSetStatus(
                "WIFI:CONNECTED:" + WiFi.localIP().toString()
            );

            WiFi.setAutoReconnect(true);

            startHttpServer();

            return;
        }


        if (
            millis() -
            connectionStart >
            WIFI_TIMEOUT
        ) {

            wifiConnecting = false;


            Serial.print(
                "Wi-Fi connection failed. Reason: "
            );

            Serial.println(
                lastWifiDisconnectReason
            );

            bleSetStatus(
                "WIFI:FAILED:" + String(lastWifiDisconnectReason)
            );


            WiFi.disconnect(
                true,
                false
            );
        }

        return;
    }

    // Reconnect if we lose an established connection.
    if (wasConnected && WiFi.status() != WL_CONNECTED) {
        if (millis() - lastDropMillis > RECONNECT_DELAY) {
            lastDropMillis = millis();
            Serial.println("Wi-Fi lost, reconnecting...");
            bleSetStatus("WIFI:DISCONNECTED");
            if (pendingSSID.length() > 0) {
                connectRequested = true;
            } else {
                wasConnected = false;
            }
        }
    } else if (WiFi.status() == WL_CONNECTED) {
        wasConnected = true;
    }
}


// --------------------------------------------------
// Status
// --------------------------------------------------

bool isWiFiConnected() {

    return (
        WiFi.status() ==
        WL_CONNECTED
    );
}


String getWiFiIPAddress() {

    return WiFi.localIP().toString();
}
