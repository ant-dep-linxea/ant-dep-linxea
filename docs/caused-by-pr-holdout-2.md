# Holdout 2: tracer v2 (suspect list) passes the gate

Date: 2026-11-18.
- **Tracer:** `scripts/trace-regression/trace.py`, frozen before the run.
- **Changes from v1:**
  - Fix commits are located on the default branch whatever the PR target, with a ticket-key fallback for squashed feature branches.
  - Blame runs per fix commit, never over a range.
  - Per-file blame timeout, with `-C` dropped when too slow.
  - "Sonar" is now treated as mechanical.
  - The output is a top-3 suspect list with review mode, plus a suggestion only when one PR clearly owns the lines.
  - Dependency changes are listed only for packages the touched files import.
- **Selection:** the same rule as holdout 1, next bugs down the list, excluding all 29 earlier cases. 19 bugs, because Linxea-React had only 4 eligible within the PR window (since 2026-08-18).

## Result

| Gate | Target | Result |
|---|---|---|
| No crash or timeout | 0 | **0** (2–16 s per bug) |
| True culprit in the top 3, for real regressions | ≥80% | **12/14 (86%)** |

**Caveats:**
- n=14 is small. The 95% interval runs roughly from 60% to 97%.
- I judged ground truth myself, and I also built the tool, so a second pair of eyes should spot-check 5 cases.

## Case by case

| Bug | Kind | Top-3 suspects | Hit? |
|---|---|---|---|
| MS-734 Kameleoon mask too long | regression | #1 !24493 / #2 !24513 (MS-701 Kameleoon) | ✅ |
| MS-732 partners list publish doesn't rebuild pages | regression [Probable] | #1 !23724 / #2 !21865 (revalidation changes) | ✅ probable |
| MS-730 alt text not asked in new media library | regression from the Strapi upgrade | !19464 (the alt feature) etc. | ❌ in-run. The dependency list read only `front/package.json`; fixed after the run, it now lists the Strapi 5.56→5.60 bumps (in-sample fix) |
| MS-720 rebuild pages on reusable block change | **feature** | suggestion none | n/a |
| MS-717 comparator cells clipped on mobile | regression, latent | #1 !18405 comparator table style (`max-h-40`) | ✅ |
| EN-3839 no haptic on overshoot | regression | #1 !24372 haptics | ✅ |
| EN-3803 tab-bar padding outside tabs | regression [Probable] | #1 !25263 maintenance screen (1 day before) | ✅ probable |
| EN-3756 password field under keyboard | regression, latent | #2 !19737 account deletion; the suggestion picked #1, wrongly | ✅ in top 3 |
| EN-3754 blur under iOS status bar | **feature** | suggestion none | n/a |
| EN-3753 4px spacing on Contrats | unclear | no convincing suspect | ❌ (counted as a miss) |
| GROW-3182 alignment on small mobiles | regression, latent | #1 !9484 layout / #3 !22787 Rebranding | ✅ |
| GROW-3161 birth city not reset in parent | regression, latent 692 days | #1 !9443 CountryAndCity | ✅ |
| GROW-3147 email case not compared | regression, latent 475 days | #1 !12349 | ✅ |
| GROW-3047 free-typed provider code | regression, latent 212 days | #1 !17237 ProviderDetails | ✅ |
| GROW-3039 stale acceptance | regression, pre-2025 code | "predates our PR history" + !9984 | ✅ |
| EN-3318 reload button on error fallback | **improvement** | suggestion asserts !9524 | n/a, wrongly suggested |
| EN-3257 chart tooltip/legend (4 fixes) | regression [Probable] | #2 !16983 recharts migration | ✅ probable |
| EN-3255 IDRECTO sort order | **backend data change** | suggestion asserts !10393 | n/a, wrongly suggested |
| EN-3040 remove New Caledonia from DOM-TOM | **business rule change** | suggestion asserts !11288 | n/a, wrongly suggested |

## What the two holdouts teach

1. **The confirmation step is not optional.** 5/19 Bugs here, and 2/20 in holdout 1 (18% overall), are not regressions: features, rule changes, backend data. The tool suggested a culprit for 3 of them. The `suggestion` line is only a hint, and the top-1 suggestion was wrong on a real regression too (EN-3756).
2. **Most escaped bugs are old.** 10 of the 14 regressions were caused by PRs merged more than 180 days earlier. Only 4 (MS-734, MS-732, EN-3839, EN-3803) trace to PRs from the last 90 days. Consequences for the metric:
   - The "review mode of the culprit" signal (bypass vs reviewed) will take **months** to accumulate for current practices.
   - Report culprits by merge cohort (month merged), not by bug date.
   - Expect few data points per quarter: about 4 recent-culprit regressions in this sample of 39 bugs.
3. **Dependency bumps matter** (MS-730 Strapi, GROW-3358 react-hook-form, GROW-3299 vital-ui). They must stay in the output.

## Gate decision

**Passed** for the suspect-list design, with the confirmation step mandatory. The tool never writes a culprit on its own.

**Before PR 1:** someone other than me spot-checks 5 of the judgements above (suggested: MS-732, EN-3803, EN-3756, GROW-3182, EN-3257).
