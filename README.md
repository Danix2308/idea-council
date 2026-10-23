# Idea Council

A skill for Codex and Claude Code for developing research through context gathering, a reviewed paragraph outline, and Writer–Critic discussion of every paragraph.

## Research Council v0.3

The skill lives in [skills/research-council](skills/research-council/SKILL.md). It uses the host's research tools and subagents, plus a small local Python state tool that enforces the workflow gates. Both personas may use the same model. No additional provider or API key is required; Python 3.8+ is required for the state tool.

1. Read the task context, existing documents, and relevant evidence.
2. Discuss and review a complete paragraph-by-paragraph outline before body drafting.
3. Draft each paragraph, critique its claims and sources, revise it, and check the revision.
4. Revisit research or the outline when evidence changes the argument.
5. Review the whole document and retain unresolved uncertainty.

Before working, each role receives the brief, complete outline, relevant evidence, and current document. Outputs include a cited report, reviewed outline, source ledger, actual paragraph discussion records, and final review. Agreement is not proof of correctness.

Research checks cover conceptual definitions and operational measures, consequential assumptions, exact source versions and reading depth, claim-level evidence, quotations and paraphrases, compatible cross-source synthesis, standalone readability, and readiness of the exact final artifact. Required checks are recorded as PASS, FAIL, UNVERIFIED, or justified N/A. The reusable guidance contains no personal course records or instructor feedback.

## Install and use

### Install on Codex

Copy the entire `skills/research-council` folder into your Codex skill directory (normally `~/.codex/skills/`) or your project's `.agents/skills/` directory. Preserve its `references/`, `agents/`, and `scripts/` folders. Start a new session if the skill is not discovered immediately.

### Install on Claude Code

Copy the `skills/research-council` folder, including its `references/`, `agents/`, and `scripts/` folders, to `~/.claude/skills/` or the project's `.claude/skills/`. It then appears as `/research-council`. Or install the marketplace with `/plugin marketplace add Danix2308/idea-council`, then run `/plugin install idea-council@idea-council`; it appears as `/idea-council:research-council`.

Example:

```text
Use $research-council to research [topic] for [audience and purpose]. Read the attached material first. Review an outline specifying what each paragraph contributes before writing. Develop every paragraph through Writer and Critic discussion. Include traceable citations and unresolved evidence gaps.
```

Separate agents require a host delegation mechanism. Without one, the skill discloses a single-agent approximation. This package does not install a runtime, configure model access, or change account settings.

## State tool

From a checkout, set `COUNCIL` to `python skills/research-council/scripts/council_state.py`; from an installed skill, set it to `python <research-council skill folder>/scripts/council_state.py`. The tool stores each run at `.council/<run-id>/`, copies every recorded artifact, and records only relative paths, SHA-256 hashes, and UTC timestamps in `council.json`.

```text
COUNCIL init --brief-file brief.md
COUNCIL ledger --file evidence-ledger.md
COUNCIL outline propose --file outline.md
COUNCIL outline review --version O1 --verdict ready --file outline-review.md
COUNCIL final document --file assembled-document.md
COUNCIL next
```

Then use `para draft`, `para critique`, `para revise`, and `para check` for each paragraph; use `para resolve` only for a capped recheck/evidence gap. Record the assembled document with `final document`; `final review`, `readiness set`, and `complete` close the run. `COUNCIL next` prints the one currently required transition. `REFUSED:` means correct the recorded process rather than bypassing it.

For evaluation runs, the optional `baseline enable`, `baseline prompts`, `baseline record-draft`, and `baseline record-verdict` commands perform a blinded comparison with a one-pass draft. It is off by default, requires disclosure of the extra call cost, and reports when the baseline scores higher. See [baseline-check.md](skills/research-council/references/baseline-check.md).

Run the stdlib test suite from the repository root:

```text
python -m unittest discover -s tests -v
```

## Design and validation

The [earlier LLM Council application design](docs/llm-council-adaptation-design.md) remains background. This skill implements the later context-first research-writing workflow; no web interface or LLM Council code is required.

See [validation](docs/validation.md) for checks and their limitations.

## References

- [LLM Council](https://github.com/karpathy/llm-council): peer review and inspectable outputs.
- [Self-Refine](https://github.com/madaan/self-refine): feedback and revision.
- [Virtual Lab](https://github.com/zou-group/virtual-lab): role-based research discussions.
- [Crossfire](https://github.com/JianyuZhan/crossfire): proposer/challenger orchestration.
- [arena](https://github.com/Jakeschincariol/arena-skill): methodological reference for a state file plus `next` driver and blind baseline comparison.

These are methodological references, not runtime dependencies. No upstream source code is copied into the skill.

## License

MIT. See [LICENSE](LICENSE).
