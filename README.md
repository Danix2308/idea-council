# Idea Council

A skill for Codex and Claude that develops research through context gathering, a reviewed paragraph outline, and Writer–Critic discussion of every paragraph.

## Research Council v0.3.1

The skill lives in [skills/research-council](skills/research-council/SKILL.md). It uses the host's research tools and subagents, plus a small local Python state tool that enforces the workflow gates. Both personas may use the same model. No additional provider or API key is required; Python 3.8+ is required for the state tool.

1. Read the task context, existing documents, and relevant evidence.
2. Discuss and review a complete paragraph-by-paragraph outline before body drafting.
3. Draft each paragraph, critique its claims and sources, revise it, and check the revision.
4. Revisit research or the outline when evidence changes the argument.
5. Review the whole document and retain unresolved uncertainty.

Before working, each role receives the brief, complete outline, relevant evidence, and current document. Outputs include a cited report, reviewed outline, source ledger, actual paragraph discussion records, and final review. Agreement is not proof of correctness.

Research checks cover conceptual definitions and operational measures, consequential assumptions, exact source versions and reading depth, claim-level evidence, quotations and paraphrases, compatible cross-source synthesis, standalone readability, and readiness of the exact final artifact. Required checks are recorded as PASS, FAIL, UNVERIFIED, or justified N/A. The reusable guidance contains no personal course records or instructor feedback.

## Install and use

For a nontechnical Claude setup, follow [the step-by-step Claude guide](docs/claude-setup.md). The same skill folder supports all hosts; there is no separate Claude fork to keep synchronized.

| Host | Installation | Activation |
|---|---|---|
| Codex | Copy `skills/research-council` into the project's `.agents/skills/` or your personal `~/.agents/skills/` | Ask to use `$research-council` |
| Claude web / desktop / Cowork | Upload the packaged ZIP in Customize > Skills and enable it | Ask to use the Research Council skill |
| Claude Code, local sessions | Copy `skills/research-council` into `.claude/skills/` in the project or `~/.claude/skills/` | `/research-council` followed by the task |
| Claude Code, plugin | Run `/plugin marketplace add Danix2308/idea-council`, then `/plugin install idea-council@idea-council` | `/idea-council:research-council` followed by the task |

Preserve the whole folder, including `references/`, `agents/` and `scripts/`. The OpenAI metadata is used by Codex; it does not create Claude agents. Restart the client if a local skill is not discovered. Claude Code local installation does not by itself install the skill in Claude web or Cowork; use the account upload for those surfaces.

Example:

```text
Use $research-council to research [topic] for [audience and purpose]. Read the attached material first. Review an outline specifying what each paragraph contributes before writing. Develop every paragraph through Writer and Critic discussion. Include traceable citations and unresolved evidence gaps.
```

In Claude chat, replace `Use $research-council` with `Use the Research Council skill`. In Claude Code, begin with `/research-council`.

Separate agents require a host delegation mechanism. Without one, the skill discloses a single-agent approximation and labels the Critic stages as self-review. It cannot fulfill a separate-agent requirement in that mode. This package does not install a runtime, configure model access, or change account settings.

### Build an upload ZIP

From a checkout with Python 3.9 or later, run `python scripts/package_skill.py`. It writes `dist/research-council.zip` with one top-level `research-council/` folder and all supporting files. This archive can be attached to an email, so recipients do not need GitHub access. See [validation](docs/validation.md) for what has and has not been tested.

## State tool

From a checkout, set `COUNCIL` to `python skills/research-council/scripts/council_state.py`; from an installed skill, set it to `python <research-council skill folder>/scripts/council_state.py`. The tool stores each run at `.council/<run-id>/`, copies every recorded artifact, and records only relative paths, SHA-256 hashes, and UTC timestamps in `council.json`.

Claude Code and Codex run the tool locally. In Claude web / desktop / Cowork it runs only when code execution ("Create and edit files") is on. There, `.council/` lives in that chat's sandbox, so the coordinator offers the run folder as a download at the end; upload it again to resume. Without code execution, the skill announces `state tool unavailable` and keeps the same records as files or labeled chat sections.

```text
COUNCIL init --brief-file brief.md
COUNCIL ledger --file evidence-ledger.md
COUNCIL outline propose --file outline.md
COUNCIL outline review --version O1 --verdict ready --file outline-review.md
COUNCIL final document --file assembled-document.md
COUNCIL next
```

Then use `para draft`, `para critique`, `para revise`, and `para check` for each paragraph; a paragraph can be reopened for as many cycles as the debate needs (no cap by default; `init --max-extra-cycles <n>` sets one, and `para resolve` closes a capped paragraph). Record the assembled document with `final document`; `final review`, `readiness set`, and `complete` close the run. `COUNCIL next` prints the one currently required transition. `REFUSED:` means correct the recorded process rather than bypassing it.

For evaluation runs, the optional `baseline enable`, `baseline prompts`, `baseline record-draft`, and `baseline record-verdict` commands perform a blinded comparison with a one-pass draft. It is off by default, requires disclosure of the extra call cost, and reports when the baseline scores higher. See [baseline-check.md](skills/research-council/references/baseline-check.md).

## Watch the debate live

`scripts/council_live.py` is a read-only viewer for a run. Start it in the project folder before or during a run; it waits for `.council/` to appear and follows new runs. It works with local Codex and Claude Code sessions only: a Claude web, desktop chat, or Cowork run lives in that chat's sandbox, so read its records there or in the downloaded `.council` folder (`watch --once --dir <folder containing .council>` prints a downloaded run).

```text
python skills/research-council/scripts/council_live.py serve --open     # browser tab at http://127.0.0.1:8765/
python skills/research-council/scripts/council_live.py watch            # terminal (CMD/PowerShell) feed
```

Each recorded artifact appears the moment the coordinator records it: Writer messages on the left, Critic messages on the right, and a "Critic is critiquing P3 · 00:42" bar showing whose turn it is and for how long. Filter by paragraph with the chips; blind baseline content stays hidden unless `--show-blind` is passed.

- `--host` also tails this project's Codex and Claude Code session transcripts, so you can see each subagent's tool calls, searches, and messages between recorded steps. It only follows sessions whose working folder is this project unless `--host-any` is given.
- `council_live.py say --role critic --working --text "Reading S3 section 4"` posts a live note and restarts that role's timer; the coordinator can call it when dispatching a role.
- `watch --compact` shows the first six lines of each message; `watch --once` prints the transcript so far and exits.

Hosts do not expose a subagent's tokens while it is still generating, so the viewer updates per recorded step, note, or transcript line rather than token by token.

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
