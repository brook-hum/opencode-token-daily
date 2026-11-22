# -*- coding: utf-8 -*-
"""
OpenCode Token Daily  V1.0.0-20261122
-------------------------------------
A fully local statistics dashboard for OpenCode token usage.
Reads OpenCode's local SQLite database read-only, computes everything on
this machine, and serves a small web UI on 127.0.0.1 only. No cloud, no
external Python packages required.
"""

import base64
import datetime
import getpass
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(APP_DIR, "web")
DATA_DIR = os.path.join(os.path.expanduser("~"), ".opencode-token-daily")
DB_PATH = os.path.join(os.path.expanduser("~"), ".local", "share", "opencode", "opencode.db")
VERSION = "V1.0.0-20261122"
CACHE_TTL = 15  # seconds

os.makedirs(DATA_DIR, exist_ok=True)

_cache = {"at": 0.0, "data": None}


# --------------------------------------------------------------------------- #
#  Data access                                                                 #
# --------------------------------------------------------------------------- #
def open_db():
    uri = "file:" + DB_PATH.replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def parse_tokens(obj):
    """Return (input, output, reasoning, cache_read, cache_write) from a
    message `tokens` object. Handles both V2 and V1 shapes."""
    t = obj.get("tokens") or {}
    if not isinstance(t, dict):
        return 0, 0, 0, 0, 0
    cache = t.get("cache") or {}
    if isinstance(cache, dict):
        cr = cache.get("read", 0) or 0
        cw = cache.get("write", 0) or 0
    else:
        cr = cw = 0
    return (
        int(t.get("input", 0) or 0),
        int(t.get("output", 0) or 0),
        int(t.get("reasoning", 0) or 0),
        int(cr),
        int(cw),
    )


def empty_bucket():
    return {
        "tokens": 0,
        "input": 0,
        "output": 0,
        "reasoning": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "cost": 0.0,
        "messages": 0,
    }


def add_bucket(bucket, parts, cost):
    inp, out, rea, cr, cw = parts
    bucket["input"] += inp
    bucket["output"] += out
    bucket["reasoning"] += rea
    bucket["cacheRead"] += cr
    bucket["cacheWrite"] += cw
    bucket["tokens"] += inp + out + rea + cr + cw
    bucket["cost"] += float(cost or 0)
    bucket["messages"] += 1


def project_display_name(project_id, worktree, name):
    if name:
        return name
    wt = (worktree or "").replace("\\", "/").rstrip("/")
    if wt in ("", "/"):
        return "全局"
    return wt.split("/")[-1] or wt


def compute_stats():
    now_ms = int(time.time() * 1000)
    con = open_db()

    # session id -> (project id, created)
    sess_proj = {}
    v2_ids = set()
    for row in con.execute("SELECT id, project_id, time_created FROM session_v2"):
        sess_proj[row["id"]] = (row["project_id"], row["time_created"])
        v2_ids.add(row["id"])
    # V1-only sessions (not migrated into session_v2)
    for row in con.execute("SELECT id, project_id, time_created FROM session"):
        if row["id"] not in v2_ids:
            sess_proj[row["id"]] = (row["project_id"], row["time_created"])

    # project id -> display info
    projects = {}
    for row in con.execute("SELECT id, worktree, name FROM project"):
        projects[row["id"]] = {
            "id": row["id"],
            "name": project_display_name(row["id"], row["worktree"], row["name"]),
            "path": row["worktree"] or "",
        }

    # Collect per-message token events. Prefer V2 session_message; use V1
    # `message` table only for sessions that were never migrated, to avoid
    # double counting.
    events = []
    for sid, data in con.execute(
        "SELECT session_id, data FROM session_message WHERE type = 'assistant'"
    ):
        try:
            obj = json.loads(data)
        except Exception:
            continue
        tm = (obj.get("time") or {}).get("created") or 0
        if not tm:
            continue
        events.append((tm, sid, parse_tokens(obj), obj.get("cost", 0)))

    for sid, data in con.execute("SELECT session_id, data FROM message"):
        if sid in v2_ids:
            continue
        try:
            obj = json.loads(data)
        except Exception:
            continue
        if obj.get("role") != "assistant" or "tokens" not in obj:
            continue
        tm = (obj.get("time") or {}).get("created") or 0
        if not tm:
            continue
        events.append((tm, sid, parse_tokens(obj), obj.get("cost", 0)))

    con.close()
    events.sort(key=lambda e: e[0])

    total = empty_bucket()
    daily = {}
    proj_agg = {}
    ranges = {"24h": empty_bucket(), "7d": empty_bucket(), "30d": empty_bucket(), "1y": empty_bucket()}
    cutoffs = {
        "24h": now_ms - 24 * 3600 * 1000,
        "7d": now_ms - 7 * 24 * 3600 * 1000,
        "30d": now_ms - 30 * 24 * 3600 * 1000,
        "1y": now_ms - 365 * 24 * 3600 * 1000,
    }

    for tm, sid, parts, cost in events:
        add_bucket(total, parts, cost)
        for key, cutoff in cutoffs.items():
            if tm >= cutoff:
                add_bucket(ranges[key], parts, cost)
        day = datetime.datetime.fromtimestamp(tm / 1000).strftime("%Y-%m-%d")
        d = daily.setdefault(day, empty_bucket())
        add_bucket(d, parts, cost)
        pid = sess_proj.get(sid, ("unknown", 0))[0]
        p = proj_agg.setdefault(pid, empty_bucket())
        p["name"] = projects.get(pid, {}).get("name", "未知项目")
        p["path"] = projects.get(pid, {}).get("path", "")
        add_bucket(p, parts, cost)

    project_list = []
    for pid, p in sorted(proj_agg.items(), key=lambda kv: kv[1]["tokens"], reverse=True):
        project_list.append({
            "id": pid,
            "name": p["name"],
            "path": p["path"],
            "tokens": p["tokens"],
            "input": p["input"],
            "output": p["output"],
            "reasoning": p["reasoning"],
            "cacheRead": p["cacheRead"],
            "cacheWrite": p["cacheWrite"],
            "cost": round(p["cost"], 6),
            "messages": p["messages"],
        })

    first_use = events[0][0] if events else 0

    return {
        "generatedAt": now_ms,
        "version": VERSION,
        "firstUse": first_use,
        "total": total,
        "ranges": ranges,
        "projects": project_list,
        "daily": daily,
        "sessionCount": len(sess_proj),
        "messageCount": len(events),
        "activeDays": len(daily),
        "dbPath": DB_PATH,
    }


def get_stats(force=False):
    now = time.time()
    if force or _cache["data"] is None or now - _cache["at"] > CACHE_TTL:
        try:
            _cache["data"] = compute_stats()
            _cache["at"] = now
        except Exception as exc:
            if _cache["data"] is not None:
                return _cache["data"]
            return {"error": str(exc), "version": VERSION}
    return _cache["data"]


# --------------------------------------------------------------------------- #
#  Local profile (username + avatar)                                           #
# --------------------------------------------------------------------------- #
def profile_file():
    return os.path.join(DATA_DIR, "profile.json")


def load_profile():
    profile = {"username": getpass.getuser() or "OpenCode 用户", "avatarFile": ""}
    try:
        with open(profile_file(), "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            if isinstance(saved.get("username"), str) and saved["username"].strip():
                profile["username"] = saved["username"].strip()
            if isinstance(saved.get("avatarFile"), str):
                profile["avatarFile"] = saved["avatarFile"]
    except Exception:
        pass
    return profile


def avatar_data_url(filename):
    if not filename:
        return ""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(path):
        return ""
    ext = os.path.splitext(filename)[1].lower()
    mime = "image/png"
    if ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif ext == ".gif":
        mime = "image/gif"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".svg":
        mime = "image/svg+xml"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:%s;base64,%s" % (mime, b64)


def save_profile(username, avatar_data_url_str):
    profile = load_profile()
    if username is not None:
        username = str(username).strip()[:32]
        if username:
            profile["username"] = username

    if avatar_data_url_str is not None:
        if avatar_data_url_str == "":
            # remove avatar
            old = profile.get("avatarFile")
            if old:
                try:
                    os.remove(os.path.join(DATA_DIR, old))
                except Exception:
                    pass
            profile["avatarFile"] = ""
        else:
            m = re.match(r"^data:image/(png|jpeg|jpg|gif|webp|svg\+xml);base64,(.+)$", avatar_data_url_str, re.S)
            if not m:
                raise ValueError("Unsupported avatar format")
            subtype = m.group(1)
            raw = base64.b64decode(m.group(2))
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError("Avatar too large (max 4MB)")
            ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(subtype, subtype)
            filename = "avatar." + ext
            with open(os.path.join(DATA_DIR, filename), "wb") as f:
                f.write(raw)
            old = profile.get("avatarFile")
            if old and old != filename:
                try:
                    os.remove(os.path.join(DATA_DIR, old))
                except Exception:
                    pass
            profile["avatarFile"] = filename

    with open(profile_file(), "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    return profile


# --------------------------------------------------------------------------- #
#  HTTP handler                                                                #
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "OpenCodeTokenDaily/" + VERSION

    def log_message(self, fmt, *args):
        pass  # keep console clean

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _serve_file(self, rel):
        rel = rel.lstrip("/")
        if rel in ("", "index.html"):
            rel = "index.html"
        path = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not path.startswith(WEB_DIR):
            self._json({"error": "forbidden"}, 403)
            return
        if not os.path.isfile(path):
            self._json({"error": "not found"}, 404)
            return
        with open(path, "rb") as f:
            body = f.read()
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, body, ctype)

    def do_GET(self):
        path = urlparse(self.path).path
        query = urlparse(self.path).query
        if path == "/api/stats":
            self._json(get_stats(force="refresh=1" in query))
        elif path == "/api/profile":
            p = load_profile()
            self._json({
                "username": p["username"],
                "avatar": avatar_data_url(p.get("avatarFile")),
                "version": VERSION,
            })
        else:
            self._serve_file(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/profile", "/api/profile/"):
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            p = save_profile(payload.get("username"), payload.get("avatar"))
            self._json({"ok": True, "username": p["username"],
                        "avatar": avatar_data_url(p.get("avatarFile"))})
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 400)


def main():
    port = int(os.environ.get("OCTD_PORT", "8765"))
    server = None
    for candidate in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        print("无法启动：没有可用端口")
        return

    url = "http://127.0.0.1:%d" % port
    print("=" * 52)
    print("  OpenCode Token Daily  " + VERSION)
    print("  本地地址: " + url)
    print("  数据库:   " + DB_PATH)
    print("  按 Ctrl+C 退出")
    print("=" * 52)

    if "--no-browser" not in sys.argv:
        threading.Timer(0.9, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
