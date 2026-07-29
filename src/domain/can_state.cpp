#include "domain/can_state.h"
#include <cstring>

const CanState::Frame* CanState::find(uint32_t id) const {
  for (const auto& f : frames_) {
    if (f.seen && f.id == id) return &f;
  }
  return nullptr;
}

void CanState::update(uint32_t id, const uint8_t data[8]) {
  for (auto& f : frames_) {                 // update existing
    if (f.seen && f.id == id) {
      std::memcpy(f.data, data, 8);
      return;
    }
  }
  for (auto& f : frames_) {                 // insert into free slot
    if (!f.seen) {
      f.seen = true;
      f.id = id;
      std::memcpy(f.data, data, 8);
      return;
    }
  }
  // table full: ignore new ids (16 distinct ids is ample for this use).
}

bool CanState::getBit(uint32_t id, uint8_t bit) const {
  const Frame* f = find(id);
  if (!f) return false;
  return (f->data[bit / 8] >> (bit % 8)) & 0x01;
}

bool CanState::evalFunction(const FunctionMap& fm) const {
  if (fm.count == 0) return false;          // unassigned
  switch (fm.combine) {
    case Combine::Single:
      return getBit(fm.bits[0].id, fm.bits[0].bit);
    case Combine::And:
      for (uint8_t i = 0; i < fm.count; ++i)
        if (!getBit(fm.bits[i].id, fm.bits[i].bit)) return false;
      return true;
    case Combine::Or:
      for (uint8_t i = 0; i < fm.count; ++i)
        if (getBit(fm.bits[i].id, fm.bits[i].bit)) return true;
      return false;
  }
  return false;
}

LogicalState CanState::evaluate(const Config& cfg) const {
  LogicalState s;
  s.leftInd    = evalFunction(mapFor(cfg, Function::LeftInd));
  s.rightInd   = evalFunction(mapFor(cfg, Function::RightInd));
  s.frontBrake = evalFunction(mapFor(cfg, Function::FrontBrake));
  s.rearBrake  = evalFunction(mapFor(cfg, Function::RearBrake));
  s.lowBeam    = evalFunction(mapFor(cfg, Function::LowBeam));
  s.highBeam   = evalFunction(mapFor(cfg, Function::HighBeam));
  s.flash      = evalFunction(mapFor(cfg, Function::HighBeamFlash));
  s.night      = evalFunction(mapFor(cfg, Function::DayNight));
  s.kickstand  = evalFunction(mapFor(cfg, Function::KickStand));

  // Run: unassigned means always-running (fail-safe, spec Open Question #1).
  const FunctionMap& runMap = mapFor(cfg, Function::Run);
  s.run = (runMap.count == 0) ? true : evalFunction(runMap);
  return s;
}
