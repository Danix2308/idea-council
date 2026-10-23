# Validation — Research Council

Date: October 23, 2026.

## v0.3 state enforcement

Added a standard-library state tool that records artifacts and mechanically gates exact-version outline readiness, paragraph cycles, whole-document review, readiness, and completion. Added an optional blinded one-pass baseline comparison, a CLI-driven unit-test suite, MIT licensing, and Claude Code plugin packaging.

The unit-test suite contains 20 tests; 20 passed in the implementation verification for this release. The bundled `quick_validate.py` passes. No new live research trial was run with the state tool, and the baseline check has not yet been run on a real task. The state tool enforces process order; it does not establish research quality or factual truth.

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
