#include "Particle.h"
#include <HttpClient.h>

HttpClient http;

http_header_t headers[] = {
    { "Content-Type", "application/json" },
    { NULL, NULL }
};

http_request_t request;
http_response_t response;

String deviceID = "";

// 要找的 iPhone / LightBlue 廣播名稱
const char* TARGET_NAME = "JerryPhone";

// 每幾毫秒量一次 RSSI
const unsigned long SAMPLE_INTERVAL = 2000;
unsigned long lastSample = 0;

void printResponse(http_response_t &response) {
    Serial.println("HTTP Response: ");
    Serial.println(response.status);
    Serial.println(response.body);
}

void sendRssiToServer(int rssi) {
    char json[256] = {0};
    JSONBufferWriter writer(json, sizeof(json) - 1);

    writer.beginObject();
    writer.name("deviceID").value(deviceID);
    writer.name("rssi").value(rssi);          // RSSI 整數 (dBm)
    writer.name("ts").value((int)Time.now()); // 簡單放一個 timestamp
    writer.endObject();

    Serial.println("JSON:");
    Serial.println(json);

    request.path = "/microcontrollerRssi";   // 你在 Node-RED 設的 URL
    request.body = json;

    http.post(request, response, headers);
    printResponse(response);
}

void setup() {
    Serial.begin(9600);

    // ---- Wi-Fi / HTTP 設定（跟原本一樣）----
    request.ip = IPAddress(10, 0, 0, 67); // 你的 Node-RED 那台電腦 IP
    request.port = 1880;

    deviceID = System.deviceID().c_str();
    Serial.printlnf("DeviceID: %s", deviceID.c_str());

    // ---- BLE 設定：當 central 來掃描 ----
    BLE.on();
    Serial.println("BLE RSSI monitor setup complete");

    lastSample = millis();
}

void loop() {
    if (millis() - lastSample >= SAMPLE_INTERVAL) {
        lastSample = millis();

        Serial.println("Scanning for BLE devices...");

        // 最多拿 20 筆掃描結果就好
        BleScanResult results[20];
        size_t count = BLE.scan(results, 20);

        int foundRssi = 0;
        bool found = false;

        for (size_t i = 0; i < count; i++) {
            BleScanResult &r = results[i];

            // 取裝置名稱
            String name = r.advertisingData().deviceName();
            int rssi = r.rssi();  // dBm, 通常是負值，比如 -50, -80 等

            Serial.printlnf("Found: %s RSSI=%d", name.c_str(), rssi);

            if (name.equals(TARGET_NAME)) {
                foundRssi = rssi;
                found = true;
                break;
            }
        }

        if (found) {
            Serial.printlnf("Target %s RSSI=%d, sending to server", TARGET_NAME, foundRssi);
            sendRssiToServer(foundRssi);
        } else {
            Serial.println("Target not found in this scan");
            // 如果沒找到，你可以選擇送一筆 rssi = 0 或跳過
            // sendRssiToServer(0);
        }
    }
}
