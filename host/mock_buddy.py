#!/usr/bin/env python3
"""mock_buddy.py - simulates the Claude Buddy device HTTP API (see ../CONTRACT.md).

Usage:
    python3 mock_buddy.py [--host 127.0.0.1] [--port 8787] [--timescale 1] [--quiet]

Then point the hook at it:
    export CLAUDE_BUDDY_URL=http://localhost:8787

--timescale N divides all timeouts by N (e.g. 600 -> "15 min" becomes 1.5 s),
which is handy for testing the decay rules.
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATES = ("idle", "working", "attention", "done")
PRIORITY = {"attention": 3, "working": 2, "done": 1, "idle": 0}

EVENT_STATE = {
    "SessionStart": "idle",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "PostToolUse": "working",
    "SubagentStop": "working",
    "Notification": "attention",
    "PermissionRequest": "attention",
    "Stop": "done",
    "StopFailure": "done",   # turn ended by an API error
}
# Notification types that do NOT need the user (see README / report):
# idle_prompt fires ~60 s after every Stop and would turn every "done" into
# "attention"; auth_success is purely informational.
PASSIVE_NOTIFICATIONS = {"idle_prompt", "auth_success"}

# Timeouts in seconds (divided by --timescale)
ACTIVE_TIMEOUT = 15 * 60     # attention/working silent -> idle
DONE_DECAY = 10 * 60         # done -> idle
SESSION_TTL = 2 * 60 * 60    # any session silent -> removed
PREVIEW_S = 5                # /test preview duration (not scaled)

USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
COLORS = {"idle": "2;37", "working": "38;2;217;119;87", "attention": "1;5;38;2;255;80;40",
          "done": "1;32", "dim": "2", "bold": "1"}


def c(text, kind):
    if not USE_COLOR:
        return text
    return f"\033[{COLORS[kind]}m{text}\033[0m"


def log(msg):
    print(f"{c(time.strftime('%H:%M:%S'), 'dim')} {msg}", flush=True)


class Buddy:
    def __init__(self, timescale=1.0, quiet=False):
        self.lock = threading.Lock()
        self.sessions = {}  # id -> {"state", "last", "since"}
        self.brightness = 80
        self.preview = None  # (state, until)
        self.scale = timescale
        self.quiet = quiet
        self.last_aggregate = "idle"

    # --- core logic -------------------------------------------------------
    def handle_event(self, ev):
        name = ev.get("hook_event_name")
        sid = ev.get("session_id")
        if not isinstance(name, str) or not isinstance(sid, str) or not sid:
            return "ignored (missing session_id/hook_event_name)"
        now = time.monotonic()
        with self.lock:
            self._expire(now)
            sess = self.sessions.get(sid)
            if name == "SessionEnd":
                if sess:
                    del self.sessions[sid]
                    self._session_log(sid, sess["state"], "removed", name)
                return "removed"
            if name not in EVENT_STATE:
                return "ignored (unknown event)"
            new = EVENT_STATE[name]
            if name == "Notification" and ev.get("notification_type") in PASSIVE_NOTIFICATIONS:
                new = sess["state"] if sess else "idle"
            if name == "SubagentStop" and sess and sess["state"] in ("done", "idle"):
                # a (background) subagent finishing after the parent stopped
                # must not resurrect "working"
                new = sess["state"]
            if sess is None:
                sess = self.sessions[sid] = {"state": None, "last": now, "since": now}
            old = sess["state"]
            sess["last"] = now
            if old != new:
                sess["state"] = new
                sess["since"] = now
                self._session_log(sid, old or "new", new, name, ev)
            self._check_aggregate()
            return new

    def _expire(self, now):
        s = self.scale
        for sid, sess in list(self.sessions.items()):
            silent = now - sess["last"]
            if silent > SESSION_TTL / s:
                del self.sessions[sid]
                self._session_log(sid, sess["state"], "removed", "timeout 2h")
                continue
            st = sess["state"]
            if st in ("working", "attention") and silent > ACTIVE_TIMEOUT / s:
                self._set(sid, sess, "idle", "timeout 15min", now)
            elif st == "done" and now - sess["since"] > DONE_DECAY / s:
                self._set(sid, sess, "idle", "decay 10min", now)

    def _set(self, sid, sess, new, why, now):
        old = sess["state"]
        sess["state"] = new
        sess["since"] = now
        self._session_log(sid, old, new, why)

    def aggregate(self):
        states = [s["state"] for s in self.sessions.values()]
        return max(states, key=PRIORITY.get) if states else "idle"

    def _check_aggregate(self):
        agg = self.aggregate()
        if agg != self.last_aggregate:
            log(f"{c('EYES', 'bold')} {c(self.last_aggregate, self.last_aggregate)} -> "
                f"{c(agg.upper(), agg)}  ({len(self.sessions)} session(s))")
            self.last_aggregate = agg

    def _session_log(self, sid, old, new, why, ev=None):
        if self.quiet:
            return
        extra = ""
        if ev:
            if ev.get("tool_name"):
                extra = f" tool={ev['tool_name']}"
            if ev.get("notification_type"):
                extra += f" type={ev['notification_type']}"
        newc = c(new, new) if new in STATES else c(new, "dim")
        oldc = c(old, old) if old in STATES else c(old, "dim")
        log(f"  session {sid[:8]:<8} {oldc} -> {newc}  [{why}{extra}]")

    def tick(self):
        with self.lock:
            self._expire(time.monotonic())
            self._check_aggregate()
            if self.preview and time.monotonic() > self.preview[1]:
                log(f"{c('PREVIEW', 'bold')} ended")
                self.preview = None

    def status(self):
        with self.lock:
            now = time.monotonic()
            self._expire(now)
            self._check_aggregate()
            state = self.aggregate()
            out = {
                "state": state,
                "sessions": [{"id": sid, "state": s["state"], "age_s": int(now - s["last"])}
                             for sid, s in self.sessions.items()],
                "brightness": self.brightness,
            }
            if self.preview and now < self.preview[1]:
                out["preview"] = self.preview[0]
            return out


class Handler(BaseHTTPRequestHandler):
    buddy: Buddy = None
    server_version = "ClaudeBuddyMock/1.0"

    def log_message(self, fmt, *args):  # silence default access log
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlparse(self.path).path != "/hook":
            return self._send(404, {"ok": False, "error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            ev = json.loads(raw or b"{}")
            if not isinstance(ev, dict):
                raise ValueError("not an object")
        except ValueError:
            log(c("bad JSON on /hook", "attention"))
            return self._send(400, {"ok": False, "error": "bad json"})
        self.buddy.handle_event(ev)
        self._send(200, {"ok": True})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        b = self.buddy
        if u.path == "/status":
            return self._send(200, b.status())
        if u.path == "/test":
            st = (q.get("state") or [""])[0]
            if st not in STATES:
                return self._send(400, {"ok": False, "error": "state must be idle|working|attention|done"})
            with b.lock:
                b.preview = (st, time.monotonic() + PREVIEW_S)
            log(f"{c('PREVIEW', 'bold')} {c(st.upper(), st)} for {PREVIEW_S}s")
            return self._send(200, {"ok": True, "preview": st, "seconds": PREVIEW_S})
        if u.path == "/brightness":
            try:
                v = int((q.get("value") or [""])[0])
                if not 0 <= v <= 255:
                    raise ValueError
            except ValueError:
                return self._send(400, {"ok": False, "error": "value must be 0-255"})
            b.brightness = v
            log(f"brightness -> {v}")
            return self._send(200, {"ok": True, "brightness": v})
        if u.path == "/":
            return self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")
        self._send(404, {"ok": False, "error": "not found"})


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Claude Buddy (mock)</title>
<style>body{font-family:system-ui;margin:16px;max-width:520px}button{margin:4px;padding:8px 12px}
pre{background:#f3f3f3;padding:8px;overflow:auto}</style></head><body>
<h1>Claude Buddy <small>(mock)</small></h1><pre id="s">...</pre>
<div><button onclick="t('idle')">idle</button><button onclick="t('working')">working</button>
<button onclick="t('attention')">attention</button><button onclick="t('done')">done</button></div>
<p>Brightness <input type="range" min="0" max="255" id="b"
 onchange="fetch('/brightness?value='+this.value)"></p>
<script>
function t(s){fetch('/test?state='+s)}
async function r(){const j=await (await fetch('/status')).json();
document.getElementById('s').textContent=JSON.stringify(j,null,2);
const b=document.getElementById('b');if(document.activeElement!==b)b.value=j.brightness}
r();setInterval(r,1000);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--timescale", type=float, default=1.0,
                    help="divide all timeouts by this factor (testing)")
    ap.add_argument("--quiet", action="store_true", help="only log aggregate changes")
    args = ap.parse_args()

    buddy = Buddy(args.timescale, args.quiet)
    Handler.buddy = buddy
    srv = ThreadingHTTPServer((args.host, args.port), Handler)

    def ticker():
        while True:
            time.sleep(0.25 if args.timescale > 1 else 1)
            buddy.tick()

    threading.Thread(target=ticker, daemon=True).start()
    log(f"Claude Buddy mock on http://{args.host}:{args.port}  "
        f"(timescale {args.timescale:g})  eyes: {c('idle', 'idle')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
