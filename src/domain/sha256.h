#pragma once
#include <stddef.h>
#include <stdint.h>

// FIPS 180-4 SHA-256. Portable, no platform headers.
class Sha256 {
 public:
  Sha256();
  void update(const uint8_t* d, size_t n);
  void finish(uint8_t out[32]);

 private:
  void block(const uint8_t* p);
  uint32_t h_[8];
  uint8_t buf_[64];
  size_t bufLen_;
  uint64_t total_;
};
