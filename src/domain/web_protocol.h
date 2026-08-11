#pragma once
#include "domain/config.h"
#include "domain/can_state.h"
#include <string>

struct ProtocolAction {
  bool        sendConfig   = false;
  bool        applyConfig  = false;
  bool        setDiscovery = false;
  bool        discoveryOut = false;
  Config      cfgOut;
  std::string error;
};

// Parse one inbound WebSocket text message into an action. Never throws.
ProtocolAction handleRequest(const std::string& json);

// Outbound message builders.
std::string configMessage(const Config& c);
std::string framesMessage(const CanFrameSnapshot* frames, int count);
std::string errorMessage(const std::string& msg);
