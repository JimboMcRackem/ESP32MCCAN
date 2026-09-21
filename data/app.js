"use strict";

// Function keys must match config_json.cpp kFuncNames order/spelling.
const FUNCS = ["run","leftInd","rightInd","frontBrake","rearBrake",
               "lowBeam","highBeam","highBeamFlash","dayNight","kickStand"];
const COLORS = ["drlWhiteDay","drlWhiteNight","drlDimRedDay","drlDimRedNight",
                "indicatorOrange","brakeRed"];
const DENALI = ["day","low","high","spot"];
const COMBINE = { 0: "Single", 1: "And", 2: "Or" };
const MAX_BITS = 4;    // must match FunctionMap::MAX_BITS in config.h
const PROTOCOL_VERSION = 2;   // must match kProtocolVersion in web_protocol.h
// Must match kScenarioNames in test_mode.cpp — the firmware table is
// authoritative and rejects anything it does not know.
const SCENARIOS = ["allOff","drlDay","drlNight","leftInd","rightInd",
                   "hazards","brake","brakeNight","lowBeam","highBeam"];
// ChannelIndex corner order.
const ZONES = ["front L","front R","rear L","rear R"];

let cfg = null;         // last config from device
let ws = null;
let testState = { active: false, kind: "off", remainingMs: 0 };
let activeScenario = null;
let testZoneState = [0, 0, 0, 0].map(() => ({ hue: [255, 255, 255], level: 0 }));
let testDenali = 0;

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
  else if (msg.type === "test_state") { testState = msg; renderTestBanner(); }
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
  renderDenali();
  renderColors();
  renderScenarios();
  renderTestZones();
  renderMaps();
  renderDiscFuncOptions();
}

function renderDenali() {
  const host = document.getElementById("denali");
  host.innerHTML = "<h3>Denali levels (0-255)</h3>";
  DENALI.forEach((k) => {
    const lab = document.createElement("label");
    lab.textContent = "Denali " + k;
    const inp = document.createElement("input");
    inp.type = "number"; inp.min = 0; inp.max = 255; inp.value = cfg.denali[k];
    inp.oninput = () => { cfg.denali[k] = clamp(inp.value, 0, 255); };
    lab.appendChild(inp); host.appendChild(lab);
  });
}

function renderColors() {
  const host = document.getElementById("colors");
  host.innerHTML = "";
  COLORS.forEach((k) => {
    const row = document.createElement("div");
    row.className = "row";
    const name = document.createElement("span"); name.textContent = k;
    const picker = document.createElement("input");
    picker.type = "color"; picker.value = rgbToHex(cfg.colors[k]);
    picker.oninput = () => { cfg.colors[k] = hexToRgb(picker.value); };
    row.appendChild(name); row.appendChild(picker); host.appendChild(row);
  });
}

function renderTestBanner() {
  const el = document.getElementById("testBanner");
  el.hidden = !testState.active;
  if (!testState.active) {
    activeScenario = null;
    renderScenarios();
    return;
  }
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

function sendTestZones() {
  activeScenario = null;
  scheduleSend(() => send({
    type: "test",
    mode: "zones",
    zones: testZoneState.map((z) => resolveJs(z.hue, z.level)),
    denali: testDenali,
  }));
}

function renderTestZones() {
  const host = document.getElementById("testZones");
  host.innerHTML = "";
  ZONES.forEach((label, i) => {
    const z = testZoneState[i];
    const box = document.createElement("div"); box.className = "zone";
    const h = document.createElement("h4"); h.textContent = label; box.appendChild(h);

    const row = document.createElement("div"); row.className = "row";
    const picker = document.createElement("input");
    picker.type = "color"; picker.value = rgbToHex(z.hue);
    const level = document.createElement("input");
    level.type = "range"; level.min = 0; level.max = 100;
    level.value = levelToPct(z.level);
    const pct = document.createElement("span");
    pct.className = "pct"; pct.textContent = level.value + "%";

    const update = () => {
      z.hue = normalizeHue(hexToRgb(picker.value));
      z.level = pctToLevel(level.value);
      pct.textContent = level.value + "%";
      sendTestZones();
      renderScenarios();     // a zone edit clears the active scenario
    };
    picker.oninput = update;
    level.oninput = update;

    row.appendChild(picker); row.appendChild(level); row.appendChild(pct);
    box.appendChild(row); host.appendChild(box);
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
function rgbToHex(a) {
  const h = (n) => ("0" + (n & 255).toString(16)).slice(-2);
  return "#" + h(a[0]) + h(a[1]) + h(a[2]);
}
function hexToRgb(s) {
  return [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16)];
}

// Mirrors resolveColor()/colorFromRgb() in color.h. Zone overrides are sent
// as raw duty, so the app applies gamma itself.
function gamma8Js(level) { return Math.round(255 * Math.pow(level / 255, 2.2)); }

function normalizeHue(rgb) {
  const m = Math.max(rgb[0], rgb[1], rgb[2]);
  return m ? rgb.map((c) => Math.round((c * 255) / m)) : [255, 255, 255];
}

function resolveJs(hue, level) {
  const g = gamma8Js(level);
  return normalizeHue(hue).map((c) => Math.floor((c * g) / 255));
}

function pctToLevel(p) { return Math.round((Number(p) * 255) / 100); }
function levelToPct(l) { return Math.round((l * 100) / 255); }

// One send per animation frame, so dragging a slider cannot flood the socket.
let pendingSend = null, rafId = 0;
function scheduleSend(fn) {
  pendingSend = fn;
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    rafId = 0;
    const f = pendingSend; pendingSend = null;
    if (f) f();
  });
}

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
document.getElementById("testDenali").oninput = (e) => {
  testDenali = pctToLevel(e.target.value);
  document.getElementById("testDenaliPct").textContent = e.target.value + "%";
  sendTestZones();
};

connect();
