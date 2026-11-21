#pragma once
#include "domain/config.h"
#include <cstdint>

// Reads a NumSignal's raw value out of an 8-byte payload.
//
// Bit n is byte n/8, bit n%8, LSB = 0 -- the same numbering as BitRef.
// - Intel (bigEndian false): startBit is the value's LSB; value bit i is
//   payload bit startBit + i.
// - Motorola (bigEndian true), DBC convention: startBit is the value's MSB.
//   The walk goes b -> b - 1 within a byte, and from bit 0 of byte k to bit 7
//   of byte k+1 (b -> b + 15). The first bit walked is the value's MSB.
// Signed values are two's complement at `length` bits.
//
// False when the signal is unmapped (length 0 or over 32) or any bit falls
// outside the 64-bit payload.
bool decodeRaw(const uint8_t data[8], const NumSignal& sig, int64_t& rawOut);

// decodeRaw, then raw * scale + offset.
bool decodeSignal(const uint8_t data[8], const NumSignal& sig, float& valueOut);
