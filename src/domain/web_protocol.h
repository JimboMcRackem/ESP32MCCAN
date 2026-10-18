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

// Wire-name asymmetry, deliberate and load-bearing: an INBOUND test request
// names its mode in "mode" (read at web_protocol.cpp:47), while the OUTBOUND
// test_state names the same concept in "kind" (written at :131). Both sides
// are in step with the app today; renaming either is a wire break for no
// functional gain, so leave them. Separately, "zones" (the key),
// TestKind::Zones and TestMode::zones all now mean one 12-bit output mask --
// the name predates the per-corner colour triples it used to carry.

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
