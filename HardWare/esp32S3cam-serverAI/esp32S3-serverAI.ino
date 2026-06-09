#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsClient.h>

// ======================================================
// 1. WIFI + BACKEND CONFIG
// ======================================================
const char* ssid = "Room Room";
const char* password = "khongcopass";

// IP laptop chạy FastAPI BE
const char* ws_host = "192.168.2.101";
const int ws_port = 8000;
const char* ws_path = "/api/v1/ws/detect";

WebSocketsClient webSocket;

// ======================================================
// 2. PIN MAPPING ESP32-S3 N16R8 CAM OV2640 / OV5640
// ======================================================
#define PWDN_GPIO_NUM   -1
#define RESET_GPIO_NUM  -1

#define XCLK_GPIO_NUM   15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5

// Camera data bus D0 -> D7
#define Y2_GPIO_NUM     11   // D0
#define Y3_GPIO_NUM      9   // D1
#define Y4_GPIO_NUM      8   // D2
#define Y5_GPIO_NUM     10   // D3
#define Y6_GPIO_NUM     12   // D4
#define Y7_GPIO_NUM     18   // D5
#define Y8_GPIO_NUM     17   // D6
#define Y9_GPIO_NUM     16   // D7

#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM   13

// ======================================================
// 3. BUTTON CONFIG
// ======================================================
// Nối: GPIO21 ---- Nút nhấn ---- GND
// Dùng INPUT_PULLUP:
// - Chưa nhấn = HIGH
// - Nhấn = LOW
#define BUTTON_PIN 21

bool studySessionActive = false;

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;

unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

// ======================================================
// 4. FPS CONFIG
// ======================================================
unsigned long prev_ms = 0;

// 70ms tương đương tối đa khoảng 14 FPS lý thuyết.
// FPS thật còn phụ thuộc camera, WiFi, WebSocket, server.
const uint16_t interval = 70;

unsigned long fps_timer = 0;
uint16_t sent_frames = 0;

// ======================================================
// 5. STATUS FLAGS
// ======================================================
bool cameraReady = false;

// ======================================================
// FUNCTION PROTOTYPES
// ======================================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length);
bool initCamera();
void initWiFi();
void handleButton();
void sendStudySessionState();
void sendCameraFrame();

// ======================================================
// 6. SEND STUDY SESSION STATE TO BACKEND
// ======================================================
void sendStudySessionState() {
  if (!webSocket.isConnected()) {
    Serial.println("⚠️ WebSocket not connected, cannot send study state now");
    return;
  }

  String msg = "{";
  msg += "\"type\":\"button\",";
  msg += "\"device\":\"esp32_s3_camera\",";
  msg += "\"study_session_active\":";

  if (studySessionActive) {
    msg += "true";
  } else {
    msg += "false";
  }

  msg += "}";

  bool ok = webSocket.sendTXT(msg);

  if (ok) {
    Serial.print("📤 Sent study state to BE: ");
    Serial.println(msg);
  } else {
    Serial.println("❌ Failed to send study state");
  }
}

// ======================================================
// 7. WEBSOCKET EVENT
// ======================================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket disconnected");
      break;

    case WStype_CONNECTED:
      Serial.println("✅ WebSocket connected");
      Serial.printf("URL: %s\n", payload);

      // Khi reconnect, gửi lại trạng thái hiện tại cho BE
      sendStudySessionState();
      break;

    case WStype_TEXT:
      Serial.printf("📩 Text from BE: %s\n", payload);
      break;

    case WStype_BIN:
      Serial.println("📦 Binary from BE received");
      break;

    case WStype_ERROR:
      Serial.println("🚨 WebSocket error");
      break;

    default:
      break;
  }
}

// ======================================================
// 8. CAMERA INIT
// ======================================================
bool initCamera() {
  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Realtime object detection
  config.frame_size = FRAMESIZE_QVGA;  // 320x240
  config.jpeg_quality = 9;             // nhỏ hơn = nét hơn, lớn hơn = nhẹ hơn

  config.fb_count = 2;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  if (!psramFound()) {
    Serial.println("⚠️ PSRAM not found! Use DRAM fallback.");
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.jpeg_quality = 15;
  } else {
    Serial.println("✅ PSRAM found");
  }

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed: 0x%x\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();

  if (s) {
    s->set_brightness(s, 0);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
    s->set_gain_ctrl(s, 1);
    s->set_whitebal(s, 1);

    // Nếu ảnh bị ngược, mở thử:
    // s->set_vflip(s, 1);
    // s->set_hmirror(s, 1);
  }

  Serial.println("✅ Camera initialized");
  return true;
}

// ======================================================
// 9. WIFI INIT
// ======================================================
void initWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  WiFi.begin(ssid, password);

  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("✅ WiFi Connected");
  Serial.print("ESP32-S3 IP: ");
  Serial.println(WiFi.localIP());
}

// ======================================================
// 10. BUTTON HANDLER
// ======================================================
void handleButton() {
  bool reading = digitalRead(BUTTON_PIN);

  // Nếu trạng thái đọc thay đổi thì reset timer chống dội
  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
  }

  // Sau debounceDelay ms mà trạng thái vẫn ổn định thì xử lý
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != stableButtonState) {
      stableButtonState = reading;

      // INPUT_PULLUP: nhấn nút = LOW
      if (stableButtonState == LOW) {
        studySessionActive = !studySessionActive;

        Serial.println("================================");
        Serial.print("🔘 Button pressed -> Study mode: ");
        Serial.println(studySessionActive ? "START" : "STOP");
        Serial.println("================================");

        sendStudySessionState();
      }
    }
  }

  lastButtonReading = reading;
}

// ======================================================
// 11. SEND CAMERA FRAME
// ======================================================
void sendCameraFrame() {
  if (!cameraReady) {
    return;
  }

  if (!webSocket.isConnected()) {
    return;
  }

  unsigned long now = millis();

  if (now - prev_ms < interval) {
    return;
  }

  prev_ms = now;

  camera_fb_t *fb = esp_camera_fb_get();

  if (!fb) {
    Serial.println("❌ Camera capture failed");
    return;
  }

  bool success = webSocket.sendBIN(fb->buf, fb->len);

  if (success) {
    sent_frames++;
  } else {
    Serial.println("❌ sendBIN failed");
  }

  esp_camera_fb_return(fb);
}

// ======================================================
// 12. SETUP
// ======================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("===== ESP32-S3 CAMERA + BUTTON WEBSOCKET SENDER =====");

  // Button
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("✅ Button initialized on GPIO21");
  Serial.println("Button wiring: GPIO21 ---- button ---- GND");

  // WiFi
  initWiFi();

  // Camera
  cameraReady = initCamera();

  if (!cameraReady) {
    Serial.println("❌ Camera is not ready. ESP32-S3 will only handle button/WebSocket.");
  }

  // WebSocket
  webSocket.begin(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);

  // Optional: heartbeat để giữ kết nối ổn định hơn
  webSocket.enableHeartbeat(15000, 3000, 2);

  fps_timer = millis();
}

// ======================================================
// 13. LOOP
// ======================================================
void loop() {
  webSocket.loop();

  // Nút phải được đọc liên tục, kể cả khi WebSocket chưa kết nối
  handleButton();

  // Gửi ảnh binary lên BE
  sendCameraFrame();

  // Log FPS gửi ảnh
  if (millis() - fps_timer >= 1000) {
    Serial.printf("📤 ESP32-S3 send FPS: %u | Study mode: %s\n",
                  sent_frames,
                  studySessionActive ? "START" : "STOP");

    sent_frames = 0;
    fps_timer = millis();
  }
}