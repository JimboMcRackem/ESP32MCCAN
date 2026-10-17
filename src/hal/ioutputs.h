#pragma once
#include <cstdint>

// The seam between the domain and whatever drives real pins. Implementations
// must ignore an out-of-range index rather than fault.
class IOutputs {
public:
  virtual ~IOutputs() = default;
  virtual void setOutput(uint8_t index, bool on) = 0;
};
