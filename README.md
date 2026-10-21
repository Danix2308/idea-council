# Idea Council

A Codex skill for developing research through context gathering, a reviewed paragraph outline, and Writer–Critic discussion of every paragraph.

## Research Council v0.1

The skill lives in [skills/research-council](skills/research-council/SKILL.md). It is an instruction-based workflow using the host's research tools and subagents, not a standalone app or background service. Both personas may use the same model. No additional provider or API key is required by the skill; normal host usage applies.

1. Read the task context, existing documents, and relevant evidence.
2. Discuss and review a complete paragraph-by-paragraph outline before body drafting.
3. Draft each paragraph, critique its claims and sources, revise it, and check the revision.
4. Revisit research or the outline when evidence changes the argument.
5. Review the whole document and retain unresolved uncertainty.

Before working, each role receives the brief, complete outline, relevant evidence, and current document. Outputs include a cited report, reviewed outline, source ledger, actual paragraph discussion records, and final review. Agreement is not proof of correctness.

## Install and use

Copy the entire `skills/research-council` folder into your Codex skill directory (normally `~/.codex/skills/`) or your project's `.agents/skills/` directory. Preserve its `references/` and `agents/` folders. Start a new session if the skill is not discovered immediately.

Example:

```text
Use $research-council to research [topic] for [audience and purpose]. Read the attached material first. Review an outline specifying what each paragraph contributes before writing. Develop every paragraph through Writer and Critic discussion. Include traceable citations and unresolved evidence gaps.
```

Separate agents require a host delegation mechanism. Without one, the skill discloses a single-agent approximation. This package does not install a runtime, configure model access, or change account settings.

## Design and validation

The [earlier LLM Council application design](docs/llm-council-adaptation-design.md) remains background. This skill implements the later context-first research-writing workflow; no web interface or LLM Council code is required.

See [validation](docs/validation.md) for checks and their limitations.

## References

- [LLM Council](https://github.com/karpathy/llm-council): peer review and inspectable outputs.
- [Self-Refine](https://github.com/madaan/self-refine): feedback and revision.
- [Virtual Lab](https://github.com/zou-group/virtual-lab): role-based research discussions.
- [Crossfire](https://github.com/JianyuZhan/crossfire): proposer/challenger orchestration.

These are methodological references, not runtime dependencies. No upstream source code is copied into the skill.
