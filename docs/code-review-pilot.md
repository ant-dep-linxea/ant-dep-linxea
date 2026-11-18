# Code review at Linxea: baseline and AI-review pilot

Status: draft v1, for team discussion. Data window: PRs created 2026-08-18 → 2026-11-18 (13 weeks), all repos of the `Linxea-React` and `Linxea-Mobile` Azure DevOps projects. Reproduce with `scripts/review-baseline/`.

## TL;DR

1. **Review speed is not our problem.** Median time to first human review is 30 min; median time to merge is 1.1 h.
2. **Review coverage is.** 47% of human-authored PRs (750) merged without approval from anyone other than the author. Two mechanisms explain it:
   - **Policy bypass (491 of the 750).** 568 PRs were completed with "override branch policies". In 533 of them the author completed their own PR, and two people account for ~88% of all bypasses. The most common reasons entered are "good" (345) and "fine" (37).
   - **Self-approval counts (most of the remainder).** On the main branches of `Linxea-React`, `Linxea-Mobile`, `design-system` and `frontend-instructions`, branch policy counts the author's own vote (`creatorVoteCounts: true`). The `rebrand`/`rebranding` branches have no review policy at all.
3. **Sensitive code is included.** ~32% of merged PRs touching auth, money/signature, identity or pipeline/dependency files had no approval from another human (approximate, path-regex based; see caveats).
4. **Revert rate (0.3%) is useless as a quality metric here.** Too rare to move. We need an escaped-defect metric before changing anything.

Consequence: the Anthropic-style "AI reviews, humans only on risk" model would, today, be *adding* review rather than replacing it. The first job is to make the human gate real on risky paths; AI review comes second, as an extra layer.

## 1. Baseline (measured)

Human-authored PRs only (89 bot PRs excluded). "Other-human approval" = a positive vote (approve / approve with suggestions) by someone other than the author, bots and groups excluded.

| Repo | Merged (per wk) | Abandoned | Time to merge p50 / p90 | First human review p50 / p90 | No other-human approval | No other-human comment | Fix/hotfix PRs |
|---|---|---|---|---|---|---|---|
| **All** | 1595 (~123) | 9% | 1.1 h / 71 h | 0.5 h / 28 h | **47%** | 70% | 40% |
| Linxea-React | 207 (~16) | 18% | 3.4 h / 88 h | 0.7 h / 39 h | 36% | 60% | 32% |
| Linxea-Mobile | 396 (~30) | 5% | 2.8 h / 91 h | 0.5 h / 29 h | 20% | 60% | 50% |
| website | 351 (~27) | 10% | 0.4 h / 67 h | 0.4 h / 17 h | **61%** | 66% | 51% |
| frontend-instructions | 292 (~22) | 1% | 0.5 h / 14 h | n/a | **97%** | 99% | 19% |
| tunnels | 189 (~15) | 14% | 2.9 h / 138 h | 0.7 h / 64 h | 16% | 57% | 37% |
| design-system | 110 (~8) | 13% | 1.0 h / 42 h | 0.8 h / 26 h | 30% | 73% | 52% |

Other observations:

- **Volume is rising:** 482 merged in September, 651 in October, 410 in the first 18 days of November (on pace for ~680).
- **Authorship is concentrated:** the top author wrote 41% of merged PRs, and the top two wrote 60%. A review policy that relies on peers will be capacity-bound by 2–3 people.
- **Approval without comment** (rubber-stamp proxy) ranges from 17% (website) to 45% (design-system). This is a proxy, not proof. A clean PR legitimately gets no comments.
- **Reverts:** 5 in 13 weeks (0.3%).
- **An automated quality bot already runs.** "Code quality (front)" comments cover coverage on changed lines, lint, duplication and vulnerable dependencies (~0.4 comments/PR overall, ~0.9 on Linxea-React and tunnels). That is our deterministic layer; an AI reviewer would sit on top of it.

### Unreviewed merges on sensitive paths

Merged PRs in Linxea-React, Linxea-Mobile, website and tunnels, classified by changed file paths:

| Category | PRs touching it | Merged with no other-human approval |
|---|---|---|
| auth (login, session, oauth, account recovery) | 101 | 21 (21%) |
| money / signature (transactions, payments, subscription, signature codes) | 167 | 17 (10%) |
| identity / personal data (identity, KYC, personal information, customer profile) | 66 | 21 (32%) |
| pipeline / dependencies (pipelines, YAML, package manifests, lockfiles) | 264 | 131 (50%) |

Worst spots: website (identity 78% and pipeline/deps 70% unapproved), and Linxea-React (money/signature 43%, auth 36%).

### Branch policy facts (read-only check)

- `Linxea-React` master, `Linxea-Mobile` main, `design-system` main and `frontend-instructions` master: minimum 1 reviewer **with creator vote counting**. The website's required-reviewer policy also counts the creator.
- Branches `preprod`, `recette`, `release`, `rq-main`, plus `tunnels`/`utils` master, already have `creatorVoteCounts: false`. The team already uses the stricter setting elsewhere.
- Path-scoped required reviewers exist only for `.editorconfig` and `azure-pipelines*.yml` on `Linxea-React` `release`.
- **Bypass is the main hole, more than `creatorVoteCounts`.** Policy bypass is used on 36% of merged PRs (568/1595): 185 in September, 280 in October. Tightening `creatorVoteCounts` alone changes nothing while bypass permission stays with the same people who author most PRs.

| Repo / target | Unapproved merges via bypass | Unapproved merges without bypass |
|---|---|---|
| Linxea-Mobile main | 62 | 0 (+5 on `rebrand`) |
| Linxea-React master | 53 | 0 (+15 on `rebranding`) |
| website master | 132 | 39 (+42 on `rebranding`) |
| design-system master | 31 | 0 |
| tunnels master | 25 | 0 |
| frontend-instructions master | 168 | 102 |

### Caveats

- Path categories are regex matches on file paths. They over-match (e2e tests and docs inside an `auth/` folder count) and under-match (sensitive logic in a generic `utils/`). Treat them as orders of magnitude, not exact counts.
- Approvals given verbally or in a pairing session are invisible here.
- "Fix/hotfix" is parsed from PR titles (conventional-commit prefix). It counts intent, not escaped bugs.
- August is partial (from the 18th).

## 2. What we are NOT doing

- No reduction of human review in this pilot.
- No AI approvals: the AI reviewer comments, it never votes approve.
- No auto-merge driven by AI.

## 3. Proposal

### Step 1: make the human gate real where it matters (decision for repo owners)

Proposed policy change, not applied, to be decided by whoever owns branch policies:

0. **Restrict "bypass policies when completing pull requests"** to an emergency role, and require a real reason (hotfix ticket ID), reviewed fortnightly. Without this, the items below are cosmetic.
1. Set `creatorVoteCounts: false` on the default branches of Linxea-React, Linxea-Mobile, website and design-system. This aligns them with `preprod`/`release`, which already do it. Put the same policy on long-lived branches (`rebrand`, `rebranding`).
2. Add path-scoped required reviewers on sensitive paths (list below). These are deterministic Azure DevOps path filters, auditable and not decided by an LLM.
3. Keep author self-approval possible only for explicitly low-risk paths if the team wants speed there (docs, copy, `frontend-instructions`), via separate path policies.

Draft mandatory-review path list, to validate with each repo's leads:

- Auth: `**/auth/**`, `**/authentification/**`, `**/account-recovery/**`, `**/oauth/**`, `**/mcp-oauth/**`
- Money and signature: `**/transaction/**`, `**/payment*/**`, `**/signature/**`, `**/verificationCode/**`, `**/subscription*/**`, `**/sourceOfFunds/**`
- Identity and personal data: `**/identity/**`, `**/personalInformation*/**`, `**/customerProfile/**`, `**/DCRIdentity/**`
- Regulatory display (fees, risk levels, legal notices): to be identified with product and compliance
- Pipeline and supply chain: `**/azure-pipelines*.yml`, `**/package.json`, lockfiles, `eas.json`, `app.config.*`

**Expected cost:** with first review at p50 = 30 min, the added wait should be small. The real constraint is reviewer capacity, given that 2 authors produce 60% of PRs. Measure it in the next 2 weeks instead of guessing.

### Step 2: AI review as an extra layer (4 weeks, after step 1)

- An AI reviewer runs on PRs to Linxea-React, Linxea-Mobile and tunnels (the customer-facing flows), after the existing quality bot.
- Each AI comment gets tagged by the PR author: `real-bug` / `useful-nit` / `false-positive`.
- Success criteria, fixed before starting:
  - ≥ 1 `real-bug` per 20 PRs.
  - ≤ 30% `false-positive`.
  - No increase in time-to-merge p50.
- Failure → turn it off. No sunk-cost extension.

### Step 3: decision (written now, applied later)

- If step 2 succeeds: let author self-approval plus AI review plus green CI suffice **only** on paths outside the mandatory list.
- Never on the mandatory list.

## 4. Metrics to track (fortnightly)

1. % merged PRs with no other-human approval, overall and on sensitive paths. Target: 0% on sensitive paths after step 1. Also track policy-bypass count and reasons.
2. Time to first human review and time to merge, p50 and p90. Guardrail against slowdown.
3. **Escaped defects** (to set up, missing today): Jira bugs linked to a PR merged in the previous 14 days, plus production incidents traced to a PR. This replaces revert rate.
4. AI reviewer precision during step 2 (tag counts).

## 5. Risks

- **Correlated misses:** code written with AI and reviewed by AI share blind spots. The human gate on sensitive paths and the deterministic quality bot are the independent layers; don't trade them away.
- **Reviewer capacity:** concentrated authorship means stricter policy could queue PRs behind 2–3 reviewers. Watch time-to-first-review p90.
- **Regulatory:** as a regulated intermediary, Linxea may need to evidence human control over changes to customer subscription and transaction flows. Check with compliance before step 3, not after.
- **Knowledge erosion:** 70% of merged PRs get no comment from another human. That already suggests most code is not read by a second person. AI review does not fix this; it may make it feel fixed.

## 6. Next actions

1. Share this baseline with the team and the repo owners. Decide on step 1 (bypass permission, `creatorVoteCounts`, path list).
2. Set up the escaped-defect metric: a Jira bug field or link to the originating PR.
3. Only then, choose and configure the AI reviewer for step 2.

Owner: _TBD_.
