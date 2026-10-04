#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

#include "web_server.h"
#include "config.h"
#include "feeder.h"
#include "motor.h"

WebServer server(80);

bool httpServerStarted = false;

void startHttpServer() {

    if (httpServerStarted) {
        return;
    }
server.on(
    "/test/channel1",
    HTTP_POST,
    []() {

        Serial.println(
            "HTTP test channel 1"
        );

        testChannel1();

        server.send(
            200,
            "application/json",
            String("{\"ok\":true,\"channel\":1,\"gpio\":") + CHANNEL1_PIN + "}"
        );
    }
);


server.on(
    "/test/channel2",
    HTTP_POST,
    []() {

        Serial.println(
            "HTTP test channel 2"
        );

        testChannel2();

        server.send(
            200,
            "application/json",
            String("{\"ok\":true,\"channel\":2,\"gpio\":") + CHANNEL2_PIN + "}"
        );
    }
);
    server.on(
        "/",
        HTTP_GET,
        []() {
            server.send(
                200,
                "text/html",
                "<h1>Cat-Feeding-Inator</h1>"
                "<p><a href=\"/status\">status</a></p>"
                "<form method=\"POST\" action=\"/feed\">"
                "<button type=\"submit\">Feed</button>"
                "</form>"
                "<form method=\"POST\" action=\"/motor\">"
                "<button type=\"submit\">Spin motor 2s</button>"
                "</form>"
                "<form method=\"POST\" action=\"/motor/run\">"
                "<button type=\"submit\">Run motor</button>"
                "</form>"
                "<form method=\"POST\" action=\"/motor/stop\">"
                "<button type=\"submit\">Stop motor</button>"
                "</form>"
            );
        }
    );

    server.on(
        "/status",
        HTTP_GET,
        []() {

            String response =
                "{\"status\":\"online\","
                "\"ip\":\"" +
                WiFi.localIP().toString() +
                "\",\"feeding\":" +
                (isFeeding() ? "true" : "false") +
                ",\"motor_running\":" +
                (isMotorRunning() ? "true" : "false") +
                "}";

            server.send(
                200,
                "application/json",
                response
            );
        }
    );

    server.on(
        "/feed",
        HTTP_POST,
        []() {

            if (!feedCat()) {
                server.send(
                    409,
                    "application/json",
                    "{\"ok\":false,\"error\":\"busy\"}"
                );
                return;
            }

            server.send(
                200,
                "application/json",
                "{\"ok\":true,\"action\":\"feed\"}"
            );
        }
    );

    server.on(
        "/motor",
        HTTP_POST,
        []() {
            unsigned long want = MOTOR_DEFAULT_MS;

            if (server.hasArg("duration")) {
                want = (unsigned long)server.arg("duration").toInt();
            } else if (server.hasArg("plain")) {
                // Tiny JSON support: {"duration":1500}
                String body = server.arg("plain");
                int idx = body.indexOf("duration");
                if (idx >= 0) {
                    int colon = body.indexOf(':', idx);
                    if (colon >= 0) {
                        want = (unsigned long)body.substring(colon + 1).toInt();
                    }
                }
            }

            if (want == 0) {
                want = MOTOR_DEFAULT_MS;
            }
            if (want > MOTOR_MAX_MS) {
                want = MOTOR_MAX_MS;
            }

            if (!motorRun(want)) {
                server.send(
                    409,
                    "application/json",
                    "{\"ok\":false,\"error\":\"busy\"}"
                );
                return;
            }

            String response =
                String("{\"ok\":true,\"action\":\"motor\",\"duration_ms\":") +
                want + "}";

            server.send(
                200,
                "application/json",
                response
            );
        }
    );

    server.onNotFound(
        []() {
            String response =
                String("{\"ok\":false,\"error\":\"Not found: ") +
                server.uri() + "\"}";

            server.send(
                404,
                "application/json",
                response
            );
        }
    );

    auto handleMotorRun = []() {
        if (!motorRunLatched()) {
            server.send(
                409,
                "application/json",
                "{\"ok\":false,\"error\":\"busy\"}"
            );
            return;
        }

        server.send(
            200,
            "application/json",
            "{\"ok\":true,\"action\":\"motor_run\",\"in1\":\"HIGH\",\"in2\":\"HIGH\"}"
        );
    };

    auto handleMotorStop = []() {
        motorStop();

        server.send(
            200,
            "application/json",
            "{\"ok\":true,\"action\":\"motor_stop\"}"
        );
    };

    server.on("/motor/run", HTTP_POST, handleMotorRun);
    server.on("/motor/stop", HTTP_POST, handleMotorStop);
    // Aliases: POST /run and POST /stop do the same thing.
    server.on("/run", HTTP_POST, handleMotorRun);
    server.on("/stop", HTTP_POST, handleMotorStop);

    server.begin();

    httpServerStarted = true;

    Serial.println(
        "HTTP server started"
    );
}

void handleWebServer() {

    if (
        httpServerStarted &&
        WiFi.status() == WL_CONNECTED
    ) {
        server.handleClient();
    }
}
