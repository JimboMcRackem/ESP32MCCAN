#pragma once
#include <string>
#include <functional>
#include <cstdint>

// SoftAP + captive-portal DNS + HTTP static file server (LittleFS) + synchronous
// WebSocket server. The WS event callback runs inline on the main task during loop().
class WebServerHal {
public:
  using MessageCb = std::function<void(uint8_t clientId, const std::string& text)>;
  using DisconnectCb = std::function<void(uint8_t clientId)>;

  bool begin(const char* ssid, const char* password);
  void loop();                                  // call every main-loop iteration
  void onMessage(MessageCb cb);
  // Fires when a WebSocket client goes away. Test mode uses this so a phone
  // that walks out of range cannot leave the lights latched.
  void onDisconnect(DisconnectCb cb);
  void sendTo(uint8_t clientId, const std::string& text);
  void broadcast(const std::string& text);
};
