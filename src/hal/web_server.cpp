#include "hal/web_server.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <WebSocketsServer.h>

static WebServer         s_http(80);
static DNSServer         s_dns;
static WebSocketsServer  s_ws(81);
static IPAddress         s_apIP(192, 168, 4, 1);
static WebServerHal::MessageCb s_cb;
static WebServerHal::DisconnectCb s_disc;

static void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_TEXT && s_cb) {
    s_cb(num, std::string(reinterpret_cast<char*>(payload), length));
  } else if (type == WStype_DISCONNECTED && s_disc) {
    s_disc(num);
  }
}

#include "hal/web_assets.h"

static const WebAsset* findAsset(const char* path) {
  for (const WebAsset& a : kWebAssets) {
    if (strcmp(a.path, path) == 0) return &a;
  }
  return nullptr;
}

// Serve an embedded asset (gzip, from flash). "/" and every unknown path
// (OS captive-portal probes) get /index.html with 200: no redirect, no loop.
static void serveAsset() {
  String uri = s_http.uri();
  const WebAsset* a = (uri == "/") ? nullptr : findAsset(uri.c_str());
  if (!a) a = findAsset("/index.html");
  if (!a) {
    s_http.send(500, "text/plain", "MCCAN: web assets missing");
    return;
  }
  s_http.sendHeader("Content-Encoding", "gzip");
  s_http.sendHeader("Cache-Control", "no-cache");
  s_http.send_P(200, a->mime, reinterpret_cast<const char*>(a->gz), a->len);
}

bool WebServerHal::begin(const char* ssid, const char* password) {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(s_apIP, s_apIP, IPAddress(255, 255, 255, 0));
  bool ap = WiFi.softAP(ssid, password);

  // Captive portal: resolve every hostname to us.
  s_dns.start(53, "*", s_apIP);

  // Embedded SPA; the not-found handler serves the app for captive-portal probes.
  s_http.onNotFound(serveAsset);
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

void WebServerHal::onDisconnect(DisconnectCb cb) { s_disc = cb; }

void WebServerHal::sendTo(uint8_t clientId, const std::string& text) {
  s_ws.sendTXT(clientId, text.c_str(), text.length());
}

void WebServerHal::broadcast(const std::string& text) {
  s_ws.broadcastTXT(text.c_str(), text.length());
}
