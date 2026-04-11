---
name: respond-pr-review-comments
description: Universal PR review manager. Runs a specialized Python script to fetch, decompose, and plan fixes for human and bot comments.
---

## Goal
Process pull request comments (human and bot) and generate a clear action plan.

## Universal Instruction (Gemini, Claude, Cursor, Copilot)
1. Run the analysis script: `python3 .agents/skill/respond-pr-review/scripts/analyze_pr.py {pr_url}`
2. Read the generated file: `review-actions-{pr_number}.md`
3. Resolve comments that need no code change (using GraphQL/API).
4. **STOP**: Present the generated `review-actions-#nnn.md` to the user. Do NOT proceed to fix the code unless a separate, explicit directive is issued.

## Why use the script?
- **Strict Separation**: The agent identifies "what" needs to be fixed and documents the "how" in a plan file, but does not touch the source code.
- **Token Efficiency**: Instead of reading 100+ comments into the context window, the script parses them locally and only presents the actionable items.
- **Portability**: The script works anywhere the `gh` CLI is installed.
- **Bot Logic**: The script automatically handles the complex nesting of CodeRabbit, CodeAnt, and Viper reports.
