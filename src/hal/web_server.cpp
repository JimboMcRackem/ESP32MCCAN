#include "hal/web_server.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <WebSocketsServer.h>
#include <LittleFS.h>

static WebServer         s_http(80);
static DNSServer         s_dns;
static WebSocketsServer  s_ws(81);
static IPAddress         s_apIP(192, 168, 4, 1);
static WebServerHal::MessageCb s_cb;

static void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_TEXT && s_cb) {
    s_cb(num, std::string(reinterpret_cast<char*>(payload), length));
  }
}

bool WebServerHal::begin(const char* ssid, const char* password) {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(s_apIP, s_apIP, IPAddress(255, 255, 255, 0));
  bool ap = WiFi.softAP(ssid, password);

  // Captive portal: resolve every hostname to us.
  s_dns.start(53, "*", s_apIP);

  // Serve the SPA from LittleFS. serveStatic infers content types from extensions.
  s_http.serveStatic("/", LittleFS, "/index.html");
  s_http.serveStatic("/index.html", LittleFS, "/index.html");
  s_http.serveStatic("/app.js", LittleFS, "/app.js");
  s_http.serveStatic("/style.css", LittleFS, "/style.css");
  // Any other path (OS captive-portal probes) -> redirect to the app root.
  s_http.onNotFound([]() {
    s_http.sendHeader("Location", "http://192.168.4.1/", true);
    s_http.send(302, "text/plain", "");
  });
  s_http.begin();

  s_ws.begin();
  s_ws.onEvent(onWsEvent);
  return ap;
}

void WebServerHal::loop() {
  s_dns.processNextRequest();
  s_http.handleClient();
  s_ws.loop();
}

void WebServerHal::onMessage(MessageCb cb) { s_cb = cb; }

void WebServerHal::sendTo(uint8_t clientId, const std::string& text) {
  s_ws.sendTXT(clientId, text.c_str(), text.length());
}

void WebServerHal::broadcast(const std::string& text) {
  s_ws.broadcastTXT(text.c_str(), text.length());
}
