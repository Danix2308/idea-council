#!/usr/bin/env python3
"""Read-only terminal and browser live view for a Research Council run.

It discovers copied artifacts in council.json without depending on a particular
state schema.  The optional ``say`` command is the sole writer: it appends
operator notes to a run-local live.jsonl file.
"""
from __future__ import print_function

import argparse
import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


POLL_SECONDS = 0.4
MAX_TEXT = 200 * 1024
ROLE_COLORS = {"Writer": "36", "Critic": "35", "Coordinator": "2;37", "Judge": "32", "Baseline": "34", "Host": "2"}


class CouncilArgumentParser(argparse.ArgumentParser):
    """Use the same short, predictable usage failures as council_state."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "USAGE: {}\n".format(message))


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def configure_utf8():
    """Avoid UnicodeEncodeError when CMD/PowerShell has a legacy code page."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except (OSError, ValueError):
            pass


def configure_console(no_color=False):
    """Make Windows terminals friendly to UTF-8 and ANSI where possible."""
    configure_utf8()
    color = not no_color and sys.stdout.isatty()
    if color and os.name == "nt":
        try:
            handle = ctypes.windll.kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if not ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                color = False
            elif not ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004):
                color = False
        except Exception:
            color = False
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    unicode_ok = any(name in encoding for name in ("utf", "65001"))
    return color, unicode_ok


def find_run(base=None):
    """Return (run, run_id), or (None, None) while a run has not appeared."""
    root = Path(base or Path.cwd()).resolve()
    if (root / "council.json").is_file():
        return root, root.name
    latest = root / ".council" / "LATEST"
    if not latest.is_file():
        return None, None
    try:
        run_id = latest.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None, None
    run = latest.parent / run_id
    if not run_id or not (run / "council.json").is_file():
        return None, None
    return run, run_id


def walk_artifacts(value, found, inherited=None):
    """Collect artifact-shaped dictionaries, retaining discovery order."""
    if isinstance(value, dict):
        if "path" in value and "recorded_at" in value:
            record = dict(value)
            inherited_keys = []
            for key, item in (inherited or {}).items():
                record.setdefault(key, item)
                if key not in value:
                    inherited_keys.append(key)
            record["_council_live_inherited"] = inherited_keys
            found.append(record)
        scalars = {}
        for key, item in value.items():
            if key in ("cycle", "version") and isinstance(item, (str, int, float, bool)):
                scalars[key] = item
        for child in value.values():
            walk_artifacts(child, found, scalars)
    elif isinstance(value, list):
        for child in value:
            walk_artifacts(child, found, inherited)


def artifact_role_label(path):
    """Translate a copied-artifact path to the human debate transcript."""
    p = path.replace("\\", "/").lower()
    name = p.rsplit("/", 1)[-1]
    if re.match(r"^brief/b\d+\.md$", p):
        return "Coordinator", "Brief " + name[:-3].upper()
    if (p.startswith("ledger/") or p.startswith("evidence/")) and re.match(r"^e\d+\.md$", name):
        return "Coordinator", "Evidence ledger " + name[:-3].upper()
    match = re.match(r"^outline/(o\d+)(-critic)?\.md$", p)
    if match:
        return ("Critic", "Outline {} review".format(match.group(1).upper())) if match.group(2) else ("Writer", "Outline {} proposed".format(match.group(1).upper()))
    match = re.match(r"^paragraphs/(p\d+)/v(\d+)-(draft|critique|revision|responses|check|resolve)\.md$", p)
    if match:
        para, cycle, kind = match.groups()
        labels = {
            "draft": ("Writer", "{} draft (cycle {})"), "critique": ("Critic", "{} critique"),
            "revision": ("Writer", "{} revision"), "responses": ("Writer", "{} responses to objections"),
            "check": ("Critic", "{} check"), "resolve": ("Coordinator", "{} resolution"),
        }
        role, label = labels[kind]
        return role, label.format(para.upper(), cycle)
    if p.startswith("final/"):
        if name.startswith("review-writer-"):
            return "Writer", "Final review"
        if name.startswith("review-critic-"):
            return "Critic", "Final review"
        if name.startswith("edit-"):
            return "Writer", "Final edit"
        return "Coordinator", "Final document"
    if p.startswith("baseline/"):
        return "Baseline", path
    if p.startswith("blind/"):
        return "Judge", path
    return "Coordinator", path


def safe_artifact_path(run, relative):
    candidate = Path(str(relative).replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return run / candidate


def read_artifact(run, relative, show_blind=False):
    normalized = str(relative).replace("\\", "/").lower()
    if normalized.startswith("blind/") and not show_blind:
        return "[blinded content hidden; use --show-blind]"
    target = safe_artifact_path(run, relative)
    if target is None:
        return "[unsafe artifact path omitted]"
    try:
        with target.open("rb") as handle:
            data = handle.read(MAX_TEXT + 1)
    except OSError as exc:
        return "[artifact unavailable: {}]".format(exc)
    truncated = len(data) > MAX_TEXT
    if truncated:
        data = data[:MAX_TEXT]
    text = data.decode("utf-8", errors="replace")
    return text + ("\n\n[truncated after 200 KB]" if truncated else "")


def artifact_event(run, record, sequence, show_blind=False):
    path = str(record.get("path", ""))
    role, label = artifact_role_label(path)
    details = {}
    inherited = set(record.get("_council_live_inherited", ()))
    for key, value in record.items():
        if key in ("path", "sha256", "recorded_at", "_council_live_inherited") or key in inherited:
            continue
        if key.lower() in ("verdict", "objections", "version", "cycle", "check_verdict") and isinstance(value, (str, int, float, bool)):
            details[key.replace("check_", "")] = value
    return {"kind": "artifact", "role": role, "label": label, "path": path,
            "ts": str(record.get("recorded_at", "")), "text": read_artifact(run, path, show_blind),
            "details": details, "sequence": sequence}


def artifact_kind_rank(path):
    """Break same-second artifact ties in the Council's natural work order."""
    normalized = str(path).replace("\\", "/").lower()
    outline = re.match(r"^outline/o\d+(-critic)?\.md$", normalized)
    if outline:
        return 0 if not outline.group(1) else 1
    match = re.match(r"^paragraphs/p\d+/v\d+-(draft|critique|responses|revision|check|resolve)\.md$", normalized)
    if match:
        return {"draft": 0, "critique": 1, "responses": 2, "revision": 3,
                "check": 4, "resolve": 5}[match.group(1)]
    return 50


def artifact_sort_key(run, record, discovery):
    target = safe_artifact_path(run, record.get("path", ""))
    try:
        modified = target.stat().st_mtime_ns if target else -1
    except OSError:
        modified = -1
    return (str(record.get("recorded_at", "")), modified,
            artifact_kind_rank(record.get("path", "")), discovery)


def turn_from_next(text):
    """Map council_state next output into a compact, displayable turn."""
    raw = (text or "").strip()
    lower = raw.lower()
    if any(line.strip() == "DONE" for line in raw.splitlines()):
        return {"role": "Coordinator", "activity": "run finished", "finished": True}
    mappings = [
        (r"outline\s+propose", "Writer", "drafting the outline"),
        (r"outline\s+review", "Critic", "reviewing the outline"),
        (r"para\s+draft\s+(p\d+)", "Writer", "drafting {}"),
        (r"para\s+critique\s+(p\d+)", "Critic", "critiquing {}"),
        (r"para\s+revise\s+(p\d+)", "Writer", "revising {}"),
        (r"para\s+check\s+(p\d+)", "Critic", "checking {}"),
        (r"final\s+review\s+--role\s+(writer|critic)", None, "final review"),
    ]
    for pattern, role, activity in mappings:
        match = re.search(pattern, lower)
        if match:
            if role is None:
                role = match.group(1).title()
            return {"role": role, "activity": activity.format(match.group(1).upper()) if "{}" in activity else activity, "finished": False}
    if any(word in lower for word in ("baseline", "blind")):
        return {"role": "Judge" if "judge" in lower or "blind" in lower else "Baseline", "activity": "performing baseline comparison", "finished": False}
    return {"role": "Coordinator", "activity": "coordinating the next step", "finished": False}


def current_turn(run):
    script = Path(__file__).resolve().parent / "council_state.py"
    try:
        result = subprocess.run([sys.executable, str(script), "next", "--dir", str(run)], text=True,
                                capture_output=True, timeout=10, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None
    return turn_from_next(result.stdout) if result.returncode == 0 else None


def parse_host_line(line):
    """Return display records from one defensive Codex or Claude JSONL line."""
    try:
        value = json.loads(line)
    except (TypeError, ValueError):
        return []
    result = []
    if value.get("type") == "response_item":
        payload = value.get("payload", {})
        kind = payload.get("type")
        if kind == "reasoning":
            return [("thinking...", "reasoning")]
        if kind in ("function_call", "custom_tool_call"):
            arg = payload.get("arguments", payload.get("input", ""))
            return [("{} {}".format(payload.get("name", "tool"), compact_value(arg)), "tool")]
        if kind == "message" and payload.get("role") == "assistant":
            text = content_text(payload.get("content", payload.get("text", "")))
            return [(text, "message")] if text else []
    if value.get("type") == "assistant":
        contents = value.get("message", {}).get("content", [])
        if not isinstance(contents, list):
            contents = [contents]
        for item in contents:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                result.append((str(item["text"]), "message"))
            elif item.get("type") == "tool_use":
                result.append(("{} {}".format(item.get("name", "tool"), compact_value(item.get("input", ""))), "tool"))
    return result


def content_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item.get("text", "")) for item in value if isinstance(item, dict) and item.get("text"))
    return ""


def compact_value(value, limit=180):
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            value = str(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] + ("..." if len(value) > limit else "")


class HostTailer(object):
    """Best-effort tailer for recent Codex and Claude Code session transcripts."""
    def __init__(self, project_root, any_host=False):
        self.project_root, self.any_host = str(Path(project_root).resolve()), any_host
        home = Path.home()
        self.codex_root = home / ".codex" / "sessions"
        self.claude_root = home / ".claude" / "projects"
        self.started, self.known, self.offsets, self.codex_cwds = time.time(), set(), {}, {}
        self.last_scan = 0
        # Files already on disk belong to an existing host session.  Do not
        # replay them; new session files found by later scans begin at offset 0.
        for path in self.candidates():
            try:
                self.known.add(path)
                self.offsets[path] = path.stat().st_size
                if self.is_codex_path(path):
                    with path.open("r", encoding="utf-8", errors="replace") as handle:
                        for line in handle:
                            try:
                                item = json.loads(line)
                            except ValueError:
                                continue
                            if item.get("type") == "session_meta":
                                self.codex_cwds[path] = str(item.get("payload", {}).get("cwd", ""))
                                break
            except OSError:
                pass

    def candidates(self):
        return list(self.codex_root.glob("**/rollout-*.jsonl")) + list(self.claude_root.glob("**/*.jsonl"))

    @staticmethod
    def is_under(path, root):
        try:
            return os.path.commonpath((os.path.normcase(str(Path(path).resolve())),
                                       os.path.normcase(str(Path(root).resolve())))) == os.path.normcase(str(Path(root).resolve()))
        except (OSError, ValueError):
            return False

    def is_codex_path(self, path):
        return self.is_under(path, self.codex_root)

    def is_claude_path(self, path):
        return self.is_under(path, self.claude_root)

    def codex_matches_project(self, path):
        cwd = self.codex_cwds.get(path, "")
        return os.path.normcase(os.path.normpath(cwd)) == os.path.normcase(os.path.normpath(self.project_root))

    def allowed_claude(self, path):
        expected = re.sub(r"[^a-zA-Z0-9]", "-", self.project_root).strip("-").lower()
        return expected in str(path).lower()

    def poll(self):
        if time.time() - self.last_scan < 2:
            return []
        self.last_scan = time.time()
        out = []
        for path in self.candidates():
            try:
                recent = path.stat().st_mtime >= self.started - 600
            except OSError:
                continue
            if not recent:
                continue
            new = path not in self.known
            if new:
                self.known.add(path)
                if not self.any_host and self.is_claude_path(path) and not self.allowed_claude(path):
                    self.offsets[path] = path.stat().st_size
                    continue
                self.offsets[path] = 0 if new else path.stat().st_size
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(self.offsets.get(path, 0)); lines = handle.readlines(); self.offsets[path] = handle.tell()
            except OSError:
                continue
            for line in lines:
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if parsed.get("type") == "session_meta":
                    self.codex_cwds[path] = str(parsed.get("payload", {}).get("cwd", ""))
                    continue
                if not self.any_host and self.is_codex_path(path) and not self.codex_matches_project(path):
                    continue
                for text, kind in parse_host_line(line):
                    out.append({"kind": "host", "role": "Host", "label": path.stem[-18:], "text": compact_value(text, 240),
                                "ts": utc_now(), "details": {"activity": kind}})
        return out


class CouncilWatcher(object):
    def __init__(self, base=None, show_blind=False, host=False, host_any=False):
        self.base = Path(base or Path.cwd()).resolve(); self.show_blind = show_blind
        self.run = self.run_id = None; self.events = []; self.seen = set(); self.sequence = 0
        self.state_mtime = None; self.note_offset = 0; self.turn = None; self.turn_started = time.time()
        self.host = HostTailer(self.base, host_any) if host else None

    def add(self, event):
        self.sequence += 1
        event["sequence"] = self.sequence
        event["run_id"] = self.run_id
        self.events.append(event)
        if event.get("kind") in ("artifact", "system") or (event.get("kind") == "note" and event.get("details", {}).get("working")):
            self.turn_started = self.parse_timestamp(event.get("ts")) or time.time()
        return event

    @staticmethod
    def parse_timestamp(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    def refresh_turn(self):
        if not self.run:
            self.turn = {"role": "Coordinator", "activity": "waiting for a run", "finished": False}
        else:
            turn = current_turn(self.run)
            if turn:
                self.turn = turn

    def poll_notes(self, out):
        path = self.run / "live.jsonl"
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self.note_offset)
                lines = handle.readlines(); self.note_offset = handle.tell()
        except OSError:
            return
        for line in lines:
            try:
                note = json.loads(line)
            except ValueError:
                continue
            if not isinstance(note, dict) or not note.get("text"):
                continue
            role = str(note.get("role", "coordinator")).title()
            event = {"kind": "note", "role": role, "label": "Live note", "text": str(note["text"]),
                     "ts": str(note.get("ts", utc_now())), "details": {"working": bool(note.get("working"))}}
            out.append(self.add(event))

    def poll(self):
        out = []
        run, run_id = find_run(self.base)
        if run != self.run:
            old = self.run
            self.run, self.run_id = run, run_id
            self.events, self.seen, self.sequence, self.state_mtime, self.note_offset = [], set(), 0, None, 0
            self.turn_started = time.time()
            if old is not None and run is not None:
                out.append(self.add({"kind": "system", "role": "Coordinator", "label": "New run started", "text": "New run started", "ts": utc_now(), "details": {}}))
        if not self.run:
            self.refresh_turn()
            return out
        state_path = self.run / "council.json"
        try:
            mtime = state_path.stat().st_mtime_ns
        except OSError:
            return out
        changed = mtime != self.state_mtime
        if changed:
            self.state_mtime = mtime
            try:
                state = json.loads(state_path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                state = None
            if state is not None:
                records = []; walk_artifacts(state, records)
                ordered = sorted(enumerate(records), key=lambda pair: artifact_sort_key(self.run, pair[1], pair[0]))
                for _, record in ordered:
                    key = (str(record.get("path", "")), str(record.get("sha256", "")))
                    if key not in self.seen:
                        self.seen.add(key); out.append(self.add(artifact_event(self.run, record, self.sequence + 1, self.show_blind)))
        before = len(out); self.poll_notes(out)
        if changed or len(out) != before or self.turn is None:
            self.refresh_turn()
        if self.host:
            for event in self.host.poll():
                out.append(self.add(event))
        return out

    def snapshot(self):
        turn = dict(self.turn or {"role": "Coordinator", "activity": "waiting for a run", "finished": False})
        turn["started_at"] = datetime.fromtimestamp(self.turn_started, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        turn["run_id"] = self.run_id
        return {"run_id": self.run_id, "events": list(self.events), "turn": turn}


def event_header(event):
    try:
        stamp = datetime.fromisoformat(event.get("ts", "").replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except ValueError:
        stamp = time.strftime("%H:%M:%S")
    details = "".join("  [{}: {}]".format(k, v) for k, v in event.get("details", {}).items() if v not in (None, ""))
    return "{}  {:11}  {}{}".format(stamp, event.get("role", "Coordinator").upper(), event.get("label", ""), details)


def print_event(event, color, compact=False):
    header = event_header(event)
    code = ROLE_COLORS.get(event.get("role"))
    print(("\033[{}m{}\033[0m".format(code, header) if color and code else header))
    lines = str(event.get("text", "")).splitlines() or [""]
    if compact and len(lines) > 6:
        lines = lines[:6] + ["[{} more lines; use without --compact to show all]".format(len(str(event.get("text", "")).splitlines()) - 6)]
    for line in lines:
        print("  " + line)
    print("")


def status_line(watcher, unicode_ok):
    turn = watcher.snapshot()["turn"]
    elapsed = max(0, int(time.time() - watcher.turn_started)); marker = "✍" if unicode_ok else ">"
    separator = "·" if unicode_ok else "-"
    return "{} {} is {} {} {:02d}:{:02d}".format(marker, turn["role"], turn["activity"], separator, elapsed // 60, elapsed % 60)


def watch_terminal(args):
    color, unicode_ok = configure_console(args.no_color)
    watcher = CouncilWatcher(args.dir, args.show_blind, args.host, args.host_any)
    printed, status, initialised = 0, False, False
    try:
        while True:
            watcher.poll()
            if not initialised:
                initialised = True
                if args.no_replay:
                    printed = len(watcher.events)
            events = watcher.events
            if args.once:
                for event in events:
                    print_event(event, color, args.compact)
                snapshot = watcher.snapshot()
                separator = "—" if unicode_ok else "-"
                print("CURRENT TURN: {} {} {}".format(snapshot["turn"]["role"], separator, snapshot["turn"]["activity"]))
                return 0
            if not watcher.run and not printed:
                print("Waiting for a Council run in {}\\.council ...".format(watcher.base)); printed = len(watcher.events)
            for event in events[printed:]:
                if status:
                    # Spaces work when ANSI clear-line is unavailable or --no-color
                    # was requested, so transcript blocks never overwrite the spinner.
                    print("\r" + (" " * 160) + "\r", end="")
                print_event(event, color, args.compact); status = False
            printed = len(events)
            if sys.stdout.isatty():
                print("\r" + status_line(watcher, unicode_ok), end="", flush=True); status = True
            time.sleep(0.2)
    except KeyboardInterrupt:
        if status:
            print("\r" + (" " * 160) + "\r")
        return 0


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Live debate</title><style>
:root{--bg:#f7f5f0;--card:#fff;--ink:#252525;--muted:#6b6b6b;--line:#ddd6ca;--writer:#087e8b;--critic:#9d4edd;--system:#56616f}@media(prefers-color-scheme:dark){:root{--bg:#17181b;--card:#22242a;--ink:#eee;--muted:#a9adb5;--line:#3a3d44}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px system-ui,sans-serif}.top{position:sticky;top:0;z-index:3;padding:14px max(16px,calc((100vw - 1080px)/2));background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;flex-wrap:wrap}.top h1{font-size:19px;margin:0 12px 0 0}.pill,.connection,.chip,button{border:1px solid var(--line);border-radius:999px;padding:5px 10px;background:var(--card);color:var(--ink);font:inherit;font-size:12px}.connection{margin-left:auto}.live{color:#16803a}.finished{color:var(--muted)}.filters{display:flex;gap:6px;overflow:auto;max-width:100%}.chip.active{background:var(--ink);color:var(--bg)}main{max-width:880px;margin:auto;padding:16px 12px 112px}.event{display:flex;margin:14px 0;animation:in .25s ease-out}.bubble{max-width:min(86%,690px);padding:12px 14px;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:0 1px 2px #0000000b}.writer{justify-content:flex-start}.critic{justify-content:flex-end}.critic .bubble{border-color:color-mix(in srgb,var(--critic) 35%,var(--line))}.writer .bubble{border-color:color-mix(in srgb,var(--writer) 35%,var(--line))}.system{justify-content:center}.system .bubble{max-width:92%;background:color-mix(in srgb,var(--card) 85%,var(--bg));border-radius:10px}.meta{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:12px;margin-bottom:7px}.badge{font-weight:700;color:var(--system)}.writer .badge{color:var(--writer)}.critic .badge{color:var(--critic)}pre{white-space:pre-wrap;overflow:auto;background:#00000012;padding:8px;border-radius:6px}p{margin:.35em 0}.more{margin-top:8px}a{color:inherit}#typing{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(840px,calc(100% - 24px));padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:14px 14px 0 0;box-shadow:0 -4px 16px #00000012}#typing.typing-writer{left:max(12px,calc((100% - 840px)/2));transform:none}#typing.typing-critic{left:auto;right:max(12px,calc((100% - 840px)/2));transform:none}.dots:after{content:' ...';animation:d 1.2s infinite}@keyframes d{50%{opacity:.25}}@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}#new{display:none;position:fixed;bottom:70px;left:50%;transform:translateX(-50%)}#host{display:none;position:fixed;right:12px;bottom:12px;width:min(420px,calc(100% - 24px));max-height:42vh;overflow:auto;background:var(--card);border:1px solid var(--line);padding:10px;font:12px ui-monospace,monospace;color:var(--muted)}.hostline{margin:0 0 8px}.hidden{display:none}@media(max-width:430px){.bubble{max-width:94%}.top h1{width:100%}.connection{margin-left:0}#typing.typing-writer{left:12px}#typing.typing-critic{right:12px}}
</style></head><body><header class="top"><h1>Live debate</h1><span id="run" class="pill">waiting</span><span id="status" class="pill">waiting for run</span><button id="hostbtn">Host activity</button><button id="auto">Auto-scroll: on</button><span id="connection" class="connection">connecting</span><div id="filters" class="filters"><button class="chip active" data-filter="All">All</button></div></header><main id="feed"></main><button id="new">New messages ↓</button><aside id="host"></aside><div id="typing"><span class="dots" id="typingtext">Coordinator is waiting for a run</span> <span id="timer"></span></div><script>
const feed=document.querySelector('#feed'),host=document.querySelector('#host'),filters=document.querySelector('#filters'),typing=document.querySelector('#typing'),newButton=document.querySelector('#new');
let events=[],filter='All',auto=true,turn={role:'Coordinator',activity:'waiting for a run',started_at:null},seen=new Set(),activeRun=null,started=Date.now(),previousScrollY=window.scrollY;
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function md(s){s=esc(String(s).trim());s=s.replace(/```([\s\S]*?)```/g,'<pre>$1</pre>').replace(/^#{1,6} (.*)$/gm,'<strong>$1</strong>').replace(/\*\*(.*?)\*\*/g,'<b>$1</b>').replace(/\*(.*?)\*/g,'<i>$1</i>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\[(.*?)\]\([^)]*\)/g,'$1');return s.split(/\n\n+/).filter(x=>x.trim()).map(x=>x.startsWith('- ')?'<ul>'+x.split('\n').filter(y=>y.trim()).map(y=>'<li>'+y.slice(2)+'</li>').join('')+'</ul>':x.match(/^\d+\. /)?'<ol>'+x.split('\n').filter(y=>y.trim()).map(y=>'<li>'+y.replace(/^\d+\. /,'')+'</li>').join('')+'</ol>':'<p>'+x.replace(/\n/g,'<br>')+'</p>').join('')}
function para(e){let m=(e.label+' '+e.path).match(/\b(P\d+)\b/i);if(m)return m[1].toUpperCase();if(/outline/i.test(e.label))return'Outline';if(/final/i.test(e.label))return'Final';return'Other'}function chips(){let names=['All',...new Set(events.map(para))];filters.innerHTML=names.map(n=>`<button class="chip ${n===filter?'active':''}" data-filter="${n}">${n}</button>`).join('');filters.querySelectorAll('button').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;render()})}
function atBottom(){return window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-8}function setAuto(value){auto=value;document.querySelector('#auto').textContent='Auto-scroll: '+(auto?'on':'off');if(auto||atBottom())newButton.style.display='none'}function resetForRun(runId){if(!runId||runId===activeRun)return;activeRun=runId;events=[];seen=new Set();host.innerHTML='';filter='All';feed.innerHTML=''}
function eventNode(e){let side=e.role==='Writer'?'writer':e.role==='Critic'?'critic':'system',text=e.text||'',lines=text.split('\n');let body=md(lines.slice(0,18).join('\n'));if(lines.length>18)body+='<button class="more">Show more</button><div class="hidden full">'+md(text)+'</div>';let d=document.createElement('article');d.className='event '+side;d.innerHTML=`<div class="bubble"><div class="meta"><span class="badge">${esc(e.role)}</span><b>${esc(e.label)}</b><span>${esc((e.ts||'').slice(11,19))}</span></div><div>${body}</div></div>`;let b=d.querySelector('.more');if(b)b.onclick=()=>{d.querySelector('.full').classList.remove('hidden');b.remove()};return d}function render(){feed.innerHTML='';events.filter(e=>filter==='All'||para(e)===filter).filter(e=>e.kind!=='host').forEach(e=>feed.append(eventNode(e)));chips();if(auto){window.scrollTo(0,document.documentElement.scrollHeight);newButton.style.display='none'}}
function add(e){if(e.kind==='turn'){setTurn(e);return}if(e.label==='New run started'||(e.run_id&&e.run_id!==activeRun))resetForRun(e.run_id);let key=`${e.run_id||activeRun||''}:${e.sequence||''}`;if(e.sequence&&seen.has(key))return;if(e.sequence)seen.add(key);events.push(e);if(e.kind==='host'){host.insertAdjacentHTML('beforeend',`<p class="hostline">[${esc(e.label)}] ${esc(e.text)}</p>`);return}render()}function setTurn(t){resetForRun(t.run_id);turn=t;started=t.started_at?Date.parse(t.started_at):Date.now();if(t.run_id)document.querySelector('#run').textContent=t.run_id;document.querySelector('#status').textContent=t.finished?'finished':'live';document.querySelector('#status').className='pill '+(t.finished?'finished':'live');typing.className=t.finished?'hidden':'typing-'+(t.role==='Writer'?'writer':t.role==='Critic'?'critic':'system');document.querySelector('#typingtext').textContent=`${t.role} is ${t.activity}`;}
function timer(){if(turn.finished){document.querySelector('#timer').textContent='';return}let s=Math.max(0,Math.floor((Date.now()-started)/1000));document.querySelector('#timer').textContent=`${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`}setInterval(timer,250);document.querySelector('#hostbtn').onclick=()=>host.style.display=host.style.display==='block'?'none':'block';document.querySelector('#auto').onclick=()=>setAuto(!auto);window.addEventListener('scroll',()=>{let y=window.scrollY;if(atBottom())setAuto(true);else if(y<previousScrollY&&window.innerHeight+y<document.documentElement.scrollHeight-120)setAuto(false);previousScrollY=y});newButton.onclick=()=>{setAuto(true);window.scrollTo(0,document.documentElement.scrollHeight)};
function connect(){let s=new EventSource('/events');s.onopen=()=>document.querySelector('#connection').textContent='connected';s.onerror=()=>document.querySelector('#connection').textContent='reconnecting';s.addEventListener('event',x=>add(JSON.parse(x.data)));s.addEventListener('turn',x=>setTurn(JSON.parse(x.data)))}connect();
</script></body></html>'''


class LiveServer(object):
    def __init__(self, watcher):
        self.watcher, self.clients, self.lock, self.stop = watcher, [], threading.Lock(), threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _broadcast(self, event_type, data):
        with self.lock:
            for client in list(self.clients):
                try: client.put_nowait((event_type, data))
                except queue.Full: self.clients.remove(client)

    def _loop(self):
        previous = None
        while not self.stop.is_set():
            for event in self.watcher.poll(): self._broadcast("event", event)
            snapshot = self.watcher.snapshot()["turn"]
            snapshot["started_at"] = self.watcher.snapshot()["turn"].get("started_at")
            marker = json.dumps(snapshot, sort_keys=True)
            if marker != previous: self._broadcast("turn", snapshot); previous = marker
            self.stop.wait(POLL_SECONDS)

    def start(self):
        self.watcher.poll(); self.thread.start()


def serve(args):
    watcher = CouncilWatcher(args.dir, args.show_blind, args.host, args.host_any); live = LiveServer(watcher); live.start()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *values): pass
        def send_body(self, body, content_type):
            encoded = body.encode("utf-8"); self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/": return self.send_body(HTML, "text/html; charset=utf-8")
            if route == "/state": return self.send_body(json.dumps(watcher.snapshot(), ensure_ascii=False), "application/json; charset=utf-8")
            if route != "/events": self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache"); self.send_header("Connection", "keep-alive"); self.end_headers()
            client = queue.Queue(maxsize=200)
            try:
                # Enroll before snapshotting: broadcasts after this point queue behind
                # the replay rather than vanishing in the replay/register gap.
                with live.lock:
                    live.clients.append(client)
                    snapshot = watcher.snapshot()
                for event in snapshot["events"]:
                    self.wfile.write(sse("event", event)); self.wfile.flush()
                self.wfile.write(sse("turn", snapshot["turn"])); self.wfile.flush()
                while True:
                    try: kind, data = client.get(timeout=15); self.wfile.write(sse(kind, data))
                    except queue.Empty: self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError): pass
            finally:
                with live.lock:
                    if client in live.clients: live.clients.remove(client)
    port = args.port
    server = None
    for candidate in range(port, port + 21):
        try: server = ThreadingHTTPServer(("127.0.0.1", candidate), Handler); break
        except OSError:
            if port == 0: break
    if server is None:
        print("Could not bind a port in {}-{}".format(port, port + 20), file=sys.stderr); return 2
    url = "http://127.0.0.1:{}/".format(server.server_address[1]); print(url, flush=True)
    if args.open: webbrowser.open(url)
    try: server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt: pass
    finally: live.stop.set(); server.server_close()
    return 0


def sse(kind, data):
    encoded = json.dumps(data, ensure_ascii=False).replace("\n", "\\n")
    return "id: {}\nevent: {}\ndata: {}\n\n".format(data.get("sequence", 0) if isinstance(data, dict) else 0, kind, encoded).encode("utf-8")


def say(args):
    run, _ = find_run(args.dir)
    if not run:
        print("Waiting for a Council run in {}\\.council ...".format(Path(args.dir or Path.cwd()).resolve()), file=sys.stderr); return 2
    text = Path(args.file).read_text(encoding="utf-8", errors="replace") if args.file else args.text
    entry = {"ts": utc_now(), "role": args.role, "text": text, "working": bool(args.working)}
    with (run / "live.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print("Noted"); return 0


def parser():
    root = CouncilArgumentParser(description=__doc__); sub = root.add_subparsers(dest="command", required=True)
    def common(p, host=False):
        p.add_argument("--dir"); p.add_argument("--show-blind", action="store_true")
        if host: p.add_argument("--host", action="store_true"); p.add_argument("--host-any", action="store_true")
    watch = sub.add_parser("watch"); common(watch, True); watch.add_argument("--no-replay", action="store_true"); watch.add_argument("--compact", action="store_true"); watch.add_argument("--no-color", action="store_true"); watch.add_argument("--once", action="store_true"); watch.set_defaults(func=watch_terminal)
    serve_p = sub.add_parser("serve"); common(serve_p, True); serve_p.add_argument("--port", type=int, default=8765); serve_p.add_argument("--open", action="store_true"); serve_p.set_defaults(func=serve)
    note = sub.add_parser("say"); note.add_argument("--role", required=True, choices=("writer", "critic", "coordinator", "judge")); note.add_argument("--working", action="store_true"); note.add_argument("--dir"); group = note.add_mutually_exclusive_group(required=True); group.add_argument("--text"); group.add_argument("--file"); note.set_defaults(func=say)
    return root


def main(argv=None):
    configure_utf8()
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
