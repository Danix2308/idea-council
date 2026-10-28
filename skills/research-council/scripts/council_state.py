#!/usr/bin/env python3
"""Persistent, local state gates for a Research Council writing run.

The program records only artifact metadata in JSON and copies the artifacts into
the run directory.  It deliberately does not generate prose or judge research.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


READY_KEYS = ("requirements", "foundations", "sources", "claims", "citations",
              "discussion", "analysis", "feedback", "final_artifact")
DONE_PARAS = ("reviewed", "qualified", "deferred")
BAD_COMPLETE_PARAS = ("needs_recheck", "draft", "under_review", "needs_evidence")
RUN_STATES = ("in_progress", "completed", "partial", "needs_input",
              "budget_exhausted", "cancelled", "failed")
SCORES = {
    "evidence_support": 30, "accuracy_of_use": 20, "reasoning": 20,
    "honest_uncertainty": 15, "standalone_clarity": 15,
}


class Refusal(Exception):
    """A process rule prevented a state transition."""
    def __init__(self, reason, fix):
        self.reason, self.fix = reason, fix
        super().__init__(reason)


class CouncilArgumentParser(argparse.ArgumentParser):
    """Keep syntax/usage failures distinct from state-rule refusals."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "USAGE: {}\n".format(message))


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, str(path))
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_json(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, value):
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def run_paths(args):
    if getattr(args, "dir", None):
        run = Path(args.dir).resolve()
        if run.name != ".council" and (run / "council.json").exists():
            return run, run / "council.json"
        # Permit --dir ROOT too, which is convenient for scripts.
        latest = run / ".council" / "LATEST"
    else:
        latest = Path.cwd() / ".council" / "LATEST"
    if not latest.exists():
        raise Refusal("no Council run is selected", "COUNCIL init --brief-file <brief>")
    run_id = latest.read_text(encoding="utf-8").strip()
    run = latest.parent / run_id
    state_file = run / "council.json"
    if not state_file.exists():
        raise Refusal("the selected Council run has no council.json", "COUNCIL init --brief-file <brief>")
    return run, state_file


def load_state(args):
    run, state_file = run_paths(args)
    return run, state_file, load_json(state_file)


def save_state(state_file, state):
    state["updated_at"] = utc_now()
    save_json(state_file, state)


def copy_artifact(run, source, relative):
    source = Path(source)
    if not source.is_file():
        raise Refusal("artifact file does not exist: {}".format(source), "COUNCIL ... --file <existing file>")
    if source.stat().st_size == 0:
        raise Refusal("artifact file is empty: {}".format(source), "COUNCIL ... --file <non-empty file>")
    target = run / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source), str(target))
    return {"path": target.relative_to(run).as_posix(), "sha256": sha256(target), "recorded_at": utc_now()}


def write_artifact(run, relative, content):
    target = run / relative
    atomic_write(target, content)
    return {"path": target.relative_to(run).as_posix(), "sha256": sha256(target), "recorded_at": utc_now()}


def version_number(items):
    return len(items) + 1


def current_outline(state):
    return state["outlines"][-1] if state["outlines"] else None


def outline_ready(state):
    outline = current_outline(state)
    return bool(outline and outline.get("verdict") == "ready")


def parse_ids(text):
    # Optional markdown markers then P<number>, followed by the documented delimiter.
    found, dependencies = [], {}
    line_re = re.compile(r"^\s*(?:#+\s*|[-*]\s*)?(P\d+)(?=\s*(?::|\.|\)|—|-|\s))", re.I)
    dep_re = re.compile(r"\bdepends\s*:\s*([^\n]+)", re.I)
    for line in text.splitlines():
        line = line.lstrip("\ufeff")  # PowerShell and editors may write UTF-8 BOMs.
        match = line_re.match(line)
        if not match:
            continue
        ident = match.group(1).upper()
        if ident in found:
            raise Refusal("outline contains duplicate paragraph ID {}".format(ident),
                          "COUNCIL outline propose --file <outline with unique P# IDs>")
        found.append(ident)
        dep = dep_re.search(line)
        if dep:
            ids = re.findall(r"\bP\d+\b", dep.group(1), re.I)
            dependencies[ident] = [item.upper() for item in ids]
        else:
            dependencies[ident] = []
    if not found:
        raise Refusal("outline contains no paragraph IDs", "COUNCIL outline propose --file <outline containing P1: ...>")
    return found, dependencies


def parse_affects(value):
    if value is None:
        return None
    if value.strip().lower() == "none":
        return []
    result = [x.strip().upper() for x in value.split(",") if x.strip()]
    if not result or any(not re.fullmatch(r"P\d+", x) for x in result):
        raise Refusal("--affects must be P1,P2 or none", "COUNCIL outline propose --file <outline> --affects P1,P2")
    return result


def dependent_closure(ids, deps):
    affected = set(ids)
    changed = True
    while changed:
        changed = False
        for para, needs in deps.items():
            if para not in affected and any(item in affected for item in needs):
                affected.add(para)
                changed = True
    return affected


def get_para(state, ident):
    try:
        return state["paragraphs"][ident]
    except KeyError:
        raise Refusal("{} is not in the current outline".format(ident), "COUNCIL status")


def current_versions(state):
    return {
        "brief": state["briefs"][-1]["version"] if state["briefs"] else None,
        "ledger": state["ledgers"][-1]["version"] if state["ledgers"] else None,
        "outline": current_outline(state)["version"] if current_outline(state) else None,
    }


def latest_final_document(state):
    return state.get("final_documents", [])[-1] if state.get("final_documents") else None


def clear_blind_result(state, clear_fresh_draft=False):
    baseline = state.get("baseline", {})
    for key in ("judge_prompt", "X", "Y", "assignment", "result", "verdict", "council_document"):
        baseline.pop(key, None)
    if clear_fresh_draft and baseline.get("source") == "fresh-agent":
        baseline.pop("draft", None)
        baseline.pop("writer_prompt", None)


def invalidate_final(state, document_required=True):
    state["final_reviews"] = {}
    state["readiness"] = {}
    state["final_document_required"] = document_required
    clear_blind_result(state)


def cycle_limit_reached(state, para):
    # No cap unless the run was started with an explicit --max-extra-cycles.
    if state.get("max_extra_cycles") is None:
        return False
    return para.get("cycles", 0) - para.get("cycle_base", 0) >= 1 + state["max_extra_cycles"]


def require_open_run(state):
    if state["status"] in ("completed", "partial", "cancelled", "failed"):
        raise Refusal("run status is {}".format(state["status"]), "COUNCIL init --brief-file <brief>  # start a new run")


def command_init(args):
    root = Path(args.root or Path.cwd()).resolve()
    if args.max_extra_cycles is not None and args.max_extra_cycles < 0:
        raise Refusal("--max-extra-cycles cannot be negative", "COUNCIL init --brief-file <brief> --max-extra-cycles 0")
    brief = Path(args.brief_file)
    if not brief.is_file() or brief.stat().st_size == 0:
        raise Refusal("brief file does not exist or is empty", "COUNCIL init --brief-file <non-empty brief>")
    council = root / ".council"
    council.mkdir(parents=True, exist_ok=True)
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id, suffix = base, 1
    while (council / run_id).exists():
        suffix += 1
        run_id = "{}-{}".format(base, suffix)
    run = council / run_id
    run.mkdir()
    state = {
        "schema_version": 1, "run_id": run_id, "created_at": utc_now(), "updated_at": utc_now(),
        "status": "in_progress", "mode": args.mode, "max_extra_cycles": args.max_extra_cycles,
        "briefs": [], "ledgers": [], "outlines": [], "paragraphs": {}, "final_documents": [],
        "final_document_required": True, "final_reviews": {}, "final_edits": [], "readiness": {},
        "baseline": {"enabled": False}, "events": [],
    }
    artifact = copy_artifact(run, brief, "brief/B1.md")
    state["briefs"].append({"version": "B1", "artifact": artifact})
    save_json(run / "council.json", state)
    atomic_write(council / "LATEST", run_id + "\n")
    print("Initialized {} ({})".format(run, args.mode))


def command_brief_or_ledger(args, kind):
    run, state_file, state = load_state(args)
    require_open_run(state)
    collection = state["briefs" if kind == "brief" else "ledgers"]
    prefix, folder = ("B", "brief") if kind == "brief" else ("E", "ledger")
    version = prefix + str(version_number(collection))
    artifact = copy_artifact(run, args.file, "{}/{}.md".format(folder, version))
    collection.append({"version": version, "artifact": artifact})
    if kind in ("brief", "ledger"):
        clear_blind_result(state, clear_fresh_draft=True)
    save_state(state_file, state)
    print("Recorded {}".format(version))


def command_outline_propose(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    source = Path(args.file)
    if not source.is_file():
        raise Refusal("outline file does not exist", "COUNCIL outline propose --file <outline>")
    text = source.read_text(encoding="utf-8")
    ids, deps = parse_ids(text)
    drafted = any(p.get("cycles", 0) for p in state["paragraphs"].values())
    affects = parse_affects(args.affects)
    if drafted and affects is None:
        raise Refusal("outline changes after drafting require --affects", "COUNCIL outline propose --file <outline> --affects P1,P2|none")
    old_ids = set(current_outline(state)["paragraph_ids"]) if current_outline(state) else set()
    invalid_affects = [ident for ident in (affects or []) if ident not in old_ids and ident not in ids]
    if invalid_affects:
        raise Refusal("--affects names unknown paragraph(s): " + ", ".join(invalid_affects),
                      "COUNCIL outline propose --file <outline> --affects P1,P2|none")
    version = "O" + str(version_number(state["outlines"]))
    artifact = copy_artifact(run, source, "outline/{}.md".format(version))
    state["outlines"].append({"version": version, "artifact": artifact, "paragraph_ids": ids,
                              "dependencies": deps, "verdict": None, "review": None})
    for ident in ids:
        entry = state["paragraphs"].setdefault(ident, {"status": "planned", "cycles": 0, "cycle_base": 0, "history": []})
        if entry.get("status") == "deferred" and str(entry.get("reason", "")).startswith("removed in "):
            entry["status"] = "needs_recheck" if entry.get("cycles", 0) else "planned"
            entry["cycle_base"] = entry.get("cycles", 0)
            entry["reason"] = "re-added in {}".format(version)
    if drafted:
        invalidate_final(state)
        for removed in old_ids - set(ids):
            entry = state["paragraphs"].setdefault(removed, {"cycles": 0, "cycle_base": 0, "history": []})
            entry.update({"status": "deferred", "reason": "removed in {}".format(version)})
        for ident in dependent_closure(affects, deps):
            if ident in state["paragraphs"] and ident in ids:
                state["paragraphs"][ident]["status"] = "needs_recheck"
                state["paragraphs"][ident]["cycle_base"] = state["paragraphs"][ident].get("cycles", 0)
                state["paragraphs"][ident]["reason"] = "affected by {}".format(version)
    save_state(state_file, state)
    print("Recorded {} (drafting gate closed)".format(version))


def command_outline_review(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    outline = current_outline(state)
    if not outline:
        raise Refusal("there is no outline to review", "COUNCIL outline propose --file <outline>")
    if args.version != outline["version"]:
        raise Refusal("{} is stale; current outline is {}".format(args.version, outline["version"]),
                      "COUNCIL outline review --version {} --verdict ready|revise --file <critic review>".format(outline["version"]))
    artifact = copy_artifact(run, args.file, "outline/{}-critic.md".format(args.version))
    outline["verdict"] = args.verdict
    outline["review"] = artifact
    save_state(state_file, state)
    print("{} is {}".format(args.version, args.verdict))


def require_current_outline(state, version):
    outline = current_outline(state)
    if not outline or not outline_ready(state):
        raise Refusal("current outline is not explicitly ready", "COUNCIL outline review --version {} --verdict ready --file <critic review>".format(outline["version"] if outline else "O1"))
    if version != outline["version"]:
        raise Refusal("draft names {} but current ready outline is {}".format(version, outline["version"]),
                      "COUNCIL para draft <P#> --file <draft> --outline-version {}".format(outline["version"]))
    return outline


def draft_order_refusal(state, ident, args, outline):
    order = outline["paragraph_ids"]
    target = order.index(ident)
    pending = [p for p in order[:target] if state["paragraphs"][p]["status"] not in DONE_PARAS]
    if pending and not args.out_of_order:
        raise Refusal("{} must follow unresolved {}".format(ident, ", ".join(pending)),
                      "COUNCIL para draft {} --file <draft> --outline-version {} --out-of-order --reason \"...\"".format(ident, outline["version"]))
    if args.out_of_order and not args.reason:
        raise Refusal("--out-of-order requires --reason", "COUNCIL para draft {} --file <draft> --outline-version {} --out-of-order --reason \"...\"".format(ident, outline["version"]))


def command_para_draft(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    ident = args.paragraph.upper()
    outline = require_current_outline(state, args.outline_version)
    if ident not in outline["paragraph_ids"]:
        raise Refusal("{} is not in current outline {}".format(ident, outline["version"]), "COUNCIL status")
    para = get_para(state, ident)
    if para["status"] in ("draft", "under_review"):
        raise Refusal("{} already has an unfinished cycle".format(ident), "COUNCIL next")
    draft_order_refusal(state, ident, args, outline)
    if para["status"] in DONE_PARAS and not args.reason:
        raise Refusal("redrafting finished {} requires --reason".format(ident),
                      "COUNCIL para draft {} --file <draft> --outline-version {} --reason \"...\"".format(ident, outline["version"]))
    if cycle_limit_reached(state, para):
        raise Refusal("{} reached its cycle cap; qualify or defer it".format(ident),
                      "COUNCIL para resolve {} --verdict qualified|deferred --file <note>".format(ident))
    cycle = para.get("cycles", 0) + 1
    artifact = copy_artifact(run, args.file, "paragraphs/{}/v{}-draft.md".format(ident, cycle))
    record = {"cycle": cycle, "draft": artifact, "versions": current_versions(state), "reason": args.reason}
    para.setdefault("history", []).append(record)
    para["cycles"] = cycle
    para["status"] = "draft"
    save_state(state_file, state)
    print("Recorded {} draft cycle {}".format(ident, cycle))


def latest_cycle(para):
    if not para.get("history"):
        raise Refusal("paragraph has not been drafted", "COUNCIL next")
    return para["history"][-1]


def command_para_critique(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    ident, para = args.paragraph.upper(), get_para(state, args.paragraph.upper())
    record = latest_cycle(para)
    if para["status"] != "draft" or record.get("critique"):
        raise Refusal("{} needs an uncritiqued draft or revision".format(ident), "COUNCIL next")
    if args.objections < 0:
        raise Refusal("--objections must be zero or greater", "COUNCIL para critique {} --file <review> --objections 0".format(ident))
    artifact = copy_artifact(run, args.file, "paragraphs/{}/v{}-critique.md".format(ident, record["cycle"]))
    record.update({"critique": artifact, "objections": args.objections})
    para["status"] = "under_review"
    save_state(state_file, state)
    print("Recorded {} critique".format(ident))


def command_para_revise(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    ident, para = args.paragraph.upper(), get_para(state, args.paragraph.upper())
    record = latest_cycle(para)
    if para["status"] != "under_review" or record.get("revision"):
        raise Refusal("{} needs a current critique before revision".format(ident), "COUNCIL next")
    if record["objections"] and not args.responses_file:
        raise Refusal("responses file is required when objections are nonzero", "COUNCIL para revise {} --file <revision> --responses-file <responses>".format(ident))
    artifact = copy_artifact(run, args.file, "paragraphs/{}/v{}-revision.md".format(ident, record["cycle"]))
    record["revision"] = artifact
    if args.responses_file:
        record["responses"] = copy_artifact(run, args.responses_file, "paragraphs/{}/v{}-responses.md".format(ident, record["cycle"]))
    save_state(state_file, state)
    print("Recorded {} revision".format(ident))


def command_para_check(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    ident, para = args.paragraph.upper(), get_para(state, args.paragraph.upper())
    record = latest_cycle(para)
    if para["status"] != "under_review" or not record.get("critique"):
        raise Refusal("{} needs a current critique before a check".format(ident), "COUNCIL next")
    if not record.get("revision") and record.get("objections") != 0:
        raise Refusal("{} needs a revision for its latest critique".format(ident), "COUNCIL para revise {} --file <revision> --responses-file <responses>".format(ident))
    if args.verdict == "reopen":
        if cycle_limit_reached(state, para):
            raise Refusal("{} reached its cycle cap; narrow, qualify, or defer instead of reopening".format(ident),
                          "COUNCIL para check {} --verdict deferred --file <check>".format(ident))
    artifact = copy_artifact(run, args.file, "paragraphs/{}/v{}-check.md".format(ident, record["cycle"]))
    record["check"] = artifact
    record["check_verdict"] = args.verdict
    if args.verdict == "reopen":
        para["status"] = "planned"
    else:
        para["status"] = args.verdict
    save_state(state_file, state)
    print("Recorded {} check: {}".format(ident, args.verdict))


def command_para_resolve(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    ident, para = args.paragraph.upper(), get_para(state, args.paragraph.upper())
    allowed = para["status"] in ("needs_evidence", "needs_recheck") and cycle_limit_reached(state, para)
    if not allowed:
        raise Refusal("{} is not a capped needs-evidence or recheck paragraph".format(ident), "COUNCIL next")
    cycle = para.get("cycles", 0)
    artifact = copy_artifact(run, args.file, "paragraphs/{}/v{}-resolve.md".format(ident, cycle))
    para.setdefault("history", []).append({"cycle": cycle, "resolve": artifact, "resolve_verdict": args.verdict,
                                            "versions": current_versions(state)})
    para["status"] = args.verdict
    para["reason"] = "resolved at cycle cap"
    save_state(state_file, state)
    print("Resolved {} as {}".format(ident, args.verdict))


def current_ids(state):
    outline = current_outline(state)
    return outline["paragraph_ids"] if outline else []


def unready_paras(state):
    return [p for p in current_ids(state) if state["paragraphs"][p]["status"] not in DONE_PARAS]


def command_final_document(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    bad = unready_paras(state)
    if bad:
        raise Refusal("final document is blocked by " + ", ".join(bad), "COUNCIL next")
    version = "D" + str(version_number(state["final_documents"]))
    artifact = copy_artifact(run, args.file, "final/{}.md".format(version))
    invalidate_final(state, document_required=False)
    state["final_documents"].append({"version": version, "artifact": artifact})
    save_state(state_file, state)
    print("Recorded final document {}".format(version))


def command_final_review(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    bad = unready_paras(state)
    if bad:
        raise Refusal("whole-document review is blocked by " + ", ".join(bad), "COUNCIL next")
    document = latest_final_document(state)
    if not document or state.get("final_document_required", False):
        raise Refusal("record the current final document before review", "COUNCIL final document --file <assembled document>")
    state["final_reviews"][args.role] = {"artifact": copy_artifact(run, args.file, "final/review-{}-{}.md".format(args.role, document["version"])),
                                        "document_version": document["version"]}
    save_state(state_file, state)
    print("Recorded {} final review".format(args.role))


def command_final_edit(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    ids = parse_affects(args.affects)
    if not ids:
        raise Refusal("final edit must affect at least one P#", "COUNCIL final edit --file <edit> --affects P1")
    invalid = [p for p in ids if p not in current_ids(state)]
    if invalid:
        raise Refusal("final edit names non-current paragraph(s): " + ", ".join(invalid), "COUNCIL status")
    n = len(state["final_edits"]) + 1
    artifact = copy_artifact(run, args.file, "final/edit-{}.md".format(n))
    state["final_edits"].append({"artifact": artifact, "affects": ids})
    invalidate_final(state)
    for ident in ids:
        state["paragraphs"][ident]["status"] = "needs_recheck"
    save_state(state_file, state)
    print("Recorded final edit; affected paragraphs need recheck")


def template(name):
    ref = Path(__file__).resolve().parents[1] / "references" / "baseline-check.md"
    text = ref.read_text(encoding="utf-8")
    match = re.search(r"<!-- template:{} -->\s*(.*?)\s*<!-- /template:{} -->".format(re.escape(name), re.escape(name)), text, re.S)
    if not match:
        raise RuntimeError("missing baseline template: " + name)
    return match.group(1)


def render_template(name, values):
    value = template(name)
    for key, replacement in values.items():
        value = value.replace("{{" + key + "}}", str(replacement))
    return value


def command_baseline_enable(args):
    run, state_file, state = load_state(args)
    if state["baseline"].get("enabled"):
        raise Refusal("baseline check is already enabled", "COUNCIL baseline prompts")
    seed = args.seed if args.seed is not None else random.SystemRandom().randint(0, 2**31 - 1)
    baseline = {"enabled": True, "seed": seed}
    if args.file:
        baseline["draft"] = copy_artifact(run, args.file, "baseline/user-draft.md")
        baseline["source"] = "user"
    else:
        baseline["source"] = "fresh-agent"
    state["baseline"] = baseline
    save_state(state_file, state)
    print("Baseline check enabled (extra cost: {} call(s))".format(1 if args.file else 2))


def reviews_current(state):
    document = latest_final_document(state)
    if not document or state.get("final_document_required", False):
        return False
    return all(state["final_reviews"].get(role, {}).get("document_version") == document["version"]
               for role in ("writer", "critic"))


def command_baseline_prompts(args):
    run, state_file, state = load_state(args)
    baseline = state["baseline"]
    if not baseline.get("enabled"):
        raise Refusal("baseline check is not enabled", "COUNCIL baseline enable")
    versions = current_versions(state)
    if not baseline.get("draft"):
        values = {"brief_path": run / state["briefs"][-1]["artifact"]["path"],
                  "ledger_path": run / state["ledgers"][-1]["artifact"]["path"] if state["ledgers"] else "(no ledger recorded)"}
        baseline["writer_prompt"] = write_artifact(run, "baseline/writer-prompt.md", render_template("baseline-writer", values))
    if not baseline.get("draft"):
        save_state(state_file, state)
        print("Wrote baseline writer prompt")
        return
    if not reviews_current(state):
        raise Refusal("both final reviews are required before blind comparison", "COUNCIL final review --role writer|critic --file <review>")
    document = latest_final_document(state)
    docs = [("single", baseline["draft"]), ("council", document["artifact"])]
    random.Random(baseline["seed"]).shuffle(docs)
    for blind_label, (origin, artifact) in zip(("X", "Y"), docs):
        target = run / "blind" / (blind_label + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(run / artifact["path"]), str(target))
        # record a separate artifact per blinded copy, preserving origin in JSON only.
        baseline[blind_label] = {"path": "blind/{}.md".format(blind_label), "sha256": sha256(target), "recorded_at": utc_now(), "origin": origin}
    # The mapping must follow source label, not X/Y label.
    baseline["assignment"] = {"X": docs[0][0], "Y": docs[1][0]}
    # Keep the blind prompt free of run-path labels; it is issued beside X.md/Y.md.
    x_text = (run / baseline["X"]["path"]).read_text(encoding="utf-8")
    y_text = (run / baseline["Y"]["path"]).read_text(encoding="utf-8")
    ledger_text = (run / state["ledgers"][-1]["artifact"]["path"]).read_text(encoding="utf-8") if state["ledgers"] else "No evidence ledger was recorded."
    values = {"x_document": x_text, "y_document": y_text, "ledger_text": ledger_text}
    baseline["judge_prompt"] = write_artifact(run, "blind/judge-prompt.md", render_template("baseline-judge", values))
    save_state(state_file, state)
    print("Wrote blinded judge prompt")


def command_baseline_record_draft(args):
    run, state_file, state = load_state(args)
    baseline = state["baseline"]
    if not baseline.get("enabled"):
        raise Refusal("baseline check is not enabled", "COUNCIL baseline enable")
    if baseline.get("draft"):
        raise Refusal("baseline draft is already recorded", "COUNCIL baseline prompts")
    baseline["draft"] = copy_artifact(run, args.file, "baseline/draft.md")
    save_state(state_file, state)
    print("Recorded baseline draft")


def first_json_object(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char == "{":
            try:
                value, _ = decoder.raw_decode(text[index:])
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object found")


def validate_verdict(value):
    if not isinstance(value, dict) or not {"X", "Y"}.issubset(value) or set(value) - {"X", "Y", "reason"}:
        raise ValueError("verdict must have X and Y, with optional reason only")
    if "reason" in value and (not isinstance(value["reason"], str) or not value["reason"].strip()):
        raise ValueError("reason must be a non-empty string")
    normalized = {}
    for label in ("X", "Y"):
        item = value[label]
        if not isinstance(item, dict) or set(item) != {"scores", "fatal"}:
            raise ValueError("{} must have scores and fatal".format(label))
        scores = item["scores"]
        if not isinstance(scores, dict) or set(scores) != set(SCORES):
            raise ValueError("{} scores have missing or unknown criteria".format(label))
        if not isinstance(item["fatal"], bool):
            raise ValueError("{} fatal must be boolean".format(label))
        for key, score in scores.items():
            if isinstance(score, bool) or not isinstance(score, (int, float)) or score < 0 or score > 10:
                raise ValueError("{} {} must be 0 through 10".format(label, key))
        normalized[label] = {"scores": scores, "fatal": item["fatal"],
                             "total": sum(scores[k] * SCORES[k] / 10.0 for k in SCORES)}
    if "reason" in value:
        normalized["reason"] = value["reason"].strip()
    return normalized


def command_baseline_record_verdict(args):
    run, state_file, state = load_state(args)
    baseline = state["baseline"]
    if not baseline.get("judge_prompt"):
        raise Refusal("blinded documents and judge prompt have not been created", "COUNCIL baseline prompts")
    try:
        data = first_json_object(Path(args.file).read_text(encoding="utf-8"))
        parsed = validate_verdict(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise Refusal("invalid blind verdict: {}".format(exc), "COUNCIL baseline record-verdict --file <valid verdict.json>")
    assignment = baseline["assignment"]
    outcomes = {assignment[label]: parsed[label] for label in ("X", "Y")}
    c, b = outcomes["council"], outcomes["single"]
    if c["fatal"] != b["fatal"]:
        winner = "single-draft baseline" if c["fatal"] else "council document"
    elif c["total"] > b["total"]:
        winner = "council document"
    elif b["total"] > c["total"]:
        winner = "single-draft baseline"
    else:
        winner = "tie"
    baseline["verdict"] = copy_artifact(run, args.file, "blind/verdict.json")
    baseline["result"] = {"council": c, "single": b, "winner": winner, "reason": parsed.get("reason")}
    save_state(state_file, state)
    print(blind_summary(state))


def blind_summary(state):
    result = state.get("baseline", {}).get("result")
    if not result:
        return "Blind check: pending"
    c, b = result["council"]["total"], result["single"]["total"]
    def shown(value):
        return "{:.1f}".format(value).rstrip("0").rstrip(".")
    winner = result["winner"]
    if winner == "tie":
        ending = "tie."
    elif winner == "council document":
        ending = "the council document scored higher."
    else:
        ending = "the baseline scored higher."
    summary = "Blind check: council document {} vs single-draft baseline {} - {}".format(shown(c), shown(b), ending)
    if result.get("reason"):
        summary += " Judge reason: " + result["reason"]
    return summary


def command_readiness_set(args):
    run, state_file, state = load_state(args)
    require_open_run(state)
    if not reviews_current(state):
        raise Refusal("both final reviews are required before readiness", "COUNCIL final review --role writer|critic --file <review>")
    if not args.evidence.strip():
        raise Refusal("--evidence is required", "COUNCIL readiness set {} PASS --evidence \"...\"".format(args.key))
    if args.result == "N/A" and not args.reason:
        raise Refusal("N/A requires --reason", "COUNCIL readiness set {} N/A --evidence \"...\" --reason \"...\"".format(args.key))
    state["readiness"][args.key] = {"result": args.result, "evidence": args.evidence, "reason": args.reason, "document_version": latest_final_document(state)["version"], "recorded_at": utc_now()}
    save_state(state_file, state)
    print("Recorded readiness {}: {}".format(args.key, args.result))


def completion_missing(state):
    missing = []
    if not latest_final_document(state) or state.get("final_document_required", False):
        missing.append("current final document")
    for role in ("writer", "critic"):
        if not reviews_current(state) or role not in state["final_reviews"]:
            missing.append("current final review: " + role)
    for key in READY_KEYS:
        value = state["readiness"].get(key)
        if not value:
            missing.append("readiness: " + key)
        elif value["result"] in ("FAIL", "UNVERIFIED"):
            missing.append("readiness {} is {}".format(key, value["result"]))
        elif value.get("document_version") != (latest_final_document(state) or {}).get("version"):
            missing.append("readiness {} is stale".format(key))
    for ident in current_ids(state):
        if state["paragraphs"][ident]["status"] in BAD_COMPLETE_PARAS:
            missing.append("paragraph {} is {}".format(ident, state["paragraphs"][ident]["status"]))
    return missing


def command_complete(args):
    run, state_file, state = load_state(args)
    if args.partial:
        if not args.reason:
            raise Refusal("--partial requires --reason", "COUNCIL complete --partial --reason \"...\"")
        state["status"] = "partial"
        state["status_reason"] = args.reason
        save_state(state_file, state)
        print("Run marked partial")
        return
    missing = completion_missing(state)
    if missing:
        raise Refusal("completion is blocked by: " + "; ".join(missing), "COUNCIL next")
    state["status"] = "completed"
    save_state(state_file, state)
    print("Run completed")


def command_status_set(args):
    run, state_file, state = load_state(args)
    if args.state in ("completed", "partial"):
        raise Refusal("use complete for {}".format(args.state), "COUNCIL complete")
    if not args.reason:
        raise Refusal("status changes require --reason", "COUNCIL status set {} --reason \"...\"".format(args.state))
    state["status"], state["status_reason"] = args.state, args.reason
    save_state(state_file, state)
    print("Run marked {}".format(args.state))


def state_summary(state):
    return {
        "run_id": state["run_id"], "status": state["status"], "mode": state["mode"],
        "versions": current_versions(state), "final_document": latest_final_document(state)["version"] if latest_final_document(state) else None,
        "paragraphs": {p: state["paragraphs"][p]["status"] for p in current_ids(state)},
        "readiness": {k: state["readiness"].get(k, {}).get("result", "unset") for k in READY_KEYS},
        "blind_check": blind_summary(state) if state.get("baseline", {}).get("enabled") else "Blind check: disabled",
    }


def command_status(args):
    _, _, state = load_state(args)
    summary = state_summary(state)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print("Run {}: {} | mode: {}".format(summary["run_id"], summary["status"], summary["mode"]))
    print("Versions: B={} E={} O={} D={}".format(summary["versions"]["brief"], summary["versions"]["ledger"], summary["versions"]["outline"], summary["final_document"]))
    print("Paragraphs: " + ", ".join("{}={}".format(k, v) for k, v in summary["paragraphs"].items()))
    print("Readiness: " + ", ".join("{}={}".format(k, v) for k, v in summary["readiness"].items()))
    print(summary["blind_check"])


def command_next(args):
    _, _, state = load_state(args)
    prefix = "COUNCIL "
    print("Mode: {}".format("single-agent approximation" if state["mode"] == "single-agent-approximation" else "separate-agents"))
    if state["status"] in ("completed", "partial", "cancelled", "failed"):
        print("DONE")
        return
    outline = current_outline(state)
    if not outline:
        print(prefix + "outline propose --file <outline>")
        return
    if not outline_ready(state):
        print(prefix + "outline review --version {} --verdict ready|revise --file <critic review>".format(outline["version"]))
        return
    for ident in outline["paragraph_ids"]:
        para = state["paragraphs"][ident]
        record = para["history"][-1] if para.get("history") else None
        if para["status"] in ("planned", "needs_recheck", "needs_evidence"):
            if para["status"] in ("needs_recheck", "needs_evidence") and cycle_limit_reached(state, para):
                print(prefix + "para resolve {} --verdict qualified|deferred --file <note>".format(ident))
                return
            print(prefix + "para draft {} --file <draft> --outline-version {}".format(ident, outline["version"]))
            return
        if para["status"] == "draft":
            print(prefix + "para critique {} --file <critic review> --objections <n>".format(ident))
            return
        if para["status"] == "under_review":
            if record.get("objections", 0) and not record.get("revision"):
                print(prefix + "para revise {} --file <revision> --responses-file <responses>".format(ident))
            elif not record.get("check"):
                print(prefix + "para check {} --verdict reviewed|qualified|needs_evidence|deferred|reopen --file <check>".format(ident))
            else:
                print(prefix + "para check {} --verdict reviewed|qualified|needs_evidence|deferred|reopen --file <check>".format(ident))
            return
    if not latest_final_document(state) or state.get("final_document_required", False):
        print(prefix + "final document --file <assembled document>")
        return
    for role in ("writer", "critic"):
        if state["final_reviews"].get(role, {}).get("document_version") != latest_final_document(state)["version"]:
            print(prefix + "final review --role {} --file <review>".format(role))
            return
    base = state.get("baseline", {})
    if base.get("enabled"):
        if not base.get("draft"):
            if base.get("writer_prompt"):
                print(prefix + "baseline record-draft --file <one-pass draft>")
            else:
                print(prefix + "baseline prompts")
            return
        if not base.get("judge_prompt"):
            print(prefix + "baseline prompts")
            return
        if not base.get("result"):
            print(prefix + "baseline record-verdict --file <judge verdict.json>")
            return
    for key in READY_KEYS:
        if key not in state["readiness"]:
            print(prefix + "readiness set {} PASS|FAIL|UNVERIFIED|N/A --evidence \"...\"".format(key))
            return
    if completion_missing(state):
        print(prefix + "complete --partial --reason \"...\"")
    else:
        print(prefix + "complete")


def report_text(state):
    lines = ["# Research Council checkpoint", "", "- Run: `{}`".format(state["run_id"]),
             "- Status: `{}`".format(state["status"]),
             "- Execution mode: **{}**".format("single-agent approximation" if state["mode"] == "single-agent-approximation" else "separate-agents"),
             "- Versions: brief {}, ledger {}, outline {}, final document {}".format(current_versions(state)["brief"], current_versions(state)["ledger"], current_versions(state)["outline"], latest_final_document(state)["version"] if latest_final_document(state) else "none"), "",
             "## Paragraphs", "", "| Paragraph | Status | Cycles |", "| --- | --- | --- |"]
    for ident in current_ids(state):
        value = state["paragraphs"][ident]
        lines.append("| {} | {} | {} |".format(ident, value["status"], value.get("cycles", 0)))
    lines += ["", "## Readiness", "", "| Check | Result | Evidence |", "| --- | --- | --- |"]
    for key in READY_KEYS:
        value = state["readiness"].get(key, {})
        lines.append("| {} | {} | {} |".format(key, value.get("result", "unset"), value.get("evidence", "")))
    if state.get("baseline", {}).get("enabled"):
        lines += ["", "## Blind comparison", "", blind_summary(state), "The judge is the same model family and one comparison is not a benchmark."]
    lines += ["", "## Next action", "", "Run `COUNCIL next` for the required state transition.", ""]
    return "\n".join(lines)


def command_report(args):
    run, _, state = load_state(args)
    content = report_text(state)
    if args.out:
        atomic_write(args.out, content)
        print("Wrote report {}".format(args.out))
    else:
        print(content, end="")


def add_dir(parser):
    parser.add_argument("--dir", help="run directory, or root containing .council")


def parser():
    root = CouncilArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("--brief-file", required=True); p.add_argument("--mode", choices=("separate-agents", "single-agent-approximation"), default="separate-agents")
    p.add_argument("--max-extra-cycles", type=int, default=None, help="optional per-paragraph cap; unlimited by default"); p.add_argument("--root")
    p.set_defaults(func=command_init)
    for name, func in (("brief", lambda a: command_brief_or_ledger(a, "brief")), ("ledger", lambda a: command_brief_or_ledger(a, "ledger"))):
        p = sub.add_parser(name); p.add_argument("--file", required=True); add_dir(p); p.set_defaults(func=func)
    p = sub.add_parser("outline"); outline_sub = p.add_subparsers(dest="outline_command", required=True)
    q = outline_sub.add_parser("propose"); q.add_argument("--file", required=True); q.add_argument("--affects"); add_dir(q); q.set_defaults(func=command_outline_propose)
    q = outline_sub.add_parser("review"); q.add_argument("--version", required=True); q.add_argument("--verdict", choices=("ready", "revise"), required=True); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_outline_review)
    p = sub.add_parser("para"); para_sub = p.add_subparsers(dest="para_command", required=True)
    q = para_sub.add_parser("draft"); q.add_argument("paragraph"); q.add_argument("--file", required=True); q.add_argument("--outline-version", required=True); q.add_argument("--out-of-order", action="store_true"); q.add_argument("--reason"); add_dir(q); q.set_defaults(func=command_para_draft)
    q = para_sub.add_parser("critique"); q.add_argument("paragraph"); q.add_argument("--file", required=True); q.add_argument("--objections", required=True, type=int); add_dir(q); q.set_defaults(func=command_para_critique)
    q = para_sub.add_parser("revise"); q.add_argument("paragraph"); q.add_argument("--file", required=True); q.add_argument("--responses-file"); add_dir(q); q.set_defaults(func=command_para_revise)
    q = para_sub.add_parser("check"); q.add_argument("paragraph"); q.add_argument("--verdict", required=True, choices=("reviewed", "qualified", "needs_evidence", "deferred", "reopen")); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_para_check)
    q = para_sub.add_parser("resolve"); q.add_argument("paragraph"); q.add_argument("--verdict", required=True, choices=("qualified", "deferred")); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_para_resolve)
    p = sub.add_parser("final"); final_sub = p.add_subparsers(dest="final_command", required=True)
    q = final_sub.add_parser("document"); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_final_document)
    q = final_sub.add_parser("review"); q.add_argument("--role", choices=("writer", "critic"), required=True); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_final_review)
    q = final_sub.add_parser("edit"); q.add_argument("--file", required=True); q.add_argument("--affects", required=True); add_dir(q); q.set_defaults(func=command_final_edit)
    p = sub.add_parser("baseline"); base_sub = p.add_subparsers(dest="baseline_command", required=True)
    q = base_sub.add_parser("enable"); q.add_argument("--file"); q.add_argument("--seed", type=int); add_dir(q); q.set_defaults(func=command_baseline_enable)
    q = base_sub.add_parser("prompts"); add_dir(q); q.set_defaults(func=command_baseline_prompts)
    q = base_sub.add_parser("record-draft"); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_baseline_record_draft)
    q = base_sub.add_parser("record-verdict"); q.add_argument("--file", required=True); add_dir(q); q.set_defaults(func=command_baseline_record_verdict)
    p = sub.add_parser("readiness"); rs = p.add_subparsers(dest="readiness_command", required=True)
    q = rs.add_parser("set"); q.add_argument("key", choices=READY_KEYS); q.add_argument("result", choices=("PASS", "FAIL", "UNVERIFIED", "N/A")); q.add_argument("--evidence", required=True); q.add_argument("--reason"); add_dir(q); q.set_defaults(func=command_readiness_set)
    p = sub.add_parser("complete"); p.add_argument("--partial", action="store_true"); p.add_argument("--reason"); add_dir(p); p.set_defaults(func=command_complete)
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true"); add_dir(p); p.set_defaults(func=command_status)
    p = sub.add_parser("next"); add_dir(p); p.set_defaults(func=command_next)
    p = sub.add_parser("report"); p.add_argument("--out"); add_dir(p); p.set_defaults(func=command_report)
    p = sub.add_parser("status-set", help="set non-completion terminal or pause states")
    p.add_argument("state", choices=RUN_STATES); p.add_argument("--reason", required=True); add_dir(p); p.set_defaults(func=command_status_set)
    return root


def main(argv=None):
    try:
        argv = list(sys.argv[1:] if argv is None else argv)
        if len(argv) >= 2 and argv[0] == "status" and argv[1] == "set":
            argv = ["status-set"] + argv[2:]
        args = parser().parse_args(argv)
        args.func(args)
        return 0
    except Refusal as exc:
        print("REFUSED: {}\nFix: {}".format(exc.reason, exc.fix), file=sys.stderr)
        return 2
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        print("REFUSED: cannot read Council state or artifact: {}\nFix: restore a UTF-8, readable file or choose a valid --file/--dir.".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
