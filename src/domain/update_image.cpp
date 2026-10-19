#include "domain/update_image.h"
#include <string.h>
#include "domain/signature.h"

const char* const kNotParkedText = "Park the bike first: kickstand down or ignition off.";

const char* updateErrorText(UpdateError e) {
  switch (e) {
    case UpdateError::Truncated:    return "The upload was cut short. Nothing was changed.";
    case UpdateError::BadMagic:     return "That is not an MCCAN update file (.mcup).";
    case UpdateError::BadFormat:    return "This update file needs newer firmware to install.";
    case UpdateError::BadLength:    return "The update file is damaged.";
    case UpdateError::Downgrade:    return "This update is older than the installed firmware.";
    case UpdateError::TooLarge:     return "This update is too large for this controller.";
    case UpdateError::ExtraBytes:   return "The update file is damaged.";
    case UpdateError::BadSignature: return "This update is not signed by MCCAN. Nothing was changed.";
    case UpdateError::WriteFailed:  return "Writing the update failed. Nothing was changed.";
    case UpdateError::None:         break;
  }
  return "";
}

bool parkedForUpdate(bool canStale, bool kickstandDown) { return canStale || kickstandDown; }

UpdateReceiver::UpdateReceiver(uint32_t runningBuild, uint32_t slotBytes,
                               const uint8_t* pubKey64, IUpdateSink& sink)
    : runningBuild_(runningBuild), slotBytes_(slotBytes), pub_(pubKey64), sink_(sink),
      err_(UpdateError::None), headerOk_(false), hdr_{}, head_{}, headLen_(0),
      imageGot_(0), sig_{}, sigLen_(0) {}

bool UpdateReceiver::fail(UpdateError e) {
  if (err_ == UpdateError::None) err_ = e;
  return false;
}

static uint32_t le32(const uint8_t* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

bool UpdateReceiver::parseHeader() {
  if (memcmp(head_, "MCUP", 4) != 0) return fail(UpdateError::BadMagic);
  uint16_t ver = (uint16_t)(head_[4] | (head_[5] << 8));
  if (ver != 1) return fail(UpdateError::BadFormat);
  uint32_t len = le32(head_ + 12);
  if (len == 0) return fail(UpdateError::BadLength);
  if (memchr(head_ + 16, 0, 32) == nullptr) return fail(UpdateError::BadLength);
  hdr_.build = le32(head_ + 8);
  hdr_.imageLen = len;
  memcpy(hdr_.display, head_ + 16, 32);
  if (hdr_.build < runningBuild_) return fail(UpdateError::Downgrade);
  if (len > slotBytes_) return fail(UpdateError::TooLarge);
  if (!sink_.begin(len)) return fail(UpdateError::WriteFailed);
  sha_.update(head_, 64);
  headerOk_ = true;
  return true;
}

bool UpdateReceiver::feed(const uint8_t* data, size_t len) {
  if (err_ != UpdateError::None) return false;
  while (len > 0) {
    if (headLen_ < 64) {
      size_t n = 64 - headLen_;
      if (n > len) n = len;
      memcpy(head_ + headLen_, data, n);
      headLen_ += n; data += n; len -= n;
      if (headLen_ == 64 && !parseHeader()) return false;
    } else if (imageGot_ < hdr_.imageLen) {
      size_t n = hdr_.imageLen - imageGot_;
      if (n > len) n = len;
      if (!sink_.write(data, n)) return fail(UpdateError::WriteFailed);
      sha_.update(data, n);
      imageGot_ += (uint32_t)n; data += n; len -= n;
    } else if (sigLen_ < 64) {
      size_t n = 64 - sigLen_;
      if (n > len) n = len;
      memcpy(sig_ + sigLen_, data, n);
      sigLen_ += n; data += n; len -= n;
    } else {
      return fail(UpdateError::ExtraBytes);
    }
  }
  return true;
}

UpdateError UpdateReceiver::finish() {
  if (err_ != UpdateError::None) return err_;
  if (!headerOk_ || imageGot_ < hdr_.imageLen || sigLen_ < 64) {
    fail(UpdateError::Truncated);
    return err_;
  }
  uint8_t digest[32];
  sha_.finish(digest);
  if (!verifyP256(pub_, digest, sig_)) {
    fail(UpdateError::BadSignature);
    return err_;
  }
  return UpdateError::None;
}
