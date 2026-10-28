"""CLI contract tests for the persistent Research Council state tool."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "research-council" / "scripts" / "council_state.py"
KEYS = ("requirements", "foundations", "sources", "claims", "citations", "discussion", "analysis", "feedback", "final_artifact")


class CouncilStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.write("brief.md", "A brief.\n")
        self.write("review.md", "Substantive review.\n")
        self.write("draft.md", "Draft prose.\n")
        self.write("critique.md", "Critique prose.\n")
        self.write("revision.md", "Revised prose.\n")
        self.write("responses.md", "Responses.\n")
        self.write("check.md", "Checked prose.\n")
        self.write("final.md", "Whole-document review.\n")
        self.write("document.md", "Assembled document with references.\n")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def call(self, *parts, code=0):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, parts)], cwd=str(self.root), text=True, capture_output=True)
        self.assertEqual(result.returncode, code, msg="stdout:\n{}\nstderr:\n{}".format(result.stdout, result.stderr))
        return result

    def init(self, extra=()):
        self.call("init", "--brief-file", self.root / "brief.md", "--root", self.root, *extra)

    def state(self):
        latest = (self.root / ".council" / "LATEST").read_text(encoding="utf-8").strip()
        return json.loads((self.root / ".council" / latest / "council.json").read_text(encoding="utf-8"))

    def outline(self, text="P1: opening\nP2: middle\nP3: close\n", affects=None):
        file = self.write("outline.md", text)
        args = ["outline", "propose", "--file", file]
        if affects is not None:
            args += ["--affects", affects]
        self.call(*args)

    def ready(self, version="O1"):
        self.call("outline", "review", "--version", version, "--verdict", "ready", "--file", self.root / "review.md")

    def cycle(self, paragraph, objections=1, verdict="reviewed"):
        version = self.state()["outlines"][-1]["version"]
        self.call("para", "draft", paragraph, "--file", self.root / "draft.md", "--outline-version", version)
        self.call("para", "critique", paragraph, "--file", self.root / "critique.md", "--objections", objections)
        if objections:
            self.call("para", "revise", paragraph, "--file", self.root / "revision.md", "--responses-file", self.root / "responses.md")
        self.call("para", "check", paragraph, "--verdict", verdict, "--file", self.root / "check.md")

    def reviewed_document(self):
        self.init(); self.outline(); self.ready()
        self.cycle("P1"); self.cycle("P2", 0); self.cycle("P3")
        self.call("final", "document", "--file", self.root / "document.md")
        self.call("final", "review", "--role", "writer", "--file", self.root / "final.md")
        self.call("final", "review", "--role", "critic", "--file", self.root / "final.md")

    def pass_readiness(self):
        for key in KEYS:
            args = ["readiness", "set", key, "N/A" if key == "feedback" else "PASS", "--evidence", "checked"]
            if key == "feedback": args += ["--reason", "no applicable feedback"]
            self.call(*args)

    def test_01_full_happy_path(self):
        self.reviewed_document(); self.pass_readiness()
        self.call("complete")
        self.assertEqual(self.state()["status"], "completed")
        self.assertTrue(self.call("next").stdout.strip().endswith("DONE"))

    def test_02_validation_bug_and_current_outline_version(self):
        self.init(); self.outline()
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1", code=2)
        self.ready(); self.outline("P1: revised\nP2: changed\nP3: end\n", affects="none")
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1", code=2)
        self.ready("O2")
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1", code=2)

    def test_03_stale_outline_review_refused(self):
        self.init(); self.outline(); self.outline("P1: another\n", affects="none")
        result = self.call("outline", "review", "--version", "O1", "--verdict", "ready", "--file", self.root / "review.md", code=2)
        self.assertIn("stale", result.stderr)

    def test_04_cycle_cap_refuses_second_cycle(self):
        self.init(("--max-extra-cycles", "0")); self.outline("P1: only\n"); self.ready()
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1")
        self.call("para", "critique", "P1", "--file", self.root / "critique.md", "--objections", "0")
        result = self.call("para", "check", "P1", "--verdict", "reopen", "--file", self.root / "check.md", code=2)
        self.assertIn("cycle cap", result.stderr)

    def test_04b_default_run_has_no_cycle_cap(self):
        self.init(); self.outline("P1: only\n"); self.ready()
        for _ in range(5):
            self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1")
            self.call("para", "critique", "P1", "--file", self.root / "critique.md", "--objections", "1")
            self.call("para", "revise", "P1", "--file", self.root / "revision.md", "--responses-file", self.root / "responses.md")
            self.call("para", "check", "P1", "--verdict", "reopen", "--file", self.root / "check.md")
            self.assertIn("para draft P1", self.call("next").stdout)
        result = self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1")
        self.assertIn("Recorded P1 draft cycle 6", result.stdout)

    def test_05_mid_drafting_outline_change_marks_dependents_and_removed(self):
        self.init(); self.outline("P1: one\nP2: two depends: P1\nP3: three\n"); self.ready()
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1")
        self.write("outline2.md", "P1: changed\nP2: dependent depends: P1\n")
        self.call("outline", "propose", "--file", self.root / "outline2.md", code=2)
        self.call("outline", "propose", "--file", self.root / "outline2.md", "--affects", "P1")
        data = self.state()["paragraphs"]
        self.assertEqual(data["P1"]["status"], "needs_recheck")
        self.assertEqual(data["P2"]["status"], "needs_recheck")
        self.assertEqual(data["P3"]["status"], "deferred")

    def test_06_final_review_and_final_edit_gate_completion(self):
        self.init(); self.outline("P1: only\n"); self.ready()
        result = self.call("final", "review", "--role", "writer", "--file", self.root / "final.md", code=2)
        self.assertIn("P1", result.stderr)
        self.cycle("P1")
        self.call("final", "document", "--file", self.root / "document.md")
        self.call("final", "review", "--role", "writer", "--file", self.root / "final.md")
        self.call("final", "review", "--role", "critic", "--file", self.root / "final.md")
        self.call("final", "edit", "--file", self.root / "draft.md", "--affects", "P1")
        result = self.call("complete", code=2)
        self.assertIn("needs_recheck", result.stderr)

    def test_07_readiness_rules_and_partial(self):
        self.init(); self.outline("P1: only\n"); self.ready(); self.cycle("P1"); self.call("final", "document", "--file", self.root / "document.md")
        self.call("final", "review", "--role", "writer", "--file", self.root / "final.md")
        self.call("final", "review", "--role", "critic", "--file", self.root / "final.md")
        self.call("readiness", "set", "feedback", "N/A", "--evidence", "checked", code=2)
        self.call("readiness", "set", "requirements", "UNVERIFIED", "--evidence", "not checked")
        self.assertIn("UNVERIFIED", self.call("complete", code=2).stderr)
        self.call("complete", "--partial", "--reason", "source access pending")
        self.assertEqual(self.state()["status"], "partial")

    def test_08_out_of_order_requires_override_and_reason(self):
        self.init(); self.outline("P1: first\nP2: second\n"); self.ready()
        self.call("para", "draft", "P2", "--file", self.root / "draft.md", "--outline-version", "O1", code=2)
        self.call("para", "draft", "P2", "--file", self.root / "draft.md", "--outline-version", "O1", "--out-of-order", "--reason", "P1 needs a source")

    def test_09_baseline_blinding_unblinding_fatal_and_json_fence(self):
        self.reviewed_document(); self.write("user.md", "User whole draft.\n")
        self.call("baseline", "enable", "--file", self.root / "user.md", "--seed", "7")
        self.call("baseline", "prompts")
        state1 = self.state()["baseline"]
        prompt = (self.root / ".council" / self.state()["run_id"] / state1["judge_prompt"]["path"]).read_text(encoding="utf-8").lower()
        self.assertNotIn("council", prompt); self.assertNotIn("baseline", prompt)
        assignment = state1["assignment"]
        self.assertEqual(set(assignment.values()), {"single", "council"})
        # A second independently built CLI run with the same seed has the same X/Y map.
        other = self.root / "same-seed"; other.mkdir()
        for name, content in (("brief.md", "brief\n"), ("outline.md", "P1: only\n"), ("review.md", "review\n"),
                              ("draft.md", "draft\n"), ("critique.md", "critique\n"), ("check.md", "check\n"),
                              ("final.md", "final\n"), ("document.md", "document\n"), ("user.md", "user\n")):
            (other / name).write_text(content, encoding="utf-8")
        def other_call(*items):
            result = subprocess.run([sys.executable, str(SCRIPT), *map(str, items)], cwd=str(other), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        other_call("init", "--brief-file", other / "brief.md", "--root", other)
        other_call("outline", "propose", "--file", other / "outline.md")
        other_call("outline", "review", "--version", "O1", "--verdict", "ready", "--file", other / "review.md")
        other_call("para", "draft", "P1", "--file", other / "draft.md", "--outline-version", "O1")
        other_call("para", "critique", "P1", "--file", other / "critique.md", "--objections", "0")
        other_call("para", "check", "P1", "--verdict", "reviewed", "--file", other / "check.md")
        other_call("final", "document", "--file", other / "document.md")
        other_call("final", "review", "--role", "writer", "--file", other / "final.md")
        other_call("final", "review", "--role", "critic", "--file", other / "final.md")
        other_call("baseline", "enable", "--file", other / "user.md", "--seed", "7")
        other_call("baseline", "prompts")
        other_run = (other / ".council" / (other / ".council" / "LATEST").read_text(encoding="utf-8").strip() / "council.json")
        self.assertEqual(assignment, json.loads(other_run.read_text(encoding="utf-8"))["baseline"]["assignment"])
        verdict = {label: {"scores": {k: (9 if origin == "council" else 1) for k in ("evidence_support", "accuracy_of_use", "reasoning", "honest_uncertainty", "standalone_clarity")}, "fatal": origin == "council"}
                   for label, origin in assignment.items()}
        self.write("verdict.json", "```json\n" + json.dumps(verdict) + "\n```\n")
        self.call("baseline", "record-verdict", "--file", self.root / "verdict.json")
        result = self.state()["baseline"]["result"]
        self.assertEqual(result["winner"], "single-draft baseline")
        self.write("bad.json", "{\"X\": {}}")
        self.call("baseline", "record-verdict", "--file", self.root / "bad.json", code=2)

    def test_10_resume_latest_and_dir_override(self):
        self.init(); self.outline()
        run = self.root / ".council" / self.state()["run_id"]
        self.assertIn("outline review", self.call("next").stdout)
        self.assertIn("in_progress", self.call("status", "--dir", run).stdout)

    def test_11_refusal_exit_and_prefix(self):
        result = self.call("outline", "review", "--version", "O1", "--verdict", "ready", "--file", self.root / "review.md", code=2)
        self.assertTrue(result.stderr.startswith("REFUSED:"))

    def test_12_artifacts_are_copied_hashed_and_not_embedded(self):
        self.init()
        run = self.root / ".council" / self.state()["run_id"]
        original = self.root / "brief.md"; original.write_text("changed outside run", encoding="utf-8")
        data = self.state(); artifact = data["briefs"][0]["artifact"]
        self.assertEqual((run / artifact["path"]).read_text(encoding="utf-8"), "A brief.\n")
        self.assertEqual(len(artifact["sha256"]), 64)
        self.assertNotIn("A brief.", json.dumps(data))

    def test_13_next_at_happy_path_stages(self):
        self.init(); self.assertIn("outline propose", self.call("next").stdout)
        self.outline("P1: only\n"); self.assertIn("outline review", self.call("next").stdout)
        self.ready(); self.assertIn("para draft P1", self.call("next").stdout)
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1")
        self.assertIn("para critique P1", self.call("next").stdout)
        self.call("para", "critique", "P1", "--file", self.root / "critique.md", "--objections", "1")
        self.assertIn("para revise P1", self.call("next").stdout)
        self.call("para", "revise", "P1", "--file", self.root / "revision.md", "--responses-file", self.root / "responses.md")
        self.assertIn("para check P1", self.call("next").stdout)
        self.call("para", "check", "P1", "--verdict", "reviewed", "--file", self.root / "check.md")
        self.assertIn("final document", self.call("next").stdout)
        self.call("final", "document", "--file", self.root / "document.md")
        self.assertIn("final review --role writer", self.call("next").stdout)
        self.call("final", "review", "--role", "writer", "--file", self.root / "final.md")
        self.assertIn("final review --role critic", self.call("next").stdout)
        self.call("final", "review", "--role", "critic", "--file", self.root / "final.md")
        self.assertIn("readiness set requirements", self.call("next").stdout)
        self.pass_readiness(); self.assertTrue(self.call("next").stdout.strip().endswith("COUNCIL complete"))

    def test_14_capped_rechecks_reset_budget_and_next_resolves(self):
        self.init(("--max-extra-cycles", "0")); self.outline("P1: only\n"); self.ready(); self.cycle("P1")
        self.outline("P1: changed\n", affects="P1"); self.ready("O2")
        self.assertIn("para draft P1", self.call("next").stdout)
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O2")
        self.call("para", "critique", "P1", "--file", self.root / "critique.md", "--objections", "0")
        self.call("para", "check", "P1", "--verdict", "needs_evidence", "--file", self.root / "check.md")
        suggested = self.call("next").stdout
        self.assertIn("para resolve P1", suggested)
        self.call("para", "resolve", "P1", "--verdict", "qualified", "--file", self.root / "check.md")
        self.assertEqual(self.state()["paragraphs"]["P1"]["status"], "qualified")

    def test_15_invalidation_clears_readiness_and_requires_new_document(self):
        self.init(); self.outline("P1: only\n"); self.ready(); self.cycle("P1")
        self.call("final", "document", "--file", self.root / "document.md")
        self.call("final", "review", "--role", "writer", "--file", self.root / "final.md")
        self.call("final", "review", "--role", "critic", "--file", self.root / "final.md")
        self.pass_readiness()
        self.call("final", "edit", "--file", self.root / "draft.md", "--affects", "P1")
        self.assertEqual(self.state()["readiness"], {})
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1")
        self.call("para", "critique", "P1", "--file", self.root / "critique.md", "--objections", "0")
        self.call("para", "check", "P1", "--verdict", "reviewed", "--file", self.root / "check.md")
        self.assertIn("final document", self.call("next").stdout)
        self.call("final", "document", "--file", self.root / "document.md")
        self.call("final", "review", "--role", "writer", "--file", self.root / "final.md")
        self.call("final", "review", "--role", "critic", "--file", self.root / "final.md")
        self.assertIn("readiness set requirements", self.call("next").stdout)

    def test_16_final_document_is_reviewed_and_used_for_blind_comparison(self):
        self.reviewed_document(); self.write("user.md", "User draft.\n")
        self.call("baseline", "enable", "--file", self.root / "user.md", "--seed", "5")
        self.call("baseline", "prompts")
        state = self.state(); run = self.root / ".council" / state["run_id"]
        self.assertEqual(state["final_reviews"]["writer"]["document_version"], "D1")
        council_label = next(label for label, origin in state["baseline"]["assignment"].items() if origin == "council")
        self.assertIn("Assembled document", (run / state["baseline"][council_label]["path"]).read_text(encoding="utf-8"))

    def test_17_judge_prompt_embeds_documents_and_ledger_without_paths(self):
        self.reviewed_document(); self.write("user.md", "User draft.\n"); self.write("ledger.md", "S1: source\n")
        self.call("ledger", "--file", self.root / "ledger.md")
        self.call("baseline", "enable", "--file", self.root / "user.md", "--seed", "5")
        self.call("baseline", "prompts")
        state = self.state(); run = self.root / ".council" / state["run_id"]
        prompt = (run / state["baseline"]["judge_prompt"]["path"]).read_text(encoding="utf-8")
        self.assertIn("=== DOCUMENT X ===", prompt); self.assertIn("=== EVIDENCE LEDGER ===", prompt)
        self.assertNotIn("X.md", prompt); self.assertNotIn("../ledger", prompt)

    def test_18_readded_paragraph_and_unknown_affects(self):
        self.init(); self.outline("P1: one\nP3: old\n"); self.ready(); self.cycle("P1"); self.cycle("P3")
        self.outline("P1: one\n", affects="none"); self.ready("O2")
        self.assertEqual(self.state()["paragraphs"]["P3"]["status"], "deferred")
        self.outline("P1: one\nP3: back\n", affects="none")
        self.assertEqual(self.state()["paragraphs"]["P3"]["status"], "needs_recheck")
        self.write("bad-outline.md", "P1: one\nP3: back\n")
        self.call("outline", "propose", "--file", self.root / "bad-outline.md", "--affects", "P99", code=2)

    def test_19_redrafting_finished_paragraph_requires_reason(self):
        self.init(); self.outline("P1: only\n"); self.ready(); self.cycle("P1")
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1", code=2)
        self.call("para", "draft", "P1", "--file", self.root / "draft.md", "--outline-version", "O1", "--reason", "new evidence")

    def test_20_corrupt_state_and_extra_status_are_clean_errors(self):
        self.init()
        self.call("status", "anything", code=1)
        run = self.root / ".council" / self.state()["run_id"]
        (run / "council.json").write_text("{not json", encoding="utf-8")
        result = self.call("status", code=2)
        self.assertTrue(result.stderr.startswith("REFUSED:"))


if __name__ == "__main__":
    unittest.main()
