#pragma once
#include <stdint.h>

// ECDSA P-256 verify. pub is raw X||Y, sig is raw r||s (big-endian), digest is SHA-256.
// An all-zero public key never verifies.
bool verifyP256(const uint8_t pub[64], const uint8_t digest[32], const uint8_t sig[64]);
