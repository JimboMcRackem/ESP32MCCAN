#pragma once
#include <cstdint>

class CanBus {
public:
  // rxPin/txPin are the transceiver GPIOs; set in main.cpp (PCB-defined).
  bool begin(int rxPin, int txPin, uint32_t bitrateBps);
  bool receive(uint32_t& id, uint8_t data[8]);   // non-blocking
};
