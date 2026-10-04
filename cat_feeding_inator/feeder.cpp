#include <Arduino.h>

#include "feeder.h"
#include "config.h"


static bool feeding = false;
static int feedPhase = 0;  // 0 = ch1 pulse, 1 = gap, 2 = ch2 pulse
static unsigned long phaseStart = 0;


// --------------------------------------------------
// Setup
// --------------------------------------------------

void setupFeeder() {

    pinMode(
        CHANNEL1_PIN,
        OUTPUT
    );

    pinMode(
        CHANNEL2_PIN,
        OUTPUT
    );


    digitalWrite(
        CHANNEL1_PIN,
        CHANNEL_OFF
    );

    digitalWrite(
        CHANNEL2_PIN,
        CHANNEL_OFF
    );


    Serial.println(
        "Feeder GPIO initialized."
    );

    Serial.print(
        "Channel 1 = GPIO "
    );

    Serial.println(
        CHANNEL1_PIN
    );

    Serial.print(
        "Channel 2 = GPIO "
    );

    Serial.println(
        CHANNEL2_PIN
    );
}


// --------------------------------------------------
// Individual channel tests (blocking, HTTP context only)
// --------------------------------------------------

void testChannel1() {

    if (feeding) {
        Serial.println(
            "Channel 1 test skipped: feed in progress"
        );
        return;
    }

    Serial.print(
        "Testing channel 1 / GPIO "
    );

    Serial.println(
        CHANNEL1_PIN
    );

    digitalWrite(
        CHANNEL1_PIN,
        CHANNEL_ON
    );

    delay(TEST_PULSE_MS);

    digitalWrite(
        CHANNEL1_PIN,
        CHANNEL_OFF
    );

    Serial.println(
        "Channel 1 test complete"
    );
}


void testChannel2() {

    if (feeding) {
        Serial.println(
            "Channel 2 test skipped: feed in progress"
        );
        return;
    }

    Serial.print(
        "Testing channel 2 / GPIO "
    );

    Serial.println(
        CHANNEL2_PIN
    );

    digitalWrite(
        CHANNEL2_PIN,
        CHANNEL_ON
    );

    delay(TEST_PULSE_MS);

    digitalWrite(
        CHANNEL2_PIN,
        CHANNEL_OFF
    );

    Serial.println(
        "Channel 2 test complete"
    );
}


// --------------------------------------------------
// Feed sequence (non-blocking)
// --------------------------------------------------

bool feedCat() {

    if (feeding) {
        return false;
    }

    feeding = true;
    feedPhase = 0;
    phaseStart = millis();

    Serial.println(
        "Feed started: pressing channel 1"
    );

    digitalWrite(
        CHANNEL1_PIN,
        CHANNEL_ON
    );

    return true;
}

void handleFeeder() {

    if (!feeding) {
        return;
    }

    unsigned long now = millis();

    if (feedPhase == 0) {
        if (now - phaseStart >= CH1_PULSE_MS) {
            digitalWrite(
                CHANNEL1_PIN,
                CHANNEL_OFF
            );
            Serial.println(
                "Channel 1 released, gap started"
            );
            feedPhase = 1;
            phaseStart = now;
        }
        return;
    }

    if (feedPhase == 1) {
        if (now - phaseStart >= FEED_GAP_MS) {
            Serial.println(
                "Pressing channel 2"
            );
            digitalWrite(
                CHANNEL2_PIN,
                CHANNEL_ON
            );
            feedPhase = 2;
            phaseStart = now;
        }
        return;
    }

    if (feedPhase == 2) {
        if (now - phaseStart >= CH2_PULSE_MS) {
            digitalWrite(
                CHANNEL2_PIN,
                CHANNEL_OFF
            );
            feeding = false;
            feedPhase = 0;
            Serial.println(
                "Feed sequence complete"
            );
        }
        return;
    }
}


// --------------------------------------------------
// Status
// --------------------------------------------------

bool isFeeding() {

    return feeding;
}
