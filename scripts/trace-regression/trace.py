#!/usr/bin/env python3
"""trace-regression v2: list the PRs most likely to have introduced the code a fix PR changed.

Usage: trace.py <clone_dir> <azdo_project> <repo> <fix_pr_id>
Output: a ranked suspect list for a person or agent to confirm. It never asserts a culprit.
Read-only: local git + Azure DevOps GET calls (AZDO_PAT, or a proxy that injects auth).
Needs a FULL clone: on a blobless clone, blame fetches blobs one by one and times out.
"""
import collections, json, os, re, subprocess, sys, time, urllib.parse
T0 = time.time()
def dbg(m):
    if os.environ.get("TRACE_DEBUG"): print(f"[{time.time()-T0:6.1f}s] {m}", file=sys.stderr)
from datetime import datetime, timedelta, timezone

clone, project, repo, fix_id = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
API = f"https://dev.azure.com/linxea/{project}/_apis/git/repositories/{repo}"
SKIP_FILES = re.compile(r"(lock\.ya?ml|lock\.json|bun\.lock|\.snap$|/kubb/|CHANGELOG|\.md$)")
MECHANICAL = re.compile(r"(named exports|default exports|prettier|\bformat(ting)?\b|sort-keys|autofix|"
                        r"\brename\b|style\(|lint|sonar)", re.I)
IMPORT_LINE = re.compile(r"^(import\b|export \{|\} from |from ['\"])")
BLAME_TIMEOUT = 20  # seconds per file


def az(path, **q):
    q.setdefault("api-version", "7.1")
    url = f"{API}{path}?{urllib.parse.urlencode(q)}"
    auth = ":" + os.environ.get("AZDO_PAT", "dummy")
    out = subprocess.run(["curl", "-sS", "-u", auth, url], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def git(*a, timeout=None):
    return subprocess.run(["git", "-C", clone, *a], capture_output=True, text=True,
                          check=True, timeout=timeout).stdout


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def az_date(s):  # Azure DevOps dates carry 7 fractional digits
    return datetime.fromisoformat(re.sub(r"\.\d+", "", s).replace("Z", "+00:00"))


def default_branch():
    try:
        return git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip().split("/", 1)[1]
    except subprocess.CalledProcessError:
        return next(b for b in ("main", "master") if git("branch", "-r", "--list", f"origin/{b}").strip())


def commit_key(email, date):
    return (email.lower(), utc(date).strftime("%Y-%m-%dT%H:%M:%S"))


# 1. Fix commits on the DEFAULT branch, whatever branch the fix PR targeted.
fix = az(f"/pullRequests/{fix_id}")
branch = default_branch()
ref = f"origin/{branch}"
fix_commits = az(f"/pullRequests/{fix_id}/commits", **{"$top": 500})["value"]
ids = {c["commitId"] for c in fix_commits}
keys = {commit_key(c["author"]["email"], c["author"]["date"]) for c in fix_commits}
created = az_date(fix["creationDate"])
log = git("log", ref, "--since", (created - timedelta(days=30)).isoformat(),
          "--format=%H%x09%aI%x09%ae").splitlines()
on_branch = [l.split("\t")[0] for l in log
             if l.split("\t")[0] in ids or commit_key(l.split("\t")[2], l.split("\t")[1]) in keys]
located = "by commit identity"
if not on_branch:  # squashed when a feature branch merged: fall back to the ticket key in subjects
    tickets = [t for t in re.findall(r"\b([A-Z]+-[1-9]\d*)\b", fix["title"])]
    if tickets:
        pat = "^(" + "|".join(tickets) + ")\\b"
        on_branch = git("log", ref, "--since", created.isoformat(), "--until",
                        (created + timedelta(days=90)).isoformat(), "-E", "--grep", pat,
                        "--format=%H").split()
        located = f"by ticket key {', '.join(tickets)} (fix PR targeted another branch)"
if not on_branch:
    print(f"fix !{fix_id}: its commits are not on {ref} (not shipped yet?) -> no suspects")
    sys.exit(0)
base = f"{on_branch[-1]}^"  # for dependency lookups

# 2. Old-side lines each fix commit touched (its own diff, never a range: unrelated commits
#    can sit between fix commits). Pure additions blame their neighbours.
ranges = collections.defaultdict(list)  # (blame_rev, path) -> line ranges
for c in on_branch:
    cur = None
    for l in git("diff", "-U0", "--no-color", f"{c}^", c).splitlines():
        if l.startswith("--- "):
            cur = None if l == "--- /dev/null" else l[6:]
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+", l)
        if m and cur and not SKIP_FILES.search(cur):
            start, n = int(m.group(1)), int(m.group(2) or 1)
            ranges[(f"{c}^", cur)].append((start, start + n - 1) if n else (max(1, start - 1), start + 2))

dbg(f"{len(ranges)} files, {sum(len(v) for v in ranges.values())} hunks")
blamed, slow = collections.Counter(), []
for (rev, path), rs in ranges.items():
    span = [x for a, b in rs for x in ("-L", f"{a},{b}")]
    out = None
    for extra in (["-C"], []):  # -C follows moved code; drop it if too slow
        try:
            out = git("blame", "-w", *extra, "--line-porcelain", *span, rev, "--", path, timeout=BLAME_TIMEOUT)
            break
        except subprocess.TimeoutExpired:
            slow.append(path)
        except subprocess.CalledProcessError:
            break
    sha = None
    for l in (out or "").splitlines():
        m = re.match(r"^([0-9a-f]{40}) \d+ \d+", l)
        if m:
            sha = m.group(1)
        elif l.startswith("\t") and l[1:].strip() and not IMPORT_LINE.match(l[1:].strip()):
            blamed[sha] += 1

dbg(f"blame done, {len(blamed)} commits")
# 3. Blamed commit -> PR that landed it on the default branch.
completed, skip = [], 0
while True:
    page = az("/pullrequests", **{"searchCriteria.status": "completed",
                                  "searchCriteria.targetRefName": f"refs/heads/{branch}",
                                  "$top": 500, "$skip": skip})["value"]
    completed += page
    if len(page) < 500 or min(p["closedDate"] for p in page) < "2025-01":
        break
    skip += 500
completed.sort(key=lambda p: p["closedDate"])
pr_commits = {}


def pr_for(sha):
    ad, cd, em = git("show", "-s", "--format=%aI%x09%cI%x09%ae", sha).strip().split("\t")
    k, landed = commit_key(em, ad), utc(cd)
    for p in completed:
        closed = az_date(p["closedDate"])
        if closed < landed - timedelta(minutes=5):
            continue
        if closed > landed + timedelta(days=2):
            break
        pid = p["pullRequestId"]
        if pid not in pr_commits:
            cs = az(f"/pullRequests/{pid}/commits", **{"$top": 500})["value"]
            pr_commits[pid] = {c["commitId"] for c in cs} | {commit_key(c["author"]["email"], c["author"]["date"]) for c in cs}
        if sha in pr_commits[pid] or k in pr_commits[pid]:
            return p
    return None


groups, meta = collections.Counter(), {}
for sha, n in blamed.items():
    if sha in ids or sha in on_branch:
        continue
    p = pr_for(sha)
    if p and MECHANICAL.search(p["title"]):
        continue
    if p:
        key = f"!{p['pullRequestId']}"
        when = az_date(p["closedDate"])
        others = [r for r in p.get("reviewers", []) if r.get("vote", 0) > 0 and not r.get("isContainer")
                  and r["id"] != p["createdBy"]["id"]]
        bypass = (p.get("completionOptions") or {}).get("bypassPolicy", False)
        mode = "bypassed" if bypass else ("approved by another person" if others else "self-approved")
        meta[key] = (when, p["title"], mode)
    else:  # direct push, or older than the PRs we list: group by year
        when = utc(git("show", "-s", "--format=%cI", sha).strip())
        key = f"commits from {when.year} (no PR found)"
        meta.setdefault(key, (when, "direct push or pre-PR history", "-"))
        meta[key] = (min(meta[key][0], when), *meta[key][1:])
    groups[key] += n

dbg("pr mapping done")
# 4. Report: ranked suspects, a suggestion only when one is clear, dependency changes.
total = sum(groups.values())
print(f"fix !{fix_id}: {fix['title'][:90]}")
print(f"  {len(on_branch)} commit(s) on {ref} located {located}, {total} blamed lines" + (f", slow blame skipped -C: {slow}" if slow else ""))
if not total:
    print("  no blamable lines (pure config/deps or new files): suggestion none")
ranked = groups.most_common(3)
for i, (k, n) in enumerate(ranked, 1):
    when, title, mode = meta[k]
    age = (created - when).days
    print(f"  #{i} {repo}{k if k.startswith('!') else ' ' + k}  {100*n/total:.0f}% of lines, merged {when.date()} "
          f"({age} days before the fix), {mode}: {title[:70]}")
if ranked:
    k, n = ranked[0]
    share, age = n / total, (created - meta[k][0]).days
    second = ranked[1][1] / total if len(ranked) > 1 else 0
    if not k.startswith("!"):
        verdict = "none: the code predates our PR history (latent or pre-existing)"
    elif share >= 0.6 or (share >= 0.3 and share >= 2 * second):
        verdict = f"{repo}{k} ({'latent ' + str(age) + ' days' if age > 180 else 'recent'})"
    else:
        verdict = "none: no single PR owns the changed lines"
    print(f"  suggestion: {verdict}")
print("  to confirm: is this a regression at all (vs. a feature request, new data or content)? "
      "If yes, which suspect introduced the faulty behaviour?")

# Dependency changes on packages the touched files import (blame cannot see these).
pkgs = set()
for rev, path in ranges:
    try:
        src = git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        continue
    for spec in re.findall(r"""from ['"]([^'".][^'"]*)['"]""", src):
        pkgs.add("/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0])
pkgs.discard("react")
if pkgs:
    since = (created - timedelta(days=60)).isoformat()
    hits = []
    for l in git("log", base, "--since", since, "--format=@@%h %ad %s", "--date=short", "-p", "-U0",
                 "--", ":(glob)**/package.json").splitlines():
        if l.startswith("@@") and not l.startswith("@@ "):
            commit = l[2:]
        elif l.startswith("+") and not l.startswith("+++"):
            m = re.match(r'\+\s*"([^"]+)":\s*"([^"]+)"', l)
            if m and m.group(1) in pkgs and "chore(release)" not in commit:
                hits.append(f"{commit[:80]}  ({m.group(1)} -> {m.group(2)})")
    if hits:
        print("  dependency changes on imported packages, last 60 days:")
        for h in list(dict.fromkeys(hits))[:5]:
            print("    " + h)
