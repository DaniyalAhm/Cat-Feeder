#pragma once

void setupFeeder();

bool feedCat();

// Advance the non-blocking feed state machine. Call from loop().
void handleFeeder();

void testChannel1();
void testChannel2();

bool isFeeding();
