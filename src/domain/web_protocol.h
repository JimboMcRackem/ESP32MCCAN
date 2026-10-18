#pragma once
#include "domain/config.h"
#include "domain/can_state.h"
#include "domain/test_mode.h"
#include <cstdint>
#include <string>

// Bumped whenever a message shape changes incompatibly. The app and the
// LittleFS image are separate flashes and can diverge; the app compares this
// and refuses rather than half-working. Version 1 did not send the field, so
// a missing value reads as 1. Version 3 removed the colour and denali blocks
// entirely and changed `zones` from four per-corner colour triples to a
// single 12-bit output mask.
constexpr int kProtocolVersion = 3;

struct ProtocolAction {
  bool        sendConfig   = false;
  bool        applyConfig  = false;
  bool        setDiscovery = false;
  bool        discoveryOut = false;
  bool        setTest      = false;
  Config      cfgOut;
  TestMode    testOut;
  std::string error;
};

// Parse one inbound WebSocket text message into an action. Never throws.
ProtocolAction handleRequest(const std::string& json);

// Outbound message builders.
std::string configMessage(const Config& c);
std::string framesMessage(const CanFrameSnapshot* frames, int count);
std::string errorMessage(const std::string& msg);
std::string testStateMessage(const TestMode& t, const Config& cfg, uint32_t nowMs);
