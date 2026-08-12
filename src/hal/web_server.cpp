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

// Serve the app's index.html (captive-portal landing). If the LittleFS image
// was never flashed, send a plain diagnostic instead of an endless redirect.
static void serveApp() {
  if (LittleFS.exists("/index.html")) {
    File f = LittleFS.open("/index.html", "r");
    s_http.streamFile(f, "text/html");
    f.close();
    return;
  }
  String msg = "MCCAN: web filesystem not loaded.\n";
  msg += "Run: py -3.13 -m platformio run -e esp32 -t uploadfs\n";
  msg += "LittleFS used=";
  msg += (unsigned long)LittleFS.usedBytes();
  msg += " total=";
  msg += (unsigned long)LittleFS.totalBytes();
  msg += "\nindex.html=";
  msg += LittleFS.exists("/index.html") ? "yes" : "no";
  msg += " app.js=";
  msg += LittleFS.exists("/app.js") ? "yes" : "no";
  s_http.send(200, "text/plain", msg);
}

bool WebServerHal::begin(const char* ssid, const char* password) {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(s_apIP, s_apIP, IPAddress(255, 255, 255, 0));
  bool ap = WiFi.softAP(ssid, password);

  // Boot diagnostic: what does LittleFS actually contain at runtime?
  Serial.printf("[web] LittleFS total=%u used=%u index.html=%s app.js=%s style.css=%s\n",
                (unsigned)LittleFS.totalBytes(), (unsigned)LittleFS.usedBytes(),
                LittleFS.exists("/index.html") ? "yes" : "no",
                LittleFS.exists("/app.js") ? "yes" : "no",
                LittleFS.exists("/style.css") ? "yes" : "no");

  // Captive portal: resolve every hostname to us.
  s_dns.start(53, "*", s_apIP);

  // Serve the SPA from LittleFS. serveStatic infers content types from extensions.
  s_http.serveStatic("/app.js", LittleFS, "/app.js");
  s_http.serveStatic("/style.css", LittleFS, "/style.css");
  // Root and every unknown path (OS captive-portal probes) -> serve the app
  // (or a diagnostic if the FS is missing). No redirect => no redirect loop.
  s_http.on("/", serveApp);
  s_http.on("/index.html", serveApp);
  s_http.onNotFound(serveApp);
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
