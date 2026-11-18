# Step 1 result: tracing bugs back to the PR that caused them

Date: 2026-11-18. Prototype: `scripts/trace-regression/trace_proto.py`. Read-only: local `git blame` plus Azure DevOps GET calls.

## Verdict

**Feasible.** Commit → PR lookup works under the `rebase` merge strategy, and the tracer gives a defensible answer on 9 of 9 backtest cases (8 named culprits, 1 honest abstain).

That score is **optimistic**: three rules were tuned on these same 9 cases. It needs a fresh holdout before anything is wired into the skills (see "Gate for PR 1").

## How it works (what survived the backtest)

1. **Locate the fix on master.** Match its PR commits by SHA, else by author email plus author date. Rebase keeps both; subjects are unreliable, because git joins multi-line subjects. Working from master and not from PR status matters: `Linxea-React!25966` is "completed" but its commit never reached master.
2. **Blame the old side of the lines the fix removed or modified** (`git blame -w -C`). Pure-addition hunks blame their neighbouring lines. Import/export lines, lockfiles, snapshots, generated `kubb` code and CHANGELOG are skipped.
3. **Map each blamed commit to its PR.** Take completed PRs closed within 2 days after the commit, and match SHA or email+date against the PR's commit list. Direct pushes (the frontend-instructions sync) resolve to "no PR", as they should.
4. **Skip mechanical PRs** (named exports migration, format, lint, sort-keys, rename), which own many lines without changing behaviour.
5. **Decide:**
   - One PR owns ≥60% of the blamed lines → that PR, whatever its age (`certain` at ≥80%), flagged `latent N days` if older than 180 days.
   - Otherwise, the top PR among those merged in the last 180 days (`certain` ≥80% / `probable` ≥50% / else `none`).
6. **List dependency changes from the 30 days before the fix.** Blame can't see a bump that changes behaviour.

**Runtime: 3–7 s per bug on a full clone.** On a blobless clone it timed out at more than 280 s, because blame fetches blobs one by one. Developer checkouts are full clones, so this only matters for CI or cloud runs.

## Backtest

| Case | Ground truth | Tracer | OK? |
|---|---|---|---|
| Revert `Linxea-React!25967` (password field) | !25916, by title | !25916, certain | ✅ |
| Revert `Linxea-React!24447` (Intercom) | !23825, by title | !23825, certain | ✅ |
| Revert `utils!23227` (sonar) | !22941, by title | !22941, certain | ✅ |
| Revert `tunnels!24020` (product cache) | !24002, by title | !24002, probable | ✅ |
| MS-736: simulator rendered twice (`website!26046`) | Dual-layout design from Feb 2026, read from code | !16884 "Simulator", certain, **latent 262 days** | ✅ |
| GROW-3411: birth city lost on same country (`tunnels!26386`) | !24403 added the reset on country change [Probable] | !24403, probable | ✅ |
| GROW-3358: address error while typing (`tunnels!25918`) | !24399 "adapt blur triggers to react-hook-form 7.90" edited exactly those forms [Probable]; alternative is the react-hook-form 7.91 bump | !24399, certain, plus the bump listed as a suspect | ✅ probable |
| EN-3835: `isDevelopment` ignores `aws-` (`Linxea-React!25510`) | !23963 made isPreprod/isProduction ignore `aws-` but not isDevelopment [Probable] | !23963, probable | ✅ probable |
| EN-4024: alert banner margin (`Linxea-React!26711`) | Ambiguous between Rebranding !22788 and !23554 | none (top 25%) | ✅ abstain |

Before the rule fixes, the first prototype got 2 of the 5 real bugs wrong:
- **MS-736:** a cosmetic Rebranding edit was picked because the 180-day filter dropped the real, older culprit. Fixed by the dominant-owner rule.
- **GROW-3358:** a mechanical exports refactor was picked. Fixed by the mechanical-PR skip.

## What we learned that changes the plan

- **Latent bugs are common enough to matter.** MS-736 shipped 262 days before it was reported. The metric has to read "defect caused by PR X, detected N days later". A 30-day window would miss it.
- **Dependency bumps are a blind spot for blame.** The suspect list is too noisy as is (always ~6 entries). PR 1 should filter it to packages imported by the files the fix touched.
- **Review mode of the 7 culprits found in the PR data window:**
  - 4 were approved by another person with 0 comments.
  - 3 were completed with policy bypass: !23825 (1 approval, 6 comments), !24399 (0 approvals, 24 comments), !23963 (1 approval, 0 comments).
  - Too few to conclude anything, which is why the metric needs volume.
- **Correction to my earlier message:** the bypassed auth PRs were the *reverts* (!25966/!25967). The culprit !25916 itself went through normal approval.

## Gate for PR 1 (frontend-instructions)

1. **Holdout:** run the tracer, unchanged, on 20 more Bugs it has never seen (EN, GROW and MS, including Linxea-Mobile). Review each by hand. Ship only if ≥80% are correct or honest abstains, and ≤10% name a wrong culprit with `certain`.
2. Filter dependency suspects by imports of the touched files.
3. Port to the skill format (`trace.sh` or node, ≤100-line SKILL.md), check `azdo-guard` allows the GET calls, add a release fragment.
