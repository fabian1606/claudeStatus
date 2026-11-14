#include "web.h"
#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include "config.h"
#include "hook.h"
#include "leds.h"
#include "sessions.h"
#include "settings.h"

namespace {

WebServer server(HTTP_PORT);
bool gStarted = false;

// ---------------------------------------------------------------------------
// POST /hook – body is read by ourselves into a fixed buffer (keeps the first
// HTTP_BODY_MAX bytes, discards the rest), so multi-100-KB PreToolUse payloads
// (e.g. Write tool_input) never hit the heap.
// ---------------------------------------------------------------------------
char hookBody[HTTP_BODY_MAX + 1];
size_t hookLen = 0;
bool hookTruncated = false;

class HookHandler : public RequestHandler {
 public:
  bool canHandle(HTTPMethod method, String uri) override { return method == HTTP_POST && uri == "/hook"; }
  bool canRaw(String uri) override { return uri == "/hook"; }

  void raw(WebServer& srv, String uri, HTTPRaw& raw) override {
    (void)uri;
    if (raw.status != RAW_START) return;
    hookLen = 0;
    hookTruncated = false;
    size_t expected = (size_t)max(0, srv.clientContentLength());
    WiFiClient client = srv.client();  // shares socket + rx buffer
    size_t got = 0;
    uint32_t last = millis();
    uint8_t scratch[256];
    while (got < expected && millis() - last < 3000) {
      int avail = client.available();
      if (avail <= 0) {
        if (!client.connected()) break;
        delay(1);
        continue;
      }
      size_t want = min((size_t)avail, expected - got);
      size_t room = HTTP_BODY_MAX - hookLen;
      int n;
      if (room > 0) {
        n = client.read((uint8_t*)hookBody + hookLen, min(want, room));
        if (n > 0) hookLen += n;
      } else {
        n = client.read(scratch, min(want, sizeof(scratch)));
        hookTruncated = true;
      }
      if (n > 0) {
        got += n;
        last = millis();
      }
    }
    if (got < expected) hookTruncated = true;
    hookBody[hookLen] = 0;
    // tell WebServer the body is consumed (skips its own fixed-size blocking read loop)
    raw.totalSize = expected;
    raw.currentSize = 0;
  }

  bool handle(WebServer& srv, HTTPMethod method, String uri) override {
    (void)method;
    (void)uri;
    processHookPayload(hookBody, hookLen, hookTruncated, "http");
    srv.send(200, "application/json", "{\"ok\":true}");
    return true;
  }
};

const char INDEX_HTML[] PROGMEM = R"HTML(<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claude Buddy</title>
<style>
:root{--bg:#faf9f5;--fg:#1f1e1d;--mut:#6b6a66;--card:#fff;--line:#e6e3da;--acc:#d97757}
@media(prefers-color-scheme:dark){:root{--bg:#1f1e1d;--fg:#f0eee6;--mut:#a3a19a;--card:#2a2927;--line:#3a3936}}
body{margin:0;font:15px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:520px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px}
.st{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:600}
.dot{width:16px;height:16px;border-radius:50%;background:#999}
.idle{background:#e8b48a}.working{background:#d97757}.attention{background:#ff4600}.done{background:#2ecc71}
table{width:100%;border-collapse:collapse;font-size:13px}td{padding:4px 2px;border-top:1px solid var(--line)}
td.id{font-family:ui-monospace,monospace;word-break:break-all}
.btns{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
button{padding:8px 4px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg);font:inherit;cursor:pointer}
button:hover{border-color:var(--acc)}
input[type=range]{width:100%;accent-color:var(--acc)}
.mut{color:var(--mut);font-size:13px}
details.an{border-top:1px solid var(--line);padding:8px 0}details.an:first-of-type{border-top:0}
details.an summary{cursor:pointer;font-weight:600;display:flex;align-items:center;gap:8px;list-style:none}
details.an summary::-webkit-details-marker{display:none}
.row{display:grid;grid-template-columns:110px 1fr 44px;align-items:center;gap:8px;margin:6px 0}
.row span.v{text-align:right;font-variant-numeric:tabular-nums;color:var(--mut);font-size:13px}
select,input[type=color]{font:inherit;padding:4px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
input[type=color]{width:56px;height:32px;padding:2px}
.acts{display:flex;gap:6px;margin-top:6px}.acts button{flex:1}
</style></head><body><main>
<h1>Claude Buddy</h1>
<div class="card"><div class="st"><span id="dot" class="dot"></span><span id="state">…</span></div>
<div class="mut" id="info"></div></div>
<div class="card"><b>Sessions</b><table id="sess"></table></div>
<div class="card"><b>Test-Animation (5 s)</b><div class="btns" style="margin-top:8px">
<button onclick="t('idle')">Idle</button><button onclick="t('working')">Arbeitet</button>
<button onclick="t('attention')">Achtung</button><button onclick="t('done')">Fertig</button></div></div>
<div class="card"><b>Helligkeit</b> <span id="bv"></span>
<input type="range" id="br" min="0" max="255" oninput="bv.textContent=this.value" onchange="setB(this.value)"></div>
<div class="card"><b>Animationen</b>
<div class="mut">Änderungen werden sofort als Vorschau gezeigt und gespeichert.</div><div id="anims"></div>
<div class="acts"><button onclick="resetAll()">Alle auf Standard</button></div></div>
<p class="mut">API: POST /hook · GET /status · /test?state= · /brightness?value=</p>
</main><script>
const L={idle:'Idle',working:'Arbeitet',attention:'Braucht Aufmerksamkeit',done:'Fertig'};
let dragging=false;br.onpointerdown=()=>dragging=true;br.onpointerup=()=>dragging=false;
async function load(){try{const r=await fetch('/status');const s=await r.json();
state.textContent=L[s.state]||s.state;dot.className='dot '+s.state;
info.textContent=(s.preview?'Vorschau aktiv: '+(L[s.preview]||s.preview)+' · ':'')+s.sessions.length+' Session(s)';
sess.innerHTML=s.sessions.length?s.sessions.map(x=>'<tr><td class="id">'+x.id+'</td><td>'+(L[x.state]||x.state)+'</td><td>vor '+fmt(x.age_s)+'</td></tr>').join(''):'<tr><td class="mut">keine</td></tr>';
if(!dragging&&document.activeElement!==br){br.value=s.brightness;bv.textContent=s.brightness}}catch(e){info.textContent='offline?'}}
function fmt(s){return s<60?s+' s':s<3600?Math.floor(s/60)+' min':Math.floor(s/3600)+' h'}
async function t(x){await fetch('/test?state='+x);load()}
async function setB(v){await fetch('/brightness?value='+v);load()}
const FXL={solid:'Dauerlicht',breathe:'Atmen',blink:'Blinken',flash:'2× Blitz, dann an',scanner:'Lauflicht (hin & her)',wave:'Welle',rainbow:'Regenbogen',sparkle:'Funkeln',flashoff:'2× Blitz, dann aus',off:'Aus'};
const ORDER=['idle','working','attention','done'];let A=null,tm={};
async function loadAnims(){const r=await fetch('/anim');A=await r.json();renderAnims()}
function renderAnims(){anims.innerHTML=ORDER.map(st=>{const a=A.states[st];return `<details class="an" ${st==openSt?'open':''} ontoggle="if(this.open)openSt='${st}'">
<summary><span class="dot ${st}" style="background:${a.color}"></span>${L[st]} <span class="mut">· ${FXL[a.effect]||a.effect}</span></summary>
<div class="row"><label>Effekt</label><select onchange="upd('${st}','effect',this.value,1)">${A.effects.map(e=>`<option value="${e}" ${e==a.effect?'selected':''}>${FXL[e]||e}</option>`).join('')}</select><span></span></div>
<div class="row"><label>Farbe</label><input type="color" value="${a.color}" oninput="upd('${st}','color',this.value)" onchange="upd('${st}','color',this.value,1)"><span></span></div>
<div class="row"><label>Tempo (ms)</label><input type="range" min="100" max="10000" step="50" value="${a.period}" oninput="this.nextElementSibling.textContent=this.value;upd('${st}','period',this.value)" onchange="upd('${st}','period',this.value,1)"><span class="v">${a.period}</span></div>
<div class="row"><label>Max. Helligkeit</label><input type="range" min="0" max="100" value="${a.hi}" oninput="this.nextElementSibling.textContent=this.value+'%';upd('${st}','hi',this.value)" onchange="upd('${st}','hi',this.value,1)"><span class="v">${a.hi}%</span></div>
<div class="row"><label>Min. Helligkeit</label><input type="range" min="0" max="100" value="${a.lo}" oninput="this.nextElementSibling.textContent=this.value+'%';upd('${st}','lo',this.value)" onchange="upd('${st}','lo',this.value,1)"><span class="v">${a.lo}%</span></div>
<div class="row"><label>Zwinkern</label><input type="checkbox" ${a.blink?'checked':''} onchange="upd('${st}','blink',this.checked?1:0,1)" style="justify-self:start"><span></span></div>
<div class="acts"><button onclick="t('${st}')">Vorschau</button><button onclick="resetSt('${st}')">Standard</button></div></details>`}).join('')}
let openSt='working';
function upd(st,k,v,save){A.states[st][k]=k=='effect'||k=='color'?v:+v;clearTimeout(tm[st]);
const go=()=>fetch(`/anim/set?state=${st}&${k}=${encodeURIComponent(v)}&save=${save?1:0}`).then(()=>{if(save&&k=='effect')renderAnims()});
if(save)go();else tm[st]=setTimeout(go,120)}
async function resetSt(st){await fetch('/anim/reset?state='+st);loadAnims()}
async function resetAll(){if(confirm('Alle Animationen auf Standard zurücksetzen?')){await fetch('/anim/reset');loadAnims()}}
load();loadAnims();setInterval(load,2000);
</script></body></html>)HTML";

void sendJson(int code, const String& body) { server.send(code, "application/json", body); }

void handleRoot() { server.send_P(200, "text/html; charset=utf-8", INDEX_HTML); }

void handleStatus() { sendJson(200, buildStatusJson()); }

void handleTest() {
  BuddyState s;
  String arg = server.arg("state");
  if (!parseStateName(arg.c_str(), s)) {
    sendJson(400, "{\"ok\":false,\"error\":\"state must be idle|working|attention|done\"}");
    return;
  }
  Leds::preview(s, millis());
  Serial.printf("[http] test preview: %s\n", stateName(s));
  sendJson(200, String("{\"ok\":true,\"preview\":\"") + stateName(s) + "\",\"duration_s\":" + (TEST_PREVIEW_MS / 1000) + "}");
}

void handleBrightness() {
  if (server.hasArg("value")) {
    long v = server.arg("value").toInt();
    if (v < 0 || v > 255 || server.arg("value").length() == 0) {
      sendJson(400, "{\"ok\":false,\"error\":\"value must be 0-255\"}");
      return;
    }
    Leds::setBrightness((uint8_t)v);
    Settings::saveBrightness((uint8_t)v);
    Serial.printf("[http] brightness=%ld (saved)\n", v);
  }
  sendJson(200, String("{\"ok\":true,\"brightness\":") + Leds::brightness() + "}");
}

String colorHex(const Leds::AnimCfg& a) {
  char buf[8];
  snprintf(buf, sizeof(buf), "#%02x%02x%02x", a.r, a.g, a.b);
  return buf;
}

void handleAnimGet() {
  JsonDocument doc;
  JsonArray fx = doc["effects"].to<JsonArray>();
  for (uint8_t i = 0; i < Leds::FX_COUNT; i++) fx.add(Leds::effectName(i));
  JsonObject sts = doc["states"].to<JsonObject>();
  for (uint8_t i = 0; i < Leds::NUM_STATES; i++) {
    const Leds::AnimCfg& a = Leds::anim((BuddyState)i);
    JsonObject o = sts[stateName((BuddyState)i)].to<JsonObject>();
    o["effect"] = Leds::effectName(a.effect);
    o["color"] = colorHex(a);
    o["period"] = a.period;
    o["lo"] = a.lo;
    o["hi"] = a.hi;
    o["blink"] = a.blink;
  }
  String out;
  serializeJson(doc, out);
  sendJson(200, out);
}

// GET /anim/set?state=working[&effect=breathe][&color=d97757][&period=1500][&lo=35][&hi=100][&blink=1][&save=1]
void handleAnimSet() {
  BuddyState s;
  if (!parseStateName(server.arg("state").c_str(), s)) {
    sendJson(400, "{\"ok\":false,\"error\":\"state must be idle|working|attention|done\"}");
    return;
  }
  Leds::AnimCfg a = Leds::anim(s);
  if (server.hasArg("effect") && !Leds::parseEffect(server.arg("effect").c_str(), a.effect)) {
    sendJson(400, "{\"ok\":false,\"error\":\"unknown effect\"}");
    return;
  }
  if (server.hasArg("color")) {
    String c = server.arg("color");
    if (c.startsWith("#")) c = c.substring(1);
    if (c.length() != 6) {
      sendJson(400, "{\"ok\":false,\"error\":\"color must be rrggbb\"}");
      return;
    }
    uint32_t v = strtoul(c.c_str(), nullptr, 16);
    a.r = (v >> 16) & 0xFF;
    a.g = (v >> 8) & 0xFF;
    a.b = v & 0xFF;
  }
  if (server.hasArg("period")) a.period = (uint16_t)constrain(server.arg("period").toInt(), 100, 20000);
  if (server.hasArg("lo")) a.lo = (uint8_t)constrain(server.arg("lo").toInt(), 0, 100);
  if (server.hasArg("hi")) a.hi = (uint8_t)constrain(server.arg("hi").toInt(), 0, 100);
  if (server.hasArg("blink")) a.blink = server.arg("blink").toInt() ? 1 : 0;
  Leds::setAnim(s, a);
  Leds::preview(s, millis());  // show the edited state for a few seconds
  bool save = !server.hasArg("save") || server.arg("save").toInt() != 0;
  if (save) Settings::saveAnims();
  sendJson(200, save ? "{\"ok\":true,\"saved\":true}" : "{\"ok\":true,\"saved\":false}");
}

// GET /anim/reset[?state=working]
void handleAnimReset() {
  BuddyState s;
  if (server.hasArg("state")) {
    if (!parseStateName(server.arg("state").c_str(), s)) {
      sendJson(400, "{\"ok\":false,\"error\":\"bad state\"}");
      return;
    }
    Leds::setAnim(s, Leds::defaultAnim(s));
    Leds::preview(s, millis());
  } else {
    Leds::resetAnims();
  }
  Settings::saveAnims();
  sendJson(200, "{\"ok\":true}");
}

}  // namespace

String buildStatusJson() {
  uint32_t now = millis();
  JsonDocument doc;
  doc["state"] = stateName(Sessions::aggregate());
  JsonArray arr = doc["sessions"].to<JsonArray>();
  for (size_t i = 0; i < MAX_SESSIONS; i++) {
    const Session* s = Sessions::at(i);
    if (!s) continue;
    JsonObject o = arr.add<JsonObject>();
    o["id"] = s->id;
    o["state"] = stateName(s->state);
    o["age_s"] = (now - s->lastEventMs) / 1000;
  }
  doc["brightness"] = Leds::brightness();
  // extras (not required by the contract)
  if (Leds::previewActive(now)) doc["preview"] = stateName(Leds::previewState());
  doc["uptime_s"] = now / 1000;
  if (WiFi.status() == WL_CONNECTED) doc["ip"] = WiFi.localIP().toString();
  String out;
  serializeJson(doc, out);
  return out;
}

namespace Web {

void begin() {
  if (gStarted) return;
  server.addHandler(new HookHandler());
  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/test", HTTP_GET, handleTest);
  server.on("/brightness", HTTP_GET, handleBrightness);
  server.on("/anim", HTTP_GET, handleAnimGet);
  server.on("/anim/set", HTTP_GET, handleAnimSet);
  server.on("/anim/reset", HTTP_GET, handleAnimReset);
  server.onNotFound([] { sendJson(404, "{\"ok\":false,\"error\":\"not found\"}"); });
  server.enableCORS(true);
  server.begin();
  gStarted = true;
  Serial.printf("[web] listening on http://%s/ and http://" BUDDY_HOSTNAME ".local/\n",
                WiFi.localIP().toString().c_str());
}

void loop() {
  if (gStarted) server.handleClient();
}

bool started() { return gStarted; }

}  // namespace Web
