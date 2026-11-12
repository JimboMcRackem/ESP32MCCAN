#include "domain/signature.h"

#include <uECC.h>

bool verifyP256(const uint8_t pub[64], const uint8_t digest[32], const uint8_t sig[64]) {
  uint8_t any = 0;
  for (int i = 0; i < 64; i++) any |= pub[i];
  if (any == 0) return false;
  return uECC_verify(pub, digest, 32, sig, uECC_secp256r1()) == 1;
}
