#pragma once
#include <stddef.h>
#include <stdint.h>
#include "domain/sha256.h"

// Streaming receiver for the signed .mcup update file. Platform-free.
enum class UpdateError { None, Truncated, BadMagic, BadFormat, BadLength,
                         Downgrade, TooLarge, ExtraBytes, BadSignature, WriteFailed };

const char* updateErrorText(UpdateError e);

// Shown when an update is attempted while the bike is not parked.
extern const char* const kNotParkedText;

struct UpdateHeader {
  uint32_t build;
  uint32_t imageLen;
  char display[32];
};

class IUpdateSink {
 public:
  virtual ~IUpdateSink() = default;
  virtual bool begin(uint32_t imageLen) = 0;
  virtual bool write(const uint8_t* d, size_t n) = 0;
};

class UpdateReceiver {
 public:
  UpdateReceiver(uint32_t runningBuild, uint32_t slotBytes,
                 const uint8_t* pubKey64, IUpdateSink& sink);
  bool feed(const uint8_t* data, size_t len);  // false once errored; never writes after an error
  UpdateError finish();                        // verdict once the upload has ended
  UpdateError error() const { return err_; }
  const UpdateHeader* header() const { return headerOk_ ? &hdr_ : nullptr; }

 private:
  bool fail(UpdateError e);
  bool parseHeader();

  uint32_t runningBuild_;
  uint32_t slotBytes_;
  const uint8_t* pub_;
  IUpdateSink& sink_;
  UpdateError err_;
  bool headerOk_;
  UpdateHeader hdr_;
  uint8_t head_[64];
  size_t headLen_;
  uint32_t imageGot_;
  uint8_t sig_[64];
  size_t sigLen_;
  Sha256 sha_;
  bool finished_;
};

bool parkedForUpdate(bool canStale, bool kickstandDown);  // true if either
