# Idea Council

A private workspace for building a Codex skill that strengthens ideas and arguments through constructive criticism and revision.

## Goal

Run a Proposer and a Critic in separate contexts. Both may use the same model, or use either of the two available models. Track evidence, assumptions, objections, revisions, and unresolved disagreements. Agreement alone is not evidence of correctness.

## Proposed workflow

Proposer drafts an idea → Critic challenges it → Proposer revises → Critic checks the revision.

The output should explain what improved, what remains uncertain, and what evidence or test would resolve the remaining questions. It may recommend revising or abandoning an unsupported idea.

## Status

Planning stage. No executable skill or LLM Council integration has been implemented or tested.

The [LLM Council adaptation design](docs/llm-council-adaptation-design.md) records the earlier application-oriented proposal. Its critique protocol and separate agent identities inform this skill; a standalone web interface is optional, not a requirement of the skill.

## Next steps

1. Define the skill entrypoint and Proposer/Critic role instructions.
2. Specify the shared brief, objection ledger, evidence records, and final report.
3. Implement orchestration using available Codex capabilities, with explicit limits and failure reporting.
4. Evaluate against a direct answer and a single-agent revision baseline.

## References

- [Karpathy's LLM Council](https://github.com/karpathy/llm-council)
- [Self-Refine](https://github.com/madaan/self-refine)
- [Crossfire](https://github.com/JianyuZhan/crossfire)
- [Codex-based Multi-Agent Debate](https://github.com/muthuspark/multi-agent-debate)
