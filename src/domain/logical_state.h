#pragma once

struct LogicalState {
  bool run = false;
  bool leftInd = false;
  bool rightInd = false;
  bool frontBrake = false;
  bool rearBrake = false;
  bool lowBeam = false;
  bool highBeam = false;
  bool flash = false;       // momentary high-beam flash/pass button
  bool night = false;       // day/night mode: true = night
  bool kickstand = false;

  bool hazards() const { return leftInd && rightInd; }
  bool brake() const { return frontBrake || rearBrake; }
};
