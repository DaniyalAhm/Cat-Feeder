#pragma once

#include <Arduino.h>

// Non-blocking motor driver (GPIO0/GPIO1), hard-capped at MOTOR_MAX_MS.
// Call handleMotor() from loop().
void setupMotor();

// Start a run for ms (clamped to 1..MOTOR_MAX_MS).
// Returns false if a run is already in progress.
bool motorRun(unsigned long ms);

// Latched run: IN1=HIGH, IN2=HIGH until motorStop() is called.
// Returns false if a run is already in progress.
bool motorRunLatched();

// Stop immediately (IN1=LOW, IN2=LOW). Idempotent.
void motorStop();

void handleMotor();
bool isMotorRunning();
unsigned long motorLastDuration();
