#include "hal/web_server.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <WebSocketsServer.h>
#include <Update.h>
#include <esp_ota_ops.h>
#include <ArduinoJson.h>
#include <memory>
#include "domain/update_image.h"
#include "domain/update_pubkey.h"
#include "version.h"

static WebServer         s_http(80);
static DNSServer         s_dns;
static WebSocketsServer  s_ws(81);
static IPAddress         s_apIP(192, 168, 4, 1);
static WebServerHal::MessageCb s_cb;
static WebServerHal::DisconnectCb s_disc;
static std::function<bool()>      s_parked;
static std::function<void(bool)>  s_committed;

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

// ---------------------------------------------------------------------------
// POST /update: signed .mcup upload into the next OTA slot.
//
// The receiver checks the header before the first flash write and the
// signature before anything is committed; only a verified image ever reaches
// Update.end(true), which is what switches the boot partition. Every other
// path ends in Update.abort(), which leaves the running image and the boot
// partition untouched.

// Streams image bytes into the next OTA slot through the Arduino Update class.
class EspUpdateSink : public IUpdateSink {
 public:
  bool begin(uint32_t imageLen) override {
    begun_ = true;   // set first: a failed begin still gets an abort() to clear it
    return Update.begin(imageLen, U_FLASH);
  }
  bool write(const uint8_t* d, size_t n) override {
    // Update.write copies from `d` and never modifies it; the API is just not const.
    return Update.write(const_cast<uint8_t*>(d), n) == n;
  }
  bool begun() const { return begun_; }

 private:
  bool begun_ = false;
};

// One upload in flight. `rx` is declared after `sink` so it is destroyed first
// (it holds a reference to the sink).
struct UploadState {
  bool reset = false;              // ?reset=1: wipe settings on the next boot
  bool inPart = false;             // the current multipart part is ours
  const char* refusal = nullptr;   // fixed text when refused without a receiver
  EspUpdateSink sink;
  std::unique_ptr<UpdateReceiver> rx;
};
static std::unique_ptr<UploadState> s_up;

// Set once an image is committed. Until the restart, the next OTA slot IS that
// image, so a second upload would overwrite the partition we are about to boot.
static bool s_installed = false;
static const char* const kAlreadyInstalledText =
    "An update is already installed. Restart the controller first.";

// Abandon any upload in flight. Safe to call at any time.
static void discardUpload() {
  if (s_up && s_up->sink.begun()) Update.abort();
  s_up.reset();
}

static void replyUpdate(const char* error) {
  if (!error) {
    s_http.send(200, "application/json", "{\"ok\":true}");
    return;
  }
  JsonDocument doc;
  doc["ok"] = false;
  doc["error"] = error;
  String body;
  serializeJson(doc, body);
  s_http.send(400, "application/json", body);
}

static void onUpdateChunk() {
  HTTPUpload& up = s_http.upload();
  switch (up.status) {
    case UPLOAD_FILE_START: {
      // Parked is checked first, before anything else is decided.
      if (!s_parked || !s_parked()) {
        // Refuse now and hang up rather than read the rest of the file: the
        // lighting tick cannot run while this request is being read, and the
        // bike is not parked. The client may see the 400 or a reset connection.
        Serial.println("update: refused, not parked");
        discardUpload();
        replyUpdate(kNotParkedText);
        s_http.client().stop();          // the server then reports UPLOAD_FILE_ABORTED
        return;
      }
      // A request carries one file part, "update". Any further part starts
      // over, so the last part decides; a part with another name is refused.
      discardUpload();
      s_up.reset(new UploadState());
      s_up->inPart = true;
      s_up->reset = (s_http.arg("reset") == "1");
      if (up.name != "update") {
        s_up->refusal = updateErrorText(UpdateError::BadMagic);
        return;
      }
      if (s_installed) {
        s_up->refusal = kAlreadyInstalledText;
        return;
      }
      const esp_partition_t* slot = esp_ota_get_next_update_partition(nullptr);
      if (!slot) {
        s_up->refusal = updateErrorText(UpdateError::WriteFailed);
        Serial.println("update: refused, no OTA slot");
        return;
      }
      s_up->rx.reset(new UpdateReceiver(kBuildNumber, slot->size, kUpdatePubKey, s_up->sink));
      Serial.printf("update: receiving into %s (%u bytes)\n", slot->label, (unsigned)slot->size);
      return;
    }
    case UPLOAD_FILE_WRITE:
      if (s_up && s_up->inPart && s_up->rx && up.currentSize > 0)
        s_up->rx->feed(up.buf, up.currentSize);   // after an error this is a no-op
      return;
    case UPLOAD_FILE_END:
      if (s_up && s_up->inPart) {
        s_up->inPart = false;
        if (s_up->rx) s_up->rx->finish();          // verdict, including the signature
      }
      return;
    case UPLOAD_FILE_ABORTED:
      // The client went away mid-upload. No reply: there is nobody to read it.
      if (s_up) Serial.println("update: upload aborted by client");
      discardUpload();
      return;
  }
}

static void onUpdateDone() {
  if (!s_up) {
    // No "update" file part arrived (or the request was already answered).
    replyUpdate(updateErrorText(UpdateError::Truncated));
    return;
  }
  const bool reset = s_up->reset;
  const char* error = s_up->refusal;
  if (!error) {
    UpdateError e = s_up->rx ? s_up->rx->finish() : UpdateError::Truncated;  // idempotent
    if (e != UpdateError::None) {
      error = updateErrorText(e);
    } else if (!Update.end(true)) {
      error = updateErrorText(UpdateError::WriteFailed);
    }
  }

  if (error) {
    Serial.printf("update: failed: %s\n", error);
    discardUpload();                 // Update.abort(): boot partition unchanged
    replyUpdate(error);
    return;
  }

  Serial.println("update: verified and set to boot");
  s_installed = true;
  s_up.reset();                      // Update already finished; nothing to abort
  replyUpdate(nullptr);
  if (s_committed) s_committed(reset);
}

bool WebServerHal::begin(const char* ssid, const char* password) {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(s_apIP, s_apIP, IPAddress(255, 255, 255, 0));
  bool ap = WiFi.softAP(ssid, password);

  // Captive portal: resolve every hostname to us.
  s_dns.start(53, "*", s_apIP);

  // Embedded SPA; the not-found handler serves the app for captive-portal probes.
  s_http.on("/update", HTTP_POST, onUpdateDone, onUpdateChunk);
  s_http.onNotFound(serveAsset);
  s_http.begin();

  s_ws.begin();
  s_ws.onEvent(onWsEvent);
  return ap;
}

void WebServerHal::restartAp(const char* ssid, const char* password) {
  // softAP() on a running AP re-applies the config (stations are dropped). The
  // netif keeps the IP config set in begin(); DNS, HTTP and WS keep running.
  bool ok = WiFi.softAP(ssid, password);
  Serial.println(ok ? "AP restarted with the new password" : "AP restart FAILED");
}

void WebServerHal::onUpdate(std::function<bool()> parked,
                            std::function<void(bool resetSettings)> committed) {
  s_parked = parked;
  s_committed = committed;
}

void WebServerHal::loop() {
  s_dns.processNextRequest();
  s_http.handleClient();
  // A request is read and answered inside one handleClient() call, so upload
  // state still here belongs to a request the server dropped part-way (a
  // parse failure with no ABORTED callback). Never let it reach a later request.
  if (s_up) {
    Serial.println("update: dropped request, upload discarded");
    discardUpload();
  }
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
