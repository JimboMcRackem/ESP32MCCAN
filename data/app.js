"use strict";

// Function keys must match config_json.cpp kFuncNames order/spelling.
const FUNCS = ["run","leftInd","rightInd","frontBrake","rearBrake",
               "lowBeam","highBeam","highBeamFlash","dayNight","kickStand"];
const COMBINE = { 0: "Single", 1: "And", 2: "Or" };
const MAX_BITS = 4;    // must match FunctionMap::MAX_BITS in config.h
const PROTOCOL_VERSION = 3;   // must match kProtocolVersion in web_protocol.h
// Must match kScenarioNames in test_mode.cpp — the firmware table is
// authoritative and rejects anything it does not know.
const SCENARIOS = ["allOff","drlDay","leftInd","rightInd",
                   "hazards","brake","lowBeam","highBeam"];
// Must match OutputIndex in src/domain/outputs.h, in order. The firmware's
// enum is authoritative; this mirrors it only for labels.
const OUTPUT_NAMES = [
  "Front L - DRL",  "Front L - indicator",
  "Front R - DRL",  "Front R - indicator",
  "Rear L - DRL",   "Rear L - indicator", "Rear L - brake",
  "Rear R - DRL",   "Rear R - indicator", "Rear R - brake",
  "Aux pod L",      "Aux pod R",
];

let cfg = null;         // last config from device
let ws = null;
let testState = { active: false, kind: "off", remainingMs: 0 };
let activeScenario = null;
let testMask = 0;

function setStatus(connected) {
  const el = document.getElementById("status");
  el.textContent = connected ? "connected" : "disconnected";
  el.className = "status " + (connected ? "on" : "off");
}

function connect() {
  ws = new WebSocket("ws://" + location.hostname + ":81/");
  ws.onopen = () => { setStatus(true); send({ type: "get_config" }); };
  ws.onclose = () => { setStatus(false); setTimeout(connect, 1500); };
  ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function onMessage(msg) {
  if (msg.type === "config") { checkVersion(msg.protocolVersion); cfg = msg.config; render(); }
  else if (msg.type === "frames") { renderFrames(msg.frames); }
  else if (msg.type === "test_state") {
    testState = msg;
    testMask = msg.zones | 0;
    // The firmware is the source of truth for which mode is active. If a
    // second client (or this one, via the checkboxes) switched to zones or
    // off, the scenario highlight here must not keep lying about it.
    if (msg.kind !== "scenario") { activeScenario = null; renderScenarios(); }
    renderTestBanner();
    renderTestOutputs();
  }
  else if (msg.type === "error") { alert("Device error: " + msg.message); }
  // Anything else is ignored on purpose: a newer firmware broadcasting a
  // message this app does not know must be inert, not fatal.
}

function checkVersion(v) {
  v = (v === undefined) ? 1 : v;    // v1 firmware did not send the field
  const el = document.getElementById("versionBanner");
  if (v === PROTOCOL_VERSION) { el.hidden = true; return; }
  el.textContent = v < PROTOCOL_VERSION
    ? "Firmware is older than this web app (device v" + v + ", app v" + PROTOCOL_VERSION +
      "). Reflash the firmware: py -3.13 -m platformio run -e esp32 -t upload"
    : "This web app is older than the firmware (device v" + v + ", app v" + PROTOCOL_VERSION +
      "). Reflash the web files: py -3.13 -m platformio run -e esp32 -t uploadfs";
  el.hidden = false;
}

// ---- rendering ----
function render() {
  document.getElementById("blinkPeriodMs").value = cfg.blinkPeriodMs;
  document.getElementById("spotHoldMs").value = cfg.spotHoldMs;
  document.getElementById("testMaxMs").value = cfg.testMaxMs;
  document.getElementById("flashSource").value = cfg.flashSource || "auto";
  renderScenarios();
  renderTestOutputs();
  renderMaps();
  renderDiscFuncOptions();
}

function renderTestBanner() {
  const el = document.getElementById("testBanner");
  el.hidden = !testState.active;
  // activeScenario is cleared by onMessage whenever the device reports a
  // non-scenario kind (which includes "off"), so this only has to render.
  if (!testState.active) return;
  const s = Math.max(0, Math.round(testState.remainingMs / 1000));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  document.getElementById("testBannerText").textContent =
    "TEST MODE — lights overridden, CAN input ignored · " +
    testState.kind + " · auto-exit in " + mm + ":" + ss;
}

// The device broadcasts test_state once a second; tick locally between
// broadcasts so the countdown does not look stalled.
setInterval(() => {
  if (!testState.active) return;
  testState.remainingMs = Math.max(0, testState.remainingMs - 1000);
  renderTestBanner();
}, 1000);

function exitTest() { send({ type: "test", mode: "off" }); }

function renderScenarios() {
  const host = document.getElementById("scenarios");
  host.innerHTML = "";
  SCENARIOS.forEach((name) => {
    const b = document.createElement("button");
    b.textContent = name;
    if (name === activeScenario) b.classList.add("active");
    b.onclick = () => {
      activeScenario = name;
      send({ type: "test", mode: "scenario", scenario: name });
      renderScenarios();
    };
    host.appendChild(b);
  });
}

function renderTestOutputs() {
  const host = document.getElementById("testOutputs");
  host.innerHTML = "";
  OUTPUT_NAMES.forEach((name, i) => {
    const lab = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = (testMask & (1 << i)) !== 0;
    box.onchange = () => {
      if (box.checked) testMask |= (1 << i);
      else             testMask &= ~(1 << i);
      activeScenario = null;      // a checkbox edit leaves scenario mode
      renderScenarios();
      send({ type: "test", mode: "zones", zones: testMask });
    };
    lab.appendChild(box);
    lab.appendChild(document.createTextNode(" " + name));
    host.appendChild(lab);
  });
}

function renderMaps() {
  const host = document.getElementById("maps");
  host.innerHTML = "";
  FUNCS.forEach((fn) => {
    const m = cfg.maps[fn] || { combine: 0, bits: [] };
    cfg.maps[fn] = m;
    const box = document.createElement("div");
    box.className = "mapfn";
    const h = document.createElement("h3"); h.textContent = fn; box.appendChild(h);

    const sel = document.createElement("select");
    Object.entries(COMBINE).forEach(([v, t]) => {
      const o = document.createElement("option"); o.value = v; o.textContent = t;
      if (Number(v) === m.combine) o.selected = true; sel.appendChild(o);
    });
    sel.onchange = () => { m.combine = Number(sel.value); };
    box.appendChild(sel);

    (m.bits || []).forEach((b, i) => {
      const row = document.createElement("div"); row.className = "row";
      const label = document.createElement("span");
      label.textContent = "0x" + b.id.toString(16) + " bit " + b.bit;
      const del = document.createElement("button");
      del.textContent = "remove";
      del.onclick = () => { m.bits.splice(i, 1); renderMaps(); };
      row.appendChild(label); row.appendChild(del); box.appendChild(row);
    });
    host.appendChild(box);
  });
}

function renderDiscFuncOptions() {
  const sel = document.getElementById("discFunc");
  const prev = sel.value;
  sel.innerHTML = "";
  FUNCS.forEach((fn) => {
    const o = document.createElement("option"); o.value = fn; o.textContent = fn;
    sel.appendChild(o);
  });
  if (prev) sel.value = prev;
}

function renderFrames(frames) {
  const host = document.getElementById("frames");
  host.innerHTML = "";
  frames.sort((a, b) => a.id - b.id).forEach((f) => {
    const div = document.createElement("div"); div.className = "frame";
    const id = document.createElement("span");
    id.className = "id"; id.textContent = "0x" + f.id.toString(16);
    div.appendChild(id);
    // 64 bits, LSB-first within each byte (canonical convention).
    for (let bit = 0; bit < 64; bit++) {
      const byte = f.data[bit >> 3];
      const on = (byte >> (bit & 7)) & 1;
      const cell = document.createElement("span");
      cell.className = "bit" + (on ? " set" : "");
      cell.textContent = on ? "1" : "0";
      cell.title = "bit " + bit;
      cell.onclick = () => assignBit(f.id, bit);
      div.appendChild(cell);
    }
    host.appendChild(div);
  });
}

function assignBit(id, bit) {
  if (!cfg) return;
  const fn = document.getElementById("discFunc").value;
  const m = cfg.maps[fn] || (cfg.maps[fn] = { combine: 0, bits: [] });
  if (m.bits.some((b) => b.id === id && b.bit === bit)) {
    alert("0x" + id.toString(16) + " bit " + bit + " is already mapped to " + fn);
    return;
  }
  if (m.bits.length >= MAX_BITS) {
    alert(fn + " already has the maximum of " + MAX_BITS + " bits. " +
          "Remove one on the Mapping tab before adding another.");
    return;
  }
  m.bits.push({ id, bit });
  alert("Added 0x" + id.toString(16) + " bit " + bit + " to " + fn +
        " (Save & apply to persist)");
}

// ---- outbound ----
function collect() {
  cfg.blinkPeriodMs = clamp(document.getElementById("blinkPeriodMs").value, 50, 5000);
  cfg.spotHoldMs = clamp(document.getElementById("spotHoldMs").value, 100, 10000);
  cfg.testMaxMs = clamp(document.getElementById("testMaxMs").value, 10000, 3600000);
  cfg.flashSource = document.getElementById("flashSource").value;
  return cfg;
}

function save() { send({ type: "set_config", config: collect() }); }

function exportConfig() {
  const blob = new Blob([JSON.stringify(collect(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "mccan-config.json"; a.click();
  URL.revokeObjectURL(a.href);
}

function importConfig(file) {
  const r = new FileReader();
  r.onload = () => {
    try { cfg = JSON.parse(r.result); render(); save(); }
    catch (e) { alert("Invalid JSON file"); }
  };
  r.readAsText(file);
}

// ---- helpers ----
function clamp(v, lo, hi) { v = Number(v) | 0; return v < lo ? lo : v > hi ? hi : v; }

// ---- wiring ----
document.querySelectorAll("nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.getElementById("tab-" + b.dataset.tab).classList.add("active");
  };
});
document.getElementById("saveBtn").onclick = save;
document.getElementById("reloadBtn").onclick = () => send({ type: "get_config" });
document.getElementById("exportBtn").onclick = exportConfig;
document.getElementById("importInput").onchange = (e) => {
  if (e.target.files[0]) importConfig(e.target.files[0]);
};
document.getElementById("discToggle").onchange = (e) => {
  send({ type: "discovery", enable: e.target.checked });
};

document.getElementById("testExitBtn").onclick = exitTest;

connect();
