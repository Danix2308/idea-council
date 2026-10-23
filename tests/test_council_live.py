"""Contract tests for the standalone Research Council live viewer."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "research-council" / "scripts" / "council_live.py"
SPEC = importlib.util.spec_from_file_location("council_live", SCRIPT)
LIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIVE)


class CouncilLiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / ".council" / "run-x"
        self.run.mkdir(parents=True)
        (self.root / ".council" / "LATEST").write_text("run-x\n", encoding="utf-8")
        self.artifact("brief/B1.md", "Brief text")
        self.artifact("paragraphs/P3/v1-draft.md", "Writer draft text")
        self.artifact("paragraphs/P3/v1-critique.md", "Critic critique text")
        self.artifact("blind/X.md", "secret blind text")
        self.write_state()

    def tearDown(self):
        self.temp.cleanup()

    def artifact(self, name, text):
        path = self.run / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_state(self, extra=None):
        records = [
            {"path": "paragraphs/P3/v1-critique.md", "sha256": "c", "recorded_at": "2026-01-01T00:00:03Z", "objections": 2},
            {"path": "brief/B1.md", "sha256": "b", "recorded_at": "2026-01-01T00:00:01Z"},
            {"path": "paragraphs/P3/v1-draft.md", "sha256": "d", "recorded_at": "2026-01-01T00:00:02Z"},
            {"path": "blind/X.md", "sha256": "x", "recorded_at": "2026-01-01T00:00:04Z"},
        ]
        if extra:
            records.append(extra)
        (self.run / "council.json").write_text(json.dumps({"nested": {"artifacts": records}}), encoding="utf-8")

    def call(self, *parts):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, parts)], text=True,
                              capture_output=True, timeout=8)

    def test_mapping_replay_and_blind_content(self):
        self.assertEqual(LIVE.artifact_role_label("outline/O2-critic.md"), ("Critic", "Outline O2 review"))
        self.assertEqual(LIVE.artifact_role_label("paragraphs/P4/v2-responses.md"), ("Writer", "P4 responses to objections"))
        watcher = LIVE.CouncilWatcher(self.root)
        watcher.poll()
        self.assertEqual([event["label"] for event in watcher.events][:3],
                         ["Brief B1", "P3 draft (cycle 1)", "P3 critique"])
        self.assertIn("blinded content hidden", watcher.events[-1]["text"])
        shown = LIVE.CouncilWatcher(self.root, show_blind=True)
        shown.poll()
        self.assertIn("secret blind text", shown.events[-1]["text"])

    def test_same_second_order_and_no_parent_detail_leakage(self):
        draft = self.artifact("paragraphs/P1/v1-draft.md", "draft")
        critique = self.artifact("paragraphs/P1/v1-critique.md", "critique")
        outline = self.artifact("outline/O1.md", "P1: opening")
        review = self.artifact("outline/O1-critic.md", "ready")
        same_time = 1700000000000000000
        for artifact in (draft, critique, outline, review):
            os.utime(str(artifact), ns=(same_time, same_time))
        state = {
            "outlines": [{"version": "O1", "verdict": "ready", "artifact": {"path": "outline/O1.md", "sha256": "o", "recorded_at": "2026-02-01T00:00:00Z"},
                          "review": {"path": "outline/O1-critic.md", "sha256": "or", "recorded_at": "2026-02-01T00:00:00Z"}}],
            "paragraphs": {"P1": {"history": [{"cycle": 1, "objections": 2,
                "draft": {"path": "paragraphs/P1/v1-draft.md", "sha256": "d1", "recorded_at": "2026-02-01T00:00:00Z"},
                "critique": {"path": "paragraphs/P1/v1-critique.md", "sha256": "c1", "recorded_at": "2026-02-01T00:00:00Z"}}]}}}
        (self.run / "council.json").write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        watcher = LIVE.CouncilWatcher(self.root)
        watcher.poll()
        labels = [event["label"] for event in watcher.events]
        self.assertLess(labels.index("Outline O1 proposed"), labels.index("Outline O1 review"))
        self.assertLess(labels.index("P1 draft (cycle 1)"), labels.index("P1 critique"))
        draft_event = next(event for event in watcher.events if event["label"] == "P1 draft (cycle 1)")
        outline_event = next(event for event in watcher.events if event["label"] == "Outline O1 proposed")
        self.assertNotIn("objections", draft_event["details"])
        self.assertNotIn("cycle", draft_event["details"])
        self.assertNotIn("verdict", outline_event["details"])

    def test_say_and_watch_once(self):
        result = self.call("say", "--dir", self.root, "--role", "writer", "--working", "--text", "working now")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.run / "live.jsonl").read_text(encoding="utf-8"))["role"], "writer")
        result = self.call("watch", "--dir", self.root, "--once", "--no-color")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("P3 draft", result.stdout)
        self.assertIn("Writer draft text", result.stdout)
        self.assertIn("P3 critique", result.stdout)
        self.assertIn("Critic critique text", result.stdout)

    def test_host_parser_and_turn_text(self):
        tool = json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "search", "input": {"q": "term"}}})
        assistant = json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"text": "Codex says hello"}]}})
        user = json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"text": "hidden"}]}})
        claude = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}, {"type": "tool_use", "name": "Read", "input": {"path": "x"}}]}})
        self.assertIn("search", LIVE.parse_host_line(tool)[0][0])
        self.assertEqual(LIVE.parse_host_line(assistant)[0][0], "Codex says hello")
        self.assertEqual(LIVE.parse_host_line(user), [])
        self.assertEqual(LIVE.parse_host_line(claude)[0][0], "hello")
        self.assertIn("Read", LIVE.parse_host_line(claude)[1][0])
        self.assertEqual(LIVE.parse_host_line("garbage"), [])
        self.assertTrue(LIVE.turn_from_next("DONE\n")["finished"])
        self.assertFalse(LIVE.turn_from_next("not done yet")["finished"])

    def test_host_cwd_filter_and_host_any(self):
        with tempfile.TemporaryDirectory() as home_text:
            home = Path(home_text)
            matching = home / ".codex" / "sessions" / "a" / "rollout-match.jsonl"
            other = home / ".codex" / "sessions" / "b" / "rollout-other.jsonl"
            for path, cwd in ((matching, self.root), (other, home / "other-project")):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"type": "session_meta", "payload": {"cwd": str(cwd)}}) + "\n", encoding="utf-8")
            with mock.patch.object(LIVE.Path, "home", return_value=home):
                tailer = LIVE.HostTailer(self.root)
                with matching.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "match", "input": {}}}) + "\n")
                with other.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "other", "input": {}}}) + "\n")
                shown = tailer.poll()
                self.assertEqual(len(shown), 1)
                self.assertIn("match", shown[0]["text"])
                any_tailer = LIVE.HostTailer(self.root, any_host=True)
                with other.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "any", "input": {}}}) + "\n")
                self.assertIn("any", any_tailer.poll()[0]["text"])

    def test_host_event_does_not_reset_turn_timer(self):
        watcher = LIVE.CouncilWatcher(self.root)
        watcher.turn_started = 123.0
        watcher.add({"kind": "host", "role": "Host", "label": "session", "text": "tool", "ts": "2026-01-01T00:00:00Z", "details": {}})
        self.assertEqual(watcher.turn_started, 123.0)
        watcher.add({"kind": "note", "role": "Writer", "label": "Live note", "text": "working", "ts": "2026-01-01T00:00:01Z", "details": {"working": True}})
        self.assertNotEqual(watcher.turn_started, 123.0)

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_embedded_javascript_parses(self):
        match = re.search(r"<script>([\s\S]*)</script>", LIVE.HTML)
        self.assertIsNotNone(match)
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
            script_path = Path(handle.name)
            handle.write(match.group(1))
        try:
            result = subprocess.run(["node", "--check", str(script_path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            script_path.unlink()

    def test_server_state_and_sse_update(self):
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "serve", "--dir", str(self.root), "--port", "0"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            url = proc.stdout.readline().strip()
            self.assertTrue(url.startswith("http://127.0.0.1:"))
            page = urllib.request.urlopen(url, timeout=4).read().decode()
            self.assertIn("Live debate", page)
            state = json.loads(urllib.request.urlopen(url + "state", timeout=4).read().decode())
            self.assertGreaterEqual(len(state["events"]), 4)
            stream = urllib.request.urlopen(url + "events", timeout=4)
            self.assertTrue(stream.readline().decode().startswith("id:"))
            self.artifact("final/D1.md", "final")
            self.write_state({"path": "final/D1.md", "sha256": "final", "recorded_at": "2026-01-01T00:00:05Z"})
            deadline, data = time.time() + 4, ""
            while time.time() < deadline and "Final document" not in data:
                data += stream.readline().decode(errors="replace")
            self.assertIn("Final document", data)
            stream.close()
        finally:
            proc.terminate()
            proc.wait(timeout=4)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
