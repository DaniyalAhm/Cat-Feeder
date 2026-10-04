#pragma once

#define DEVICE_NAME \
    "Cat-Feeding-Inator"

#define SERVICE_UUID \
    "12345678-1234-1234-1234-123456789000"

#define SSID_UUID \
    "12345678-1234-1234-1234-123456789001"

#define PASSWORD_UUID \
    "12345678-1234-1234-1234-123456789002"

#define COMMAND_UUID \
    "12345678-1234-1234-1234-123456789003"

#define STATUS_UUID \
    "12345678-1234-1234-1234-123456789004"

#define SCAN_RESULT_UUID \
    "12345678-1234-1234-1234-123456789005"

// Feeder GPIO assignments (must match feeder.cpp + web_server.cpp).
// Feeder now GPIO 5/6 (Active-LOW, idle HIGH = safe at boot).
// Motor now GPIO 0/1.
#define CHANNEL1_PIN 5
#define CHANNEL2_PIN 6

// Motor driver (H-bridge IN1/IN2 like L298N / TB6612 / DRV8833).
// GPIO0 -> IN1, GPIO1 -> IN2. HIGH/HIGH = run, LOW/LOW = stop.
#define MOTOR_IN1_PIN 0
#define MOTOR_IN2_PIN 1

// Hard limit: motor can never run longer than this per POST.
#define MOTOR_MAX_MS 2000
#define MOTOR_DEFAULT_MS 2000

// Active-LOW polarity: LOW drives the channel ON (GND pulse), HIGH is idle.
#define CHANNEL_ON LOW
#define CHANNEL_OFF HIGH

#define CH1_PULSE_MS 300
#define FEED_GAP_MS 500
#define CH2_PULSE_MS 300
#define TEST_PULSE_MS 500
