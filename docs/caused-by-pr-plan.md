# Plan: "caused by PR" on Jira bugs, via frontend-instructions

Goal: every front Bug that reaches master gets a machine-readable link to the PR that introduced it, so we can measure **escaped defects per merged PR**. That lets us split them by reviewed vs self-approved vs bypassed, by sensitive path, and later by AI-reviewed or not.

## Facts this plan rests on (checked 2026-11-18)

| Fact | Consequence |
|---|---|
| 297 Bugs created in EN/GROW/MS since 2026-08-18; only 4 carry an `is caused by` / `created by` link | No usable defect metric today |
| Jira already has link type `Problem/Incident` (`causes` / `is caused by`) and `Defect` (`created` / `created by`) | Ticket-to-ticket causality needs no Jira admin |
| 670 of 1,360 merged app PRs (49%) have no real ticket key (`EN-0`/`X-0` or none) | A ticket-to-ticket link alone misses half the culprits, so **the PR web link is the primary record** |
| Merge strategy is `rebase`: master commits keep the branch commit subject (`EN-4071/chore(...)`), with no `Merged PR NNN` | Commit → PR needs an Azure DevOps lookup; the ticket key in the subject is a fast first hint |
| `create-ticket/references/jira-workspace.md` already centralises Jira field IDs and link conventions | Store the new conventions there; skills reference it |

## Data model (no Jira admin needed)

On the **Bug** ticket:

1. **Web link** (`createJiraIssueRemoteIssueLink`) to the culprit PR URL, titled `Caused by PR <repo>!<id>`. This is the primary record and works for ticketless PRs. Check `listJiraIssueRemoteIssueLinks` first, because duplicates can't be removed.
2. **Issue link** `Problem/Incident`: Bug `is caused by` culprit ticket, only when the culprit PR has a real ticket key. It's JQL-native.
3. **One origin label**, JQL-searchable:
   - `origin-front-regression`: a merged front PR caused it (1 + 2 apply).
   - `origin-preexisting`: the bug predates the culprit search window, or is legacy.
   - `origin-backend`, `origin-third-party`, `origin-content`: not front code.
   - `origin-unknown`: the trace found nothing conclusive. Keep this honest rather than forcing a culprit.
4. A **comment** with the trace evidence: blamed lines, confidence, culprit merge date.

Later (optional, needs a Jira admin): replace the labels with a select field "Bug origin" and make it required on the transition to `Terminé(e)`/`DONE ✅`. That's the only way to cover bugs fixed outside the Claude skills.

## Repo changes in frontend-instructions (3 PRs, in order)

Constraints: ≤100 lines per instruction file (130 absolute), a release fragment per PR, `tests/` wiring and frontmatter suites green, and `azdo-guard` must allow any new Azure DevOps call. Check that before writing the script.

### PR 1: the tracer (core, testable in isolation)

- **New `shared/.claude/skills/trace-regression/`**:
  - `SKILL.md`, model sonnet, effort medium.
  - `trace.sh`, deterministic and read-only.
  - `references/confidence.md`.
- **Input:** a fix diff (`<target>..HEAD`) or `file:line` list. **Output:** one block, `Caused-by: <repo>!<id> | ticket <KEY or none> | merged <date> | confidence certain/probable/none`.
- **Algorithm:**
  1. Take the lines removed or modified by the fix, then run `git blame -w -C -C --ignore-revs-file` on the target branch to get candidate commits. Skip format-only and lockfile commits (keep an ignore list).
  2. For each commit, find its PR by asking Azure DevOps for completed PRs whose commits include the SHA, with the subject's ticket key as a hint. Pick the right read-only endpoint while writing `trace.sh`. Rebased SHAs may need a match on subject plus date; test this on real data first.
  3. Confidence: **certain** if one PR owns all blamed lines; **probable** if one PR owns most of them; **none** otherwise, or if the culprit merged more than 12 months ago (→ `origin-preexisting`).
- **Backtest before merging:**
  - The 5 known reverts: 2 were bypassed auth PRs, `Linxea-React!25966/25967`.
  - 20 recent EN/GROW Bugs with a fix PR, checked by hand.
  - Target: ≥80% agreement on `certain`/`probable`. Below that, fix the tracer before wiring it anywhere.
- **Jira write conventions:** a section added to `create-ticket/references/jira-workspace.md` covering the data model above, link type names (resolved at runtime via `listJiraIssueLinkTypes`, never hardcoded), and label list.

### PR 2: hook it into the bug-fix paths

| Where | Change |
|---|---|
| `ticket-to-pr` → `references/investigate-plan.md` Step 4 (Bug) | After reproducing, run `trace-regression` on the suspected area for a provisional culprit. This also informs the plan. |
| `ticket-to-pr` → `references/closing-steps.md` Step 11 | For Bug tickets, rerun the trace on the final fix diff, then write the web link, the issue link if there's a ticket, the label and the evidence comment. Never block the close-out on a failed write; report it. |
| `pr-open` Step 5 | If the title type is `fix`, add a `Caused by:` line to the description (from the conversation, else run the trace, else `none found`). This covers fixes made outside `ticket-to-pr` that still go through `pr-open`. |
| `systematic-debugging` Workflow step 5 | After the fix is verified, run the trace and report the culprit. Jira writes stay with the ticket flows. |
| `mobile/.claude/skills/bug-investigation` report template | Add `Caused by PR` plus "was it reviewed / self-approved / bypassed?" under *Causes*. This feeds its "step that failed". |
| `create-ticket` (type Bug) | Accept an optional `--caused-by <repo>!<id>` and apply the same writes. Never ask when it's unknown. |

### PR 3: the metric

- **New `shared/.claude/skills/escaped-defects/`**, `disable-model-invocation: true`, run by a person every two weeks. Mirror `review-stats`.
  - JQL: Bugs labelled `origin-*` in the window. Read their web links, join them with the Azure DevOps PR data (bypass flag, other-human approval, changed paths), and print one table: escaped defects per 100 merged PRs, split by review mode, by sensitive path and by repo.
  - It also prints **coverage**: share of Done Bugs with an `origin-*` label. Below 70%, the numbers aren't usable yet.
- **`ticket-status-sweep`:** list Done Bugs in the sprint with no `origin-*` label, as a reminder only, with no auto-write.

## What this will and won't catch

- **Catches:** bugs fixed through `ticket-to-pr`, `pr-open`, `systematic-debugging` or `bug-investigation`, in the synced repos (Linxea-React, tunnels, website, Linxea-Mobile).
- **Misses:**
  - Bugs fixed by hand without these skills (until the optional required field exists).
  - Backend-caused bugs fixed in front (they get `origin-backend`, which is fine).
  - Bugs caught before merge. Those aren't escapes, so they're excluded by design.
- **Time to detection matters:** a bug found 3 months after its PR merged shows up late. Read the metric with a lag of at least 1 sprint, and backfill using the 297 existing Bugs (run the tracer on their fix PRs) to get a baseline now instead of in 3 months.

## Order and effort (estimates)

1. **Today:** run the tracer logic by hand on the 5 reverts and 5 recent Bugs to validate the commit → PR lookup under `rebase`. That's the riskiest assumption.
2. **PR 1:** tracer, backtest, and conventions in `jira-workspace.md`. About 1–2 days.
3. **PR 2 + PR 3:** hooks and metric, plus a backfill of the 297 Bugs. About 2 days.
