# Use Research Council with Claude

This guide is for people who do not use GitHub or write code. Ask the sender for `research-council.zip`; a private repository link alone does not grant access. You do not need a GitHub account when someone sends you the ZIP.

## Install in Claude web or desktop

1. Save `research-council.zip` from the email to Downloads. Leave it zipped.
2. Open [Claude](https://claude.ai) and sign in to your existing account, or open the Claude desktop app.
3. Open Settings, then Capabilities. Enable **Code execution and file creation**, called **Create and edit files** in the updated layout.
4. Open **Customize > Skills**. Click **+**, then **Create skill**, then **Upload a skill**.
5. Select the saved ZIP. When Research Council appears, turn its toggle on.
6. Start a new conversation. Attach a short source you know well using the attachment button, and paste the test prompt below.

Labels may change. If upload or file creation is missing on a managed school/work account, ask its administrator whether those features are enabled. See [Anthropic's current skill instructions](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

The package needs no separate API key or model subscription of its own. It uses the capabilities and usage allowance available in your Claude account. Uploading it does not add tools your account lacks or remove usage limits.

## Activate and test

Paste this into the new conversation:

```text
Use the Research Council skill. First confirm you have loaded it and state whether you can use actual separate Writer and Critic agents. If not, label the process single-agent approximation and identify critiques as self-review.

Using only the attached source, write a short explanatory article for a general audience, approximately 500 words. Review the full paragraph outline before drafting. For every paragraph, show a draft, critique of its claims and evidence, revision, and check of the revised text. Cite real source locations, distinguish findings from interpretation, and flag missing support. Finish with a whole-document review. Provide the article, outline, source ledger, and review records as downloadable files if available.
```

Read the resulting article alongside the original source. To inspect the review, send:

```text
Show three concrete examples of claims you narrowed, removed, or supported more carefully during review. For each, show the original wording, the objection, the revised wording, and the supporting source location. If you do not have three actual examples, say so. List unresolved weaknesses and whether each check was self-review or a separate agent's review.
```

If Claude says it cannot find the skill, confirm the toggle is on and start a new chat. Ask it to confirm it read the installed instructions rather than merely adopting the skill's name. Re-upload an updated ZIP when you receive a new version. This project's upload has not been tested through a live Claude web account; installation errors should be reported with the exact message.

## Claude Code, for users who already have it

Copy the complete `research-council` folder into your project's `.claude/skills/` folder, preserving the supporting files. For all local projects, use `~/.claude/skills/` instead. Start a new Claude Code session in your project and type:

```text
/research-council Research [topic] for [audience], using the sources in this folder. Use separate Writer and Critic agents if available, retain actual review records, and disclose any unavailable capability.
```

The coordinator uses available general-purpose subagents; no custom agent configuration is required. If delegation is unavailable or disallowed, it reports that limitation. Local folders and account-uploaded skills have different scopes; for Cowork, use the account upload above. See [Claude Code skills](https://code.claude.com/docs/en/skills) and [subagents](https://code.claude.com/docs/en/sub-agents).

## What feedback helps

Note specific paragraphs where a claim exceeds the source, evidence is too thin, analysis is missing, or a conclusion does not follow. Check whether revision resolves the reasoning problem or just changes the wording. Report setup difficulties separately from writing-quality findings. Agreement between roles does not establish truth.
