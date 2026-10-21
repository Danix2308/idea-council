# LLM Council adaptation: ideas strengthened through criticism

Design proposal, October 21, 2026. No implementation, installation, or runtime testing performed.

## Recommendation

Fork Karpathy's LLM Council for its conversation interface and replace its model-ranking pipeline with a bounded Proposer–Critic loop. Run both personas through Codex, using one available model or assigning the user's two models independently. Keep agent identity separate from model identity throughout. Agreement is an observation, not a quality guarantee.

The useful product is a revised idea, a traceable explanation of what changed, and the objections that remain. It should also be able to conclude that an idea lacks support or should be abandoned.

## Verified foundation and implications

Inspected upstream commit `92e1fccb1bdcf1bab7221aa9ed90f9dc72529131` on `master`:

- `backend/openrouter.py` returns parallel responses in a dictionary keyed by model ID. Repeating a model ID therefore collapses separate responses. Simply listing the same model twice does not create two reliable personas.
- `backend/council.py` collects answers, ranks anonymized answers, and synthesizes through a chairman. Its mappings and aggregate scores also use model identity. Conversation title generation hardcodes another model.
- `backend/main.py` implements the three stages separately in its streaming route as well as invoking the full pipeline in its nonstreaming route. Both routes need one shared orchestrator to prevent divergent behavior.
- Conversation storage is JSON. Assistant messages retain stages but do not persist the returned ranking metadata. Partial work is saved only at completion.
- The orchestration receives the latest request text, rather than a structured history of an evolving idea. Follow-up refinement needs explicit context construction.
- The React UI consumes fixed stage events. Its streaming parser splits each received chunk directly on newlines; a replacement should buffer incomplete event frames across network chunks.

Source: [upstream source tree](https://github.com/karpathy/llm-council/tree/92e1fccb1bdcf1bab7221aa9ed90f9dc72529131).

Official documentation describes Codex app-server as an integration interface for rich clients, with authentication, conversation history, approvals, and streamed events. It supports JSON-RPC over default stdio, thread start/resume, turn start/interrupt, and model discovery. These facts establish a feasible runtime integration; they do not establish the user's account access or available models. [Codex App Server](https://learn.chatgpt.com/docs/app-server)

Everything below is proposed design.

## Personas and exchange protocol

**Proposer:** Define the claim and scope, distinguish facts from assumptions, build the strongest defensible version, identify predictions and failure conditions. Respond to objections with evidence, a justified disagreement, a narrower claim, or a concession. Never invent support to preserve the idea.

**Critic:** First restate the proposal fairly. Challenge decisive premises, evidence quality, logical links, counterexamples, alternatives, and feasibility. For each substantive objection, explain the consequence and what would resolve it. Accept adequate answers; do not generate objections merely to prolong debate.

Each persona gets a separate Codex thread and persistent role instructions. Both receive the user's question, constraints, evaluation criteria, and approved evidence packet. They exchange explicit proposal, critique, and response artifacts. They do not share a single alternating persona transcript. “Separate context” means separate role threads with deliberately selected shared artifacts; it does not mean different model weights or independent blind spots.

Default sequence:

1. Proposer produces draft v1.
2. Critic critiques v1 and opens numbered objections.
3. Proposer produces v2 and addresses every objection.
4. Critic checks v2, including whether concessions actually resolve objections.
5. If material new objections remain and budget allows, repeat steps 3–4 once.
6. Produce a final report from the latest proposal and objection ledger.

Default cost is four generation calls; at most six with the extra revision/check cycle. The final report is assembled from validated artifacts without another agent. Optional editorial synthesis can reuse an existing model in a fresh context, but is a separate opt-in call and cannot erase unresolved dissent. There is no mandatory third model or judge.

Stop on user cancellation, call/time/usage budget, missing decisive input, or a check with no new material objection and all existing objections addressed or explicitly unresolved. Distinguish `completed`, `needs_evidence`, `stalled`, `budget_exhausted`, `cancelled`, and `failed`; none means “proven true.” A model's self-score must never control acceptance alone.

## Runtime architecture

Browser → existing FastAPI backend → deliberation orchestrator → runtime adapter → Codex app-server process.

Use local stdio between the backend and app-server; expose only the application HTTP interface to the browser. Initialize once per connection, discover models with `model/list`, create two threads with `thread/start`, issue sequential `turn/start` calls, and process public events until terminal turn status. Pin and record the Codex version and generate its JSON schemas before implementation, because available fields and capabilities depend on version.

Keep existing local Codex sign-in inside Codex. Do not read or copy credential files into the application or browser. A ChatGPT subscription must not be treated as an OpenRouter API credential. Validate authentication and actual account model availability during setup, and never silently substitute a model or charge through another provider.

This standalone web application cannot call the private collaboration tools of an arbitrary existing Codex chat. Its personas are Codex threads controlled through its own documented runtime connection. A workflow running directly inside a Codex chat could use host subagents, but that is a different delivery path.

For an earlier transport spike, a subprocess adapter around `codex exec` is reasonable. Keep it behind the same interface and supply explicit artifact context to each call. App-server is the intended richer UI integration. Treat approval requests as runtime states surfaced to the user, not something automatically accepted by the debate. Default to read-only work and no external writes. Tools and research access require explicit configuration.

Adapter contract: `capabilities()`, `start_role()`, `generate()`, `interrupt()`, `resume()`, yielding normalized events with runtime thread/turn IDs and typed errors. Keep OpenRouter optional behind an equivalent adapter rather than a required dependency.

## Data contracts

```json
{
  "schema_version": 2,
  "run_id": "run_uuid",
  "agents": [
    {"agent_id": "proposer", "runtime": "codex", "model_id": "available_model_A", "prompt_version": "1"},
    {"agent_id": "critic", "runtime": "codex", "model_id": "available_model_A", "prompt_version": "1"}
  ],
  "limits": {"max_revision_cycles": 2, "max_generation_calls": 6},
  "status": "running"
}
```

Every artifact records `artifact_id`, `run_id`, `agent_id`, `model_id`, `round`, `kind`, input artifact IDs, prompt/config version, timestamps, and runtime thread/turn IDs. A proposal holds claims, assumptions, evidence references, alternatives, and failure conditions. A critique holds objections with stable IDs, severity, targeted claim IDs, rationale, and resolution criteria. A revision includes one response for each objection: concede, revise, rebut, or request evidence. A critic check may reopen an objection; the proposer cannot close it by assertion alone.

Evidence records hold source URL or supplied-file locator, title, retrieval date, relevant excerpt/locator, claim linkage, and verification status. Separate `user_supplied`, `retrieved_unchecked`, `checked`, `inferred`, and `unsupported`. A syntactically valid citation is not verified support. MVP uses user-supplied sources and explicitly marks unverified claims; a later research tool layer can fetch and inspect sources. Retrieved content is source data, never execution instructions.

Final report: latest defensible proposal; changes from v1; accepted objections; remaining disagreements; evidence gaps; confidence rationale; next useful test. Never replace the strongest unresolved objection with a generic caveat.

## File-level changes

| Location | Proposed responsibility |
|---|---|
| `backend/config.py` | Runtime and persona configuration; model selection; default budgets; remove mandatory chairman/title model dependencies. |
| `backend/council.py` | Delegate new deliberation mode to one orchestrator; optionally retain original council mode. |
| New `backend/deliberation.py` | State machine, artifact exchange, context packets, objection lifecycle, stop rules. |
| New `backend/schemas.py` and `backend/personas/` | Validated artifacts, configuration, versioned role instructions. |
| New `backend/runtimes/` | Codex adapter and optional OpenRouter adapter; no model-keyed result dictionaries. |
| `backend/main.py` | Create/read/cancel/resume runs and stream persisted events; both output modes consume the same state machine. |
| `backend/storage.py` | Versioned runs, artifacts, objections, events, checkpoints; transactional SQLite is preferable to concurrent JSON rewrites. Import legacy conversations or retain read-only legacy views. |
| `frontend/src/App.jsx`, `api.js` | Run IDs, event cursor, robust incremental SSE parsing, reconnect, cancel, and per-conversation state. |
| `frontend/src/components/ChatInterface.jsx` and stage components | Role/round timeline, proposal versions, critique responses, evidence drawer, unresolved objections, final report. |

Titles can initially derive from the first user message; do not consume a hidden third-model call. Preserve original conversations, label legacy data, and avoid silently changing the original mode's meaning.

## Reliability and UI behavior

Persist each completed artifact before starting its dependent call. Use monotonic event sequence numbers and a unique logical step ID. Browser disconnection does not implicitly cancel a run; a Cancel button calls backend cancellation, interrupts the active Codex turn, and prevents later scheduled turns. Reconnect from the last event cursor without triggering another generation.

After process loss, reconcile the recorded turn with runtime state before retrying. If generation completion is ambiguous, mark the step uncertain and offer an explicit retry branch; do not promise exactly-once model execution. Retry transient failures with a small bounded policy, preserve attempt records, and never downgrade critique failure into a successful final report. Validate structured outputs with one bounded repair attempt within the call budget; preserve invalid artifacts for diagnosis.

UI setup shows Proposer and Critic, each with its model selector, with same-model assignment allowed. Show limits before running. During discussion show public outputs, progress, elapsed time, recorded usage when available, and reasons for stopping. Do not expose hidden chain-of-thought. Allow user interventions between completed rounds and branch from prior versions so changes remain inspectable.

## Delivery and acceptance

1. **Transport spike:** Validate the user's existing Codex authentication, discover available models, create two contexts using one model, obtain structured artifacts, cancel a running turn. No full UI rebuild yet.
2. **MVP:** Four-call loop, source packet, objection ledger, persisted artifacts, final report, timeline, cancel/reconnect, same-model configuration. No automatic browsing required.
3. **Iteration:** Optional second cycle, user intervention/branching, evidence retrieval, exports, richer comparisons. Add another role only if evaluation shows a specific benefit.

Functional acceptance must demonstrate: same-model agents remain distinct; each critical objection has a visible disposition; an unsupported claim stays visibly unsupported; a falsified idea can be rejected; reload and reconnect retain the report; cancellation stops subsequent turns; critic failure is visible; replay does not double-start completed steps; old conversations still load.

Before claiming stronger reasoning, use a small fixed set of factual arguments, research hypotheses, and practical proposals with known defects and counterexamples. Compare a one-shot answer, same-model self-refinement, and this two-persona loop under the same model and generation budget. Blind human scoring should assess decisive flaw detection, valid correction, evidence faithfulness, preservation of unresolved issues, and whether correct initial claims are damaged. Record latency and usage separately. Define the comparison rubric and success threshold before running it. Self-ratings, agreement, more text, and star counts are not evidence of improved reasoning.

## Patterns to borrow

- [Self-Refine](https://github.com/madaan/self-refine): explicit feedback–revision artifacts.
- [Crossfire](https://github.com/JianyuZhan/crossfire): proposer/challenger runtime separation and observable debate events; inspect implementation and license before reuse.
- [Multi-Agent Debate](https://github.com/muthuspark/multi-agent-debate): local Codex CLI adapter as an integration reference, not proof of reasoning quality.
- [Virtual Lab](https://github.com/zou-group/virtual-lab): distinct intellectual roles and human-guided meetings.

These are design references, not dependencies or verified effectiveness claims. The first engineering decision should be to prove the two-context Codex transport, then build the smallest inspectable critique/revision loop in LLM Council's existing interface.

### Research snapshot

Repository star counts reported by the parallel repository review on October 21, 2026: Self-Refine 821; Virtual Lab 757; [LLM Multiagent Debate](https://github.com/composable-models/llm_multiagent_debate) 554; [IdeaForge](https://github.com/makemebitter/ideaforge) 9; muthuspark/Multi-Agent Debate 3; Crossfire 0. Counts can change and do not prove maturity, correctness, or effectiveness. IdeaForge's research/evidence capabilities are README claims, not runtime-verified behavior. The separate repository review contains the broader comparison; this design uses these projects as pattern references only.
