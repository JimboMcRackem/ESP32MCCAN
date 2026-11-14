#pragma once
#include "hal/ioutputs.h"

// One GPIO per output, indexed in OutputIndex order. The pin table is passed in
// rather than baked in, so this class has no dependency on the domain enum and
// the board plan can change the pinout without touching the HAL.
class GpioOutputs : public IOutputs {
public:
  GpioOutputs(const uint8_t* pins, uint8_t count);
  // Sets every pin to OUTPUT and drives it LOW. Call before anything else.
  bool begin();
  void setOutput(uint8_t index, bool on) override;
private:
  const uint8_t* pins_;
  uint8_t        count_;
};
