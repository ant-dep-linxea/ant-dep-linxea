# Overnight recap: 2026-11-18 → 19

## TL;DR

- **The tracer works as a suspect list.**
  - On 14 real regressions it had never seen, the true culprit was in its top 3 for 12 (86%; small sample).
  - It never names the culprit alone: a person confirms.
- **PR 1 opened as a draft.** frontend-instructions !27077 adds the `trace-regression` skill.
  - Independent review: 0 blockers; the 6 should-fix and 2 nits are fixed.
  - Full suite green: 2,818 tests.
- **PR 2 opened as a draft, stacked on PR 1.** It wires the skill into `ticket-to-pr` (Bug close-out) and `pr-open` (fix PRs). Details below.
- **Nothing is merged and nothing is written to Jira.** Branch policies and settings are untouched.

## What you need to do

1. **Spot-check 5 of my verdicts** in `docs/caused-by-pr-holdout-2.md`: MS-732, EN-3803, EN-3756, GROW-3182, EN-3257. I judged them while having built the tool. If 2 or more are wrong, the 86% does not hold.
2. **Review PR 1 (!27077), then publish it** (it is a draft, so no reviewer has been notified). CI was still "queued" when I stopped. I cannot read builds from here (the builds API answers 401 through the proxy), so check that it ran.
3. **Then PR 2**, retargeted to master once PR 1 is merged.

## PR 1: frontend-instructions !27077 (draft), branch `adepertat/trace-regression`

`shared/.claude/skills/trace-regression/`:
- `scripts/trace-regression.mjs`: a Node port of the prototype, so it runs on Windows machines too.
  - Read-only: git plus Azure DevOps GET.
  - Auth follows the existing `review-stats.sh` pattern: an Entra token through `az`, or the proxy in a cloud session.
- `SKILL.md`, 61 lines:
  - Step 1 traces.
  - Step 2 asks the user which suspect, "Pas une régression", "Montée de dépendance" or "Inconnu".
  - Step 3 writes to the Jira Bug only after a second confirmation.
- `references/jira-writes.md`: a web link to the PR, an `is caused by` link (link type `Problem/Incident`, direction checked through the MCP), an `origin-*` label and a comment in French.
- `tests/unit/trace-regression.test.ts`: 12 tests. They cover matching by SHA, by rebase (author e-mail + author date) and by merge commit, the squashed feature branch, mechanical PRs, and `diff.noprefix`.

**What the review caught and I fixed:**
- A user's git config (`diff.noprefix`, difftastic) silently emptied the trace.
- Squash and no-ff PRs were never resolved and were wrongly reported as "predates history".
- A hard-coded 2025 cutoff on PR paging.
- Sonar and lint PRs were dropped silently; they are now reported.
- `allowed-tools` was too broad (it pre-granted Jira writes).

**Found while testing the port:** when the fix went through a feature branch, the top suspect can be a PR that landed *after* the fix (EN-3714). That bug probably never reached master. Such PRs are now labelled "landed with or after the fix" and never suggested.

## PR 2 (stacked): wiring

- `ticket-to-pr` (shared and mobile override), Step 11: for a Bug ticket, run `/trace-regression --bug <KEY>`. The user picks the answer; a failed trace never blocks the close-out.
- `pr-open` Step 5: on a `fix` PR, add a `Suspects (non confirmés)` line, so reviewers see the candidates.

## Not done, and why

- **Sync dry-run:** the container has no `az`. `sync/` is unchanged.
- **PR 3 (the escaped-defects metric skill):** not started. It needs PR 1 merged and a few weeks of confirmed origins. Main design point from the data: 10 of 14 regressions came from PRs older than 180 days, so the metric must group culprits by merge month, and the bypass vs review signal will take months to accumulate.
- **Found, outside scope:** `create-ticket/references/qa-tickets.md` puts the cause as the *outward* issue, which reverses the `is caused by` link (per the MCP tool's own description). It needs a small separate fix.

## Where things are

- **This repo** (`adepertat/adoring-pascal-3qj1ia`):
  - `docs/code-review-pilot.md`: review baseline and pilot.
  - `docs/caused-by-pr-plan.md`: the plan.
  - `docs/caused-by-pr-backtest.md`, `docs/caused-by-pr-holdout.md`, `docs/caused-by-pr-holdout-2.md`: the tests.
  - `scripts/`: the prototypes.
- **frontend-instructions:** branches `adepertat/trace-regression` (PR 1) and `adepertat/trace-regression-wiring` (PR 2).
