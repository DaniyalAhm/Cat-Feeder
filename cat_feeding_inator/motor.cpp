#include <Arduino.h>

#include "motor.h"
#include "config.h"

static bool running = false;
static unsigned long startMs = 0;
static unsigned long durationMs = 0;

void setupMotor() {
    pinMode(MOTOR_IN1_PIN, OUTPUT);
    pinMode(MOTOR_IN2_PIN, OUTPUT);

    // Safe state first: coast/stop.
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);

    Serial.println("Motor GPIO initialized.");
    Serial.print("Motor IN1 = GPIO ");
    Serial.println(MOTOR_IN1_PIN);
    Serial.print("Motor IN2 = GPIO ");
    Serial.println(MOTOR_IN2_PIN);
}

bool motorRun(unsigned long ms) {
    if (running) {
        return false;
    }
    if (ms == 0) {
        ms = MOTOR_DEFAULT_MS;
    }
    if (ms > MOTOR_MAX_MS) {
        ms = MOTOR_MAX_MS;
    }

    durationMs = ms;
    startMs = millis();
    running = true;

    // Run: IN1=HIGH, IN2=HIGH.
    digitalWrite(MOTOR_IN1_PIN, HIGH);
    digitalWrite(MOTOR_IN2_PIN, HIGH);

    Serial.print("Motor started for ");
    Serial.print(durationMs);
    Serial.println("ms");

    return true;
}

void handleMotor() {
    if (!running) {
        return;
    }
    if (durationMs == 0) {
        return;  // latched run: only motorStop() stops it.
    }
    if (millis() - startMs >= durationMs) {
        digitalWrite(MOTOR_IN1_PIN, LOW);
        digitalWrite(MOTOR_IN2_PIN, LOW);
        running = false;
        Serial.println("Motor stopped (timeout).");
    }
}

bool motorRunLatched() {
    if (running) {
        return false;
    }
    durationMs = 0;  // 0 = latched, no timeout.
    startMs = millis();
    running = true;

    // Run, HIGH level: IN1=HIGH, IN2=HIGH.
    digitalWrite(MOTOR_IN1_PIN, HIGH);
    digitalWrite(MOTOR_IN2_PIN, HIGH);

    Serial.println("Motor running (latched HIGH/HIGH). Send stop.");

    return true;
}

void motorStop() {
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);
    durationMs = 0;
    if (running) {
        running = false;
        Serial.println("Motor stopped.");
    }
}

bool isMotorRunning() {
    return running;
}

unsigned long motorLastDuration() {
    return durationMs;
}
