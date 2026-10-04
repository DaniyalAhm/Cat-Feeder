#pragma once

#include <Arduino.h>

void setupWiFi();
void handleWiFi();

void setWiFiSSID(const String &ssid);
void setWiFiPassword(const String &password);

void requestWiFiConnection();
void requestWiFiScan();

bool isWiFiConnected();
String getWiFiIPAddress();
