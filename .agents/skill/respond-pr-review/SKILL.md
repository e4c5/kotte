---
name: respond-pr-review-comments
description: Universal PR review manager. Runs a specialized Python script to fetch, decompose, and plan fixes for human and bot comments.
---

## Goal
Process pull request comments (human and bot) and generate a clear action plan.

## Universal Instruction (Gemini, Claude, Cursor, Copilot)
1. Run the analysis script: `python3 .agents/skill/respond-pr-review/scripts/analyze_pr.py {pr_url}`
2. Read the generated file: `review-actions-{pr_number}.md`
3. Resolve comments that need no code change.
4. Execute the plan for items that do require code changes.

## Why use the script?
- **Token Efficiency**: Instead of reading 100+ comments into the context window, the script parses them locally and only presents the actionable items.
- **Portability**: The script works anywhere the `gh` CLI is installed.
- **Bot Logic**: The script automatically handles the complex nesting of CodeRabbit, CodeAnt, and Viper reports.
