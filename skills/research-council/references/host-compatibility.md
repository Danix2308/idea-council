# Host compatibility

Read at setup. Use the tools actually exposed in this session; do not invent API names, tool results, model identities, or agent exchanges.

## Codex

Invoke as `$research-council` or select the installed skill. Use the host's available delegation mechanism for separate Writer and Critic contexts. `agents/openai.yaml` is Codex interface metadata, not a portable agent definition. Pass the role instructions and current context explicitly.

## Claude Code

Invoke the installed skill as `/research-council` followed by the task. The main conversation coordinates the work. When the session exposes delegation, use separate general-purpose subagents for Writer and Critic, supplying the relevant instructions from [roles.md](roles.md) and the complete versioned context packet to each. Use the current tool schema; some versions expose Agent and older versions may expose Task. No extra tool or provider is required by this skill.

Keep role identities distinct when resuming agents. If a role must restart, supply its current context and prior actual records. Do not assume a subagent inherits this skill or the main chat history. Do not delegate the coordinator into a subagent that cannot itself delegate. Retain the outline-before-prose gate and actual revised-text checks.

## Claude web, desktop chat, and Cowork

Invoke by asking to use the Research Council skill in ordinary language after enabling it. Do not require Codex's `$` syntax or Claude Code's slash command in ordinary chat.

Check whether the current session actually exposes separate-agent delegation. If it does, coordinate Writer and Critic as above. Otherwise announce `single-agent approximation` before starting and use visibly separate drafting, critique, revision, and checking stages. These are one assistant's sequential work, not independent reviewers. Keep the outline review and all evidence checks; label paragraph and final reviews as self-review. Do not invent transcripts or claim a second agent signed off. If the user requires separate agents, report that requirement as unmet and offer an environment with delegation rather than silently substituting self-review.

Use accessible attachments and enabled research tools. Without source retrieval, restrict claims to inspected supplied evidence and identify missing sources. Save records as downloadable files when file creation is available; otherwise provide labeled records in the conversation. Local computer paths are not accessible merely because the user mentions them. No automatic access to other chats or projects is implied.

## Every host

Record host, `separate-agents` or `single-agent approximation`, actual tool/source availability, context versions, and any unperformed checks in the brief and final delivery. Separate agent contexts can still use the same underlying model and are not proof of factual independence. Preserve user and organization permissions. A missing tool does not authorize installing software, changing settings, purchasing access, or publishing material.
