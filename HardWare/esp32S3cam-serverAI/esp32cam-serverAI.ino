#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsClient.h>

// --- Pin mapping AI-Thinker ---
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

const char* ssid = "Room Room";
const char* password = "khongcopass";
const char* ws_host = "192.168.2.101";
const int ws_port = 8000;

WebSocketsClient webSocket;

unsigned long prev_ms = 0;
const uint16_t interval = 90;   // 100 ms = 10 FPS mục tiêu

unsigned long fps_timer = 0;
uint16_t sent_frames = 0;

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket disconnected");
      break;
    case WStype_CONNECTED:
      Serial.println("✅ WebSocket connected");
      Serial.printf("URL: %s\n", payload);
      break;
    case WStype_TEXT:
      // Nếu sau này BE gửi lệnh xuống CAM thì xử lý ở đây
      break;
    case WStype_BIN:
      break;
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

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
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

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

  // Tối ưu cho realtime object detection
  config.frame_size = FRAMESIZE_QVGA;   // 320x240
  config.jpeg_quality = psramFound() ? 12 : 15;  // nhỏ hơn -> nét hơn, lớn hơn -> nhẹ hơn
  config.fb_count = psramFound() ? 2 : 1;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed: 0x%x\n", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 0);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
    // Có thể bật thêm nếu ảnh bị tối/nhiễu:
    // s->set_gain_ctrl(s, 1);
    // s->set_whitebal(s, 1);
  }

  webSocket.begin(ws_host, ws_port, "/api/v1/ws/detect");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);

  fps_timer = millis();
}

void loop() {
  webSocket.loop();

  if (!webSocket.isConnected()) {
    delay(10);
    return;
  }

  unsigned long now = millis();
  if (now - prev_ms >= interval) {
    prev_ms = now;

    camera_fb_t * fb = esp_camera_fb_get();
    if (fb) {
      bool success = webSocket.sendBIN(fb->buf, fb->len);
      if (success) {
        sent_frames++;
      }
      esp_camera_fb_return(fb);
    }
  }

  // In FPS gửi mỗi 1 giây, tránh spam Serial
  if (millis() - fps_timer >= 1000) {
    Serial.printf("📤 ESP32 send FPS: %u\n", sent_frames);
    sent_frames = 0;
    fps_timer = millis();
  }
}