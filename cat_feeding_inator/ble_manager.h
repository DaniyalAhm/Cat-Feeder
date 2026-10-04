#pragma once

#include <Arduino.h>

void setupBLE();

// Called by wifi_manager / feeder to report state to the BLE client.
// Safe to call before setupBLE() (buffered until advertising starts).
void bleSetStatus(const String &status);
void bleSetScanResult(const String &json);
String bleGetStatus();

// Pump feed-completion status (STARTED -> OK). Call from loop().
void handleBLE();
