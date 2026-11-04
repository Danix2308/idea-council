# Validation — Research Council

Date: October 21, 2026.

## v0.3 Claude compatibility — November 4, 2026

Added one shared host-compatibility reference for Codex, Claude Code, and Claude web/desktop/Cowork. Claude Code uses available general-purpose subagents; ordinary chat uses clearly labeled self-review when delegation is absent. Missing separate agents cannot pass a separate-agent requirement. Added nontechnical ZIP-upload instructions, a shorter portable description, and a reproducible ZIP builder. No personal course records were added.

Checks performed on the v0.3 files:

- Skill-creator format validation passed; the description also fits the 200-character limit stated in Anthropic's custom-skill guidance.
- All local Markdown reference targets resolved.
- The ZIP's eight-file manifest and every decompressed file matched the source skill folder. The archive contains only one top-level research-council folder, including SKILL.md and its supporting files.
- Repeated builds produced identical bytes. The builder rejected output inside its source folder before writing an archive there.
- Git whitespace validation passed.

A live Claude Code trial was attempted in an isolated temporary project with the installed skill, a short hypothetical pilot note, and only the Read tool available. The trial requested a two-paragraph summary plus review records, with no browsing or file writes. It ended in a provider safeguard/API error reporting reasoning_extraction, without a usable final result. This is an inconclusive runtime test, not a behavioral pass or proof that the skill caused the refusal. No separate-agent Claude trial completed. Raw run metadata remains outside the repository.

Claude web/desktop ZIP upload and Cowork execution were not tested through the UI. The setup instructions follow the official documentation checked November 4: [Claude skill setup](https://support.claude.com/en/articles/12512180-use-skills-in-claude), [custom-skill packaging](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), and [subagents](https://code.claude.com/docs/en/sub-agents). Compatibility guidance and package validity do not establish end-to-end operation or improved writing quality on any Claude surface.

## v0.2 research-quality additions

Added general-purpose foundations, source/citation audit, and completion-check references; linked them from the entrypoint and relevant roles; expanded source, claim, assumption, and readiness record contracts. No course documents, private feedback, grades, or personal research records were copied. No ENC1102 files were modified.

The skill-creator format validator, relative reference-link checks, and Git whitespace checks pass after these changes. The behavioral trial below tested v0.1; the new quality checks have been statically reviewed but have not received a new live research trial. These instruction changes do not create an automatic factual verifier.

## Static checks

The bundled skill-creator `quick_validate.py` passes. Relative skill reference links and interface metadata pass. Git whitespace checks pass.

## Supplied-sources behavioral trial

An independent evaluator ran actual separate Writer and Critic agents on a three-paragraph internal library-hours research brief. Inputs were three supplied notes: a voluntary patron survey, four Tuesday evening pilot observations without a comparison period, and a staffing-cost assumption excluding other expenses. No browsing or external services were used.

Observed behavior:

- Both roles discussed the paragraph outline before reviewing prose; the Critic prompted two useful refinements concerning assumed costs and decision criteria.
- All three paragraphs received actual source-aware Critic reviews. Draft text was retained where no substantive objection existed rather than forcing cosmetic changes.
- Both roles reviewed the whole document.
- The brief correctly qualified the voluntary sample, lack of comparison, and assumed costs. Calculations were 24/80 = 30%, 2 staff × 2 hours × $20 = $80 per extension, and $320 across four extensions; it did not present these as verified expenditure or full cost.

The trial exposed an ordering ambiguity: the Writer returned an outline revision and its first paragraph together after conditional clearance of the prior outline. The skill now requires explicit Critic confirmation of the exact current outline version before a separate body-drafting request. Premature prose is excluded and redrafted after readiness.

A focused ordering replay passed with the same separate role agents: Writer returned outline O3 only; Critic explicitly confirmed O3 ready; only then did Writer receive and complete the first paragraph drafting request. No broader repeat testing was performed.

## Limits

This is an instruction-based skill, not an executable orchestrator enforcing every state transition. The format validator does not prove research quality. The small trial does not establish improvement over direct drafting, verify real-world truth of supplied notes, or test live research, long contexts, failures, or resumption. No application, transport adapter, automated benchmark, or global installation is included. Test-run records remain outside the repository in the task's work directory; only this validation summary is published.
