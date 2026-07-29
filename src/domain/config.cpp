#include "domain/config.h"

FunctionMap& mapFor(Config& c, Function f) { return c.map[(size_t)f]; }
const FunctionMap& mapFor(const Config& c, Function f) { return c.map[(size_t)f]; }

static FunctionMap single(uint32_t id, uint8_t bit) {
  FunctionMap m;
  m.combine = Combine::Single;
  m.bits[0] = {id, bit};
  m.count = 1;
  return m;
}

Config defaultConfig() {
  Config c;  // colors/timing use struct defaults above

  // Energica Experia map (spec section 3). Run and DayNight left unassigned
  // (count 0) until discovered; Run unassigned is treated as always-true.
  mapFor(c, Function::LeftInd)   = single(0x102, 18);
  mapFor(c, Function::RightInd)  = single(0x102, 19);
  mapFor(c, Function::FrontBrake)= single(0x102, 21);
  mapFor(c, Function::RearBrake) = single(0x102, 22);
  mapFor(c, Function::LowBeam)   = single(0x102, 7);
  mapFor(c, Function::HighBeamFlash) = single(0x102, 16);
  mapFor(c, Function::KickStand) = single(0x102, 13);

  // High beam = bit 6 AND bit 16 (spec section 3).
  FunctionMap hb;
  hb.combine = Combine::And;
  hb.bits[0] = {0x102, 6};
  hb.bits[1] = {0x102, 16};
  hb.count = 2;
  mapFor(c, Function::HighBeam) = hb;

  return c;
}
