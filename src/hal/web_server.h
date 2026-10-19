#pragma once
#include <string>
#include <functional>
#include <cstdint>

// SoftAP + captive-portal DNS + HTTP server (embedded app, POST /update) + synchronous
// WebSocket server. Every callback runs inline on the main task during loop().
// NOTE: an HTTP request is handled to completion inside loop(). During an update
// upload the lighting tick runs between chunks via onUploadTick(); uploads are
// also gated on the bike being parked.
class WebServerHal {
public:
  using MessageCb = std::function<void(uint8_t clientId, const std::string& text)>;
  using DisconnectCb = std::function<void(uint8_t clientId)>;

  bool begin(const char* ssid, const char* password);
  // Re-applies the SoftAP config with a new password. The IP config, DNS, HTTP
  // and WebSocket servers keep running; connected stations are dropped and must
  // rejoin with the new password.
  void restartAp(const char* ssid, const char* password);
  // POST /update?reset=0|1 (multipart, field "update"). `parked` gates the start
  // of an upload; `committed` runs after a verified image is set to boot and the
  // 200 reply is sent. It must not restart: the reply has to flush first.
  // GET /update/ready answers 200 {"ok":true} when parked() holds, else
  // 409 {"ok":false,"error":<not-parked text>}.
  void onUpdate(std::function<bool()> parked,
                std::function<void(bool resetSettings)> committed);
  // Called after every upload chunk, so the lighting tick keeps running while
  // an upload holds the main task. It must not touch the HTTP or WS servers.
  void onUploadTick(std::function<void()> tick);
  void loop();                                  // call every main-loop iteration
  void onMessage(MessageCb cb);
  // Fires when a WebSocket client goes away. Test mode uses this so a phone
  // that walks out of range cannot leave the lights latched.
  void onDisconnect(DisconnectCb cb);
  void sendTo(uint8_t clientId, const std::string& text);
  void broadcast(const std::string& text);
};
