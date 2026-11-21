#include "domain/can_signal.h"

static bool bitAt(const uint8_t data[8], int b) {
  return ((data[b / 8] >> (b % 8)) & 1u) != 0u;
}

bool decodeRaw(const uint8_t data[8], const NumSignal& sig, int64_t& rawOut) {
  if (!sig.mapped() || sig.startBit >= 64) return false;
  const int len = sig.length;
  uint64_t u = 0;

  if (!sig.bigEndian) {
    if (sig.startBit + len > 64) return false;
    for (int i = 0; i < len; ++i)
      if (bitAt(data, sig.startBit + i)) u |= (uint64_t)1 << i;
  } else {
    int b = sig.startBit;
    for (int i = len - 1; i >= 0; --i) {      // MSB first
      if (b < 0 || b >= 64) return false;
      if (bitAt(data, b)) u |= (uint64_t)1 << i;
      b = (b % 8 == 0) ? b + 15 : b - 1;
    }
  }

  if (sig.isSigned && ((u >> (len - 1)) & 1u))
    u |= ~(uint64_t)0 << len;                 // sign-extend; len <= 32 so the shift is defined
  rawOut = (int64_t)u;
  return true;
}

bool decodeSignal(const uint8_t data[8], const NumSignal& sig, float& valueOut) {
  int64_t raw = 0;
  if (!decodeRaw(data, sig, raw)) return false;
  valueOut = (float)raw * sig.scale + sig.offset;
  return true;
}
