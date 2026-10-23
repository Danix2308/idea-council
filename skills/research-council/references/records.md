# Research records

Use Markdown or structured data; these contracts do not require a database or fixed filenames outside the state tool. When `council_state.py` is used, it copies records into the run directory with its versioned names and stores paths, hashes, and timestamps in `council.json`. Preserve stable IDs and version references.

## State-tool record locations

The run lives at `.council/<run-id>/`. The state JSON holds metadata, never artifact contents. Briefs are `brief/B<n>.md`; ledgers are `ledger/E<n>.md`; outlines and their reviews are `outline/O<n>.md` and `outline/O<n>-critic.md`; paragraph artifacts are `paragraphs/P<n>/v<n>-{draft,critique,responses,revision,check,resolve}.md`; final documents, reviews, and edits are in `final/` (`D<n>.md` is the assembled document); optional blinded `X`, `Y`, judge prompt, and verdict artifacts are in `blind/`. `council.json` maps every recorded artifact to its relative path, SHA-256, and UTC recording time.

## Shared context packet

- Brief/version: purpose, audience, scope, research questions, definitions, constraints, assumptions, decisions, evidence boundary.
- Complete outline/version and structural review status.
- Latest full document/version, with paragraph IDs and statuses. Disclose any necessary context-map substitute and provide access to originals.
- Relevant sources/locators, counterevidence, current paragraph ID, open objections, affected dependencies.
- Actual runtime roles/model identity when known, never inferred from persona names.

Each response identifies versions reviewed. Reconcile stale responses before applying them.

## Evidence ledger

For each `S#`: title, author/organization, exact date/revision, URL or authorized path, access date for live material, actual reading depth, inspected body sections, supported claim, and limitations. Preserve printed page and PDF-viewer positions separately. Distinguish source assertions from corroboration and inference. Inspect cited material; do not invent absent metadata.

For each substantive `C#`: paragraph/version, claim, quotation/paraphrase/inference status, source/version, checked passage and real locator, population/period/units/denominator, intended citation, limitations, and verification result. See [source-and-citation-audit.md](source-and-citation-audit.md).

## Foundations and readiness records

Record conceptual definitions, operational measures, and justified proxies/thresholds. For each consequential `A#`, record assumption, justification, evidence status, affected claims, consequence if false, and sensitivity check or missing evidence. Preserve the question-to-conclusion logical framework and source compatibility notes using [research-foundations.md](research-foundations.md).

Map requirements and applicable feedback to document sections and checks. Record the readiness table from [completion-checks.md](completion-checks.md) for the exact final revision: result, evidence, and remaining action. Do not let agent agreement replace verification.

## Outline

For each `P#`: section, purpose, tentative claims, evidence IDs/locators, uncertainty/counterarguments, surrounding connections, dependencies, readiness. Record both roles' outline exchange before drafting any body paragraph.

## Paragraph discussion

Keep the context versions, intended contribution, Writer draft and claim-source mapping, actual Critic review, numbered objections `P#-O#` with significance and resolution criteria, Writer response and revised text, and Critic's final check with residual uncertainty.

Paragraph status: `planned`, `draft`, `under_review`, `reviewed`, `qualified`, `needs_evidence`, `deferred`, `needs_recheck`. Reviewed means the process ran, not proven true. Qualified paragraphs state their limits. Missing Critic checks remain unreviewed.

## Checkpoint and delivery

Record execution mode (`separate-agents` or `single-agent approximation`), actual role availability, budget/usage when exposed, context versions, completed reviews, failures, objections, pending outline changes, next action.

Run status: `in_progress`, `completed`, `partial`, `needs_input`, `budget_exhausted`, `cancelled`, `failed`. Complete only after whole-document review and reconciliation of substantive final edits. Deliver report/citations, reviewed outline, evidence ledger, paragraph discussions, and whole-document review/limitations. Separate the public report from private evidence excerpts.
