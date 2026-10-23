# Blind baseline check

This optional check evaluates whether a Council run appears better than one fresh
whole-document draft. It is off by default because it costs two additional calls,
or one when the user supplies the comparison draft. It is one same-model-family
comparison, not a benchmark or proof of improvement.

The coordinator enables it only after disclosing that cost. The writer sees only
the current brief and evidence ledger. The judge receives anonymous files `X` and
`Y`, verifies claims against the supplied ledger/sources itself, and does not
reward length or confidence.

Scores are 0–10. For every criterion, 10 means consistently strong throughout; 7
means sound with limited omissions; 4 means mixed or materially incomplete; 0–2
means absent, seriously misleading, or repeatedly unsupported. Evidence support
(30%) asks whether claims are traceable to the ledger and whether unsupported
material was invented. Accuracy of use (20%) asks whether quotations, paraphrases,
statistics, denominators, and scope match the sources. Reasoning (20%) asks whether
inferences stay within evidence and consider alternatives. Honest uncertainty (15%)
asks whether limits are disclosed without a manufactured conclusion. Standalone
clarity (15%) asks whether terms and context are understandable outside the chat. A
`fatal` finding is a verified invented source, quotation, or statistic, or a
central false claim; a fatal document cannot beat a non-fatal one.

<!-- template:baseline-writer -->
Write the requested whole document in one pass using only these supplied files:

- Brief: {{brief_path}}
- Evidence ledger: {{ledger_path}}

Read both files. Do not use an outline, prior draft, review record, or unstated
source. Make only claims supported by the supplied material. State material limits
plainly. Return only the document.
<!-- /template:baseline-writer -->

<!-- template:baseline-judge -->
Read both documents fully before scoring either. Verify claims against the supplied
ledger and sources yourself. Do not reward length, fluency, or confidence. Score
evidence support, accuracy of use, reasoning, honest uncertainty, and standalone
clarity from 0–10: 10 consistently strong, 7 sound with limited omissions, 4 mixed
or materially incomplete, 0–2 absent/seriously misleading/repeatedly unsupported.
Set `fatal` true only for a verified invented source, quote, or statistic, or a
central false claim. If the documents are equally strong, say so in `reason`.

=== DOCUMENT X ===
{{x_document}}
=== END OF DOCUMENT X ===

=== DOCUMENT Y ===
{{y_document}}
=== END OF DOCUMENT Y ===

=== EVIDENCE LEDGER ===
{{ledger_text}}
=== END OF EVIDENCE LEDGER ===

Return exactly one JSON object and nothing else, using this exact format:

{
  "X": {
    "scores": {
      "evidence_support": 0,
      "accuracy_of_use": 0,
      "reasoning": 0,
      "honest_uncertainty": 0,
      "standalone_clarity": 0
    },
    "fatal": false
  },
  "Y": {
    "scores": {
      "evidence_support": 0,
      "accuracy_of_use": 0,
      "reasoning": 0,
      "honest_uncertainty": 0,
      "standalone_clarity": 0
    },
    "fatal": false
  },
  "reason": "One sentence naming the decisive difference."
}
<!-- /template:baseline-judge -->
