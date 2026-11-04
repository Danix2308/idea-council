# Idea Council

A skill for Codex and Claude that develops research through context gathering, a reviewed paragraph outline, and Writer–Critic discussion of every paragraph.

## Research Council v0.3

The skill lives in [skills/research-council](skills/research-council/SKILL.md). It is an instruction-based workflow using the host's research tools and subagents, not a standalone app or background service. Both personas may use the same model. No additional provider or API key is required by the skill; normal host usage applies.

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

Preserve the whole folder, including `references/` and `agents/`. The OpenAI metadata is used by Codex; it does not create Claude agents. Restart the client if a local skill is not discovered. Claude Code local installation does not by itself install the skill in Claude web or Cowork; use the account upload for those surfaces.

Example:

```text
Use $research-council to research [topic] for [audience and purpose]. Read the attached material first. Review an outline specifying what each paragraph contributes before writing. Develop every paragraph through Writer and Critic discussion. Include traceable citations and unresolved evidence gaps.
```

In Claude chat, replace `Use $research-council` with `Use the Research Council skill`. In Claude Code, begin with `/research-council`.

Separate agents require a host delegation mechanism. Without one, the skill discloses a single-agent approximation and labels the Critic stages as self-review. It cannot fulfill a separate-agent requirement in that mode. This package does not install a runtime, configure model access, or change account settings.

### Build an upload ZIP

From a checkout with Python 3.9 or later, run `python scripts/package_skill.py`. It writes `dist/research-council.zip` with one top-level `research-council/` folder and all supporting files. This archive can be attached to an email, so recipients do not need GitHub access. See [validation](docs/validation.md) for what has and has not been tested.

## Design and validation

The [earlier LLM Council application design](docs/llm-council-adaptation-design.md) remains background. This skill implements the later context-first research-writing workflow; no web interface or LLM Council code is required.

See [validation](docs/validation.md) for checks and their limitations.

## References

- [LLM Council](https://github.com/karpathy/llm-council): peer review and inspectable outputs.
- [Self-Refine](https://github.com/madaan/self-refine): feedback and revision.
- [Virtual Lab](https://github.com/zou-group/virtual-lab): role-based research discussions.
- [Crossfire](https://github.com/JianyuZhan/crossfire): proposer/challenger orchestration.

These are methodological references, not runtime dependencies. No upstream source code is copied into the skill.
