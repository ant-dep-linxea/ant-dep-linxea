# Holdout result: the tracer fails the gate

Date: 2026-11-18. Tracer: `scripts/trace-regression/trace_proto.py`, unchanged since the first backtest.

**Selection rule, fixed before running:** Bugs in EN/GROW/MS created since 2026-07-15, newest first. For each repo (website, Linxea-Mobile, Linxea-React, tunnels), take the 5 most recent with exactly one merged fix PR, excluding every case seen in the backtest.

## Verdict: gate failed

| Gate | Target | Result |
|---|---|---|
| Correct culprit or honest abstain | ≥80% | **10/20 (50%)**; 10/16 (62%) excluding crashes |
| Wrong culprit flagged `certain` | ≤10% | **4/20 (20%)** |

The first backtest's 9/9 was overfitted, as flagged at the time.

## Case by case

Ground truth comes from reading the fix commit and the blamed code. [Probable] unless stated.

| Bug | Tracer | Judgement |
|---|---|---|
| MS-766 anchor hidden by sticky header | website!21007 Rebranding, certain | ✅ The fix moves to `--hero-pull-up`, a rebranding header variable |
| MS-765 refuse images > 2048 px | website!26634, certain | ❌ certain. A feature filed as a Bug: no regression exists |
| MS-755 reward-year page metadata | none | ✅ abstain (missing since the page was created) |
| MS-747 rejected redirect shown "synced" | none | ✅ abstain (two plausible PRs) |
| MS-735 internal links to a 301 | none | ✅ abstain (content issue) |
| EN-4064 forget device kept the vault | Linxea-Mobile!25847 (biometry hardening), probable | ✅ That PR introduced the keep-biometry logout the fix bypasses |
| EN-3924 deposit for mandated children | — | ❌ **timeout**: `git blame -C` too slow on a Mobile file |
| EN-3903 draft not offered on retry | none (top: !21443 "defer creation") | ✅ abstain, and the right suspect was listed first |
| EN-3900 raw i18n key LinxeaAvenir2Plus | Linxea-Mobile!19181, certain | ❌ certain. A new product without a label, not a regression of that PR |
| EN-3845 (+3 tickets) UI fixes | none | ✅ abstain |
| EN-3898 iOS opens app on account-creation link | Linxea-React!21589, probable | ✅ It excluded the path but not its sub-paths |
| EN-3714 nationality exits unreachable | — | ❌ **crash**: the fix PR targeted feature branch `EN-3582-part-b`, since deleted |
| EN-3707 fund-origins Next ignores errors | — | ❌ **crash**: same feature branch |
| EN-3627 date picker + negative Y axis | Linxea-React!16983 (recharts migration), probable, latent 205 days | ✅ for the axis half |
| EN-3498 identity card stale | Linxea-React!21528, probable | ❌ The `structuralSharing` that froze the cache came from EN-1218 (Sept 2025); blame followed moved code |
| GROW-3315 empty field in validated row | tunnels!22787 Rebranding, probable | ❌ The local-copy design dates from 2024; Rebranding only touched it |
| GROW-3311 RenderView remount | — | ❌ **crash**: fix PR targeted feature branch `view-transitions` |
| GROW-3299 job category stays visible | none | ✅ abstain. The fix was a vital-ui bump, invisible to blame |
| GROW-3240 subtitle overflow (nbsp) | tunnels!24561, certain | ❌ certain. The MINOR subtitle line came from !23846 (#2 in the list) |
| GROW-3216 referral link disappears | tunnels!20200 "fix sonar warnings", certain | ❌ certain. It owns 10% of the lines; the logic dates from 2024 |

## Failure patterns

1. **Fix not merged straight to master (3 crashes).** Fix PRs into feature branches are common. *Engineering fix:* locate the fix commits on the default branch whatever the PR's target was.
2. **Blame too slow on some Mobile files (1 timeout).** *Engineering fix:* per-file timeout, and fall back to `-w` without `-C`.
3. **The recency rule crowns a minor recent toucher (GROW-3216, GROW-3315).** When most blamed lines are old, a PR that touched 10% of them recently gets named. *Rule fix:* a recent PR must also own ≥30% of all blamed lines, otherwise abstain or report "latent since <date>".
4. **Not a regression at all (MS-765, EN-3900).** The ticket is a feature, or the bug is new data (a new product). Blame always finds an owner, so **no blame threshold can fix this.**
5. **Moved code (EN-3498).** Blame credits the PR that moved the lines. Partial fix: `-C -C`. Even then, it won't be reliable.

## What this means for the design

Patterns 1–3 are fixable. Patterns 4 and 5 are not, and they are the more important ones: **the tracer cannot be trusted to write "Caused by" to Jira on its own.**

Redesign: the tracer becomes a **suspect list**, and a person or agent with the bug context confirms.

- It outputs the top 3 suspects with their share, age and review mode, plus dependency bumps on imported packages.
- In `ticket-to-pr` / `pr-open`, the agent fixing the bug already has the reproduction and the root cause. It picks one suspect, or `not a regression` / `unknown`, with one line of justification. The developer sees it in the PR description, where a wrong attribution is cheap to correct in review.
- Jira gets written only with a confirmed answer. Unconfirmed bugs stay `origin-unknown`, and the metric counts only confirmed ones.
- On this holdout, the true culprit was in the top 3 in most wrong cases: EN-1218 for EN-3498, !23846 for GROW-3240, the 2024 PRs for GROW-3216. Not measured formally yet.

## Next gate (before PR 1)

1. Implement fixes 1–3 and the suspect-list output.
2. **New holdout of 20 different bugs**, same selection rule, next ones down the list. Measures:
   - True culprit, or "not a regression", in the top 3 suspects: ≥80%.
   - No crash or timeout.
3. Then evaluate the confirmation step itself on 5 real bugs fixed with `ticket-to-pr`: does the agent pick right?
