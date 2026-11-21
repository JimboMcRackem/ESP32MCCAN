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

  // Numbers read from CAN. A value is used only when its Valid flag is set:
  // mapped, its frame fresh, and the value plausible. Invalid reads 0.
  float speedKmh = 0;
  bool  speedValid = false;
  float leanDeg = 0;        // positive = leaning right
  bool  leanValid = false;

  bool hazards() const { return leftInd && rightInd; }
  bool brake() const { return frontBrake || rearBrake; }
};
