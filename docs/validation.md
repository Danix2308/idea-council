# Validation — Research Council v0.1

Date: October 21, 2026.

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
