---
name: respond-pr-review-comments
description: Analyze top-level pull request review comments from a PR URL, resolve comments that need no code change, and write a markdown action plan for comments that require code updates.
---

You take exactly one argument: a GitHub pull request URL.

## Goal

Process pull request **top-level review comments** one at a time (the first comment in each review thread, where `replyTo == null`; ignore replies), decide whether each needs a code change, and:

- Immediately resolve comments that do **not** require code changes.
- Create a markdown-formatted plan file for comments that **do** require code changes, using the required `review-actions-#nnn` pattern (replace `#nnn` with the PR number, for example `review-actions-123`).

## Steps

1. Parse `{owner}`, `{repo}`, and `{pr_number}` from the PR URL.
2. Retrieve PR context with:
   - `gh pr view {pr_url} --json number,title,body,baseRefName,headRefName,files`
   - `gh pr diff {pr_url}`
3. Retrieve both **review threads** and **issue comments** (conversation comments) via GraphQL and paginate until done:
   - `repository.pullRequest.reviewThreads` (include `isResolved`, `isOutdated`, and `comments`)
   - `repository.pullRequest.comments`
4. For each thread or issue comment:
   - Skip if already resolved or **outdated** (for threads).
   - If it is a bot comment (author: `coderabbitai`, `codeant-ai`, `viper-review`):
     - Look for nested reports (e.g., `<details>` blocks titled "Actionable comments", "Nitpick comments", or lists of findings).
     - Decompose these reports into individual items for analysis.
   - Otherwise, select the top-level comment only (`replyTo == null` for threads; non-reply issue comments).
5. For each identified comment or decomposed item, validate against diff and surrounding file context and classify:
   - **Resolvable now**: comment can be addressed without code changes (already fixed, misunderstood, or no-op).
   - **Needs code change**: valid feedback that requires code edits.
6. If **resolvable now**, resolve the thread immediately (for review threads) or acknowledge the bot (e.g., with a reaction or reply if relevant).
7. If **needs code change**, append an item to `review-actions-#nnn`.
   - Thread/comment URL
   - File and line context with 1-indexed line numbers:
     - Single line: `path/to/file.ext:<line-number>` (example: `src/app.js:52`)
     - Line range: `path/to/file.ext:<start-line>-<end-line>` (example: `src/app.js:52-55`)
     - Deleted line: `path/to/file.ext:deleted@<old-line>` (example: `src/app.js:deleted@49`)
     - Mixed added/deleted range: include both in one field (example: `src/app.js:52-55; deleted@49`)
   - Why code change is needed
   - Concrete implementation plan for a follow-up coding agent
   - Risks/edge cases and validation notes

## Output requirements

- Produce `review-actions-123` in markdown format (replace `123` with the current PR number). If the file already exists, append a new run section with timestamp and keep prior sections for history.
- If every top-level review comment is resolved directly, still create the file and record that no code changes are required.
- Do not include reply comments in analysis or planning.
