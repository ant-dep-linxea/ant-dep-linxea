#!/usr/bin/env python3
"""Prototype: find the PR(s) that introduced the lines a fix PR changed.

Usage: trace_proto.py <clone_dir> <project> <repo> <fix_pr_id> [target_branch]
Read-only: git blame/log locally + Azure DevOps GET calls (AZDO_PAT, or a proxy that injects auth).
Needs a FULL clone: on a blobless clone, blame fetches blobs one by one and times out.
"""
import json, os, re, subprocess, sys, collections, urllib.parse
from datetime import datetime, timedelta, timezone

clone, project, repo, fix_id = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
target = sys.argv[5] if len(sys.argv) > 5 else None
API = f"https://dev.azure.com/linxea/{project}/_apis/git/repositories/{repo}"
MECHANICAL = re.compile(r"(named exports|default exports|prettier|\bformat(ting)?\b|sort-keys|autofix|\brename\b|style\(|lint)", re.I)
IGNORE_FILES = re.compile(r"(pnpm-lock\.yaml|package-lock\.json|bun\.lock|yarn\.lock|\.snap$|/kubb/|CHANGELOG)")

def az(path, **q):
    q.setdefault("api-version", "7.1")
    url = f"{API}{path}?{urllib.parse.urlencode(q)}"
    out = subprocess.run(["curl", "-sS", "-u", ":" + os.environ.get("AZDO_PAT", "dummy"), url], capture_output=True, text=True, check=True).stdout
    return json.loads(out)

def git(*a):
    return subprocess.run(["git", "-C", clone, *a], capture_output=True, text=True, check=True).stdout

def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")[:25] if "." not in s else s.split(".")[0] + "+00:00")

# 1. Fix PR and its commits, located on the target branch by (subject, author date).
fix = az(f"/pullRequests/{fix_id}")
target = target or fix["targetRefName"].split("/")[-1]
ref = f"origin/{target}"
fix_commits = az(f"/pullRequests/{fix_id}/commits", **{"$top": 200})["value"]
keys = {(c["author"]["email"].lower(), c["author"]["date"][:19]) for c in fix_commits}
fix_ids = {c["commitId"] for c in fix_commits}
log = git("log", ref, "--since", (dt(fix["creationDate"]) - timedelta(days=30)).isoformat(),
          "--format=%H%x09%aI%x09%ae").splitlines()
on_master = []
for line in log:
    sha, ad, em = line.split("\t", 2)
    adu = datetime.fromisoformat(ad).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if sha in fix_ids or (em.lower(), adu) in keys:
        on_master.append(sha)
if not on_master:
    sys.exit(f"fix PR !{fix_id}: commits not found on {ref}")
newest, oldest = on_master[0], on_master[-1]
base = f"{oldest}^"
fix_shas = set(on_master)

# 2. Old-side line ranges touched by the fix (removed or modified lines).
diff = git("diff", "-U0", "--no-color", base, newest)
ranges = collections.defaultdict(list)
cur = None
for l in diff.splitlines():
    if l.startswith("--- "):
        cur = None if l == "--- /dev/null" else l[6:]
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+", l)
    if m and cur and not IGNORE_FILES.search(cur):
        start, n = int(m.group(1)), int(m.group(2) or 1)
        if n > 0:
            ranges[cur].append((start, start + n - 1))
        else:  # pure addition after old line `start`: blame its neighbours
            ranges[cur].append((max(1, start - 1), start + 2))

# 3. Blame those lines at the fix's base.
blamed = collections.Counter()
info = {}
for path, rs in ranges.items():
    args = ["blame", "-w", "-C", "--line-porcelain"]
    for a, b in rs:
        args += ["-L", f"{a},{b}"]
    try:
        out = git(*args, base, "--", path)
    except subprocess.CalledProcessError:
        continue
    for l in out.splitlines():
        m = re.match(r"^([0-9a-f]{40}) \d+ \d+", l)
        if m:
            sha = m.group(1)
        elif l.startswith("summary "):
            info.setdefault(sha, l[8:])
        elif l.startswith("\t"):
            txt = l[1:].strip()
            if txt and not re.match(r"^(import\b|export \{|\} from |from ['\"])", txt):
                blamed[sha] += 1

# 4. Map each blamed commit to the PR that landed it.
completed = []
skip = 0
while True:
    page = az("/pullrequests", **{"searchCriteria.status": "completed",
                                  "searchCriteria.targetRefName": f"refs/heads/{target}",
                                  "$top": 500, "$skip": skip})["value"]
    completed += page
    oldest_closed = min((p["closedDate"] for p in page), default="9")
    if len(page) < 500 or oldest_closed < "2025-01":
        break
    skip += 500
completed.sort(key=lambda p: p["closedDate"])
pr_commits_cache = {}

def pr_for(sha):
    ad, cd, em, subj = git("show", "-s", "--format=%aI%x09%cI%x09%ae%x09%s", sha).strip().split("\t", 3)
    adu = datetime.fromisoformat(ad).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cdt = datetime.fromisoformat(cd).astimezone(timezone.utc)
    for p in completed:
        closed = dt(p["closedDate"])
        if closed < cdt - timedelta(minutes=5):
            continue
        if closed > cdt + timedelta(days=2):
            break
        pid = p["pullRequestId"]
        if pid not in pr_commits_cache:
            cs = az(f"/pullRequests/{pid}/commits", **{"$top": 500})["value"]
            pr_commits_cache[pid] = {c["commitId"] for c in cs} | {(c["author"]["email"].lower(), c["author"]["date"][:19]) for c in cs}
        if sha in pr_commits_cache[pid] or (em.lower(), adu) in pr_commits_cache[pid]:
            return pid, p["title"], closed.date().isoformat()
    return None, f"direct push or older than PR window: {subj[:60]}", cdt.date().isoformat()

total = sum(blamed.values())
by_pr = collections.Counter()
labels = {}
for sha, n in blamed.most_common():
    if sha in fix_shas:
        continue
    pid, title, when = pr_for(sha)
    if pid and MECHANICAL.search(title):
        continue
    key = pid or f"commit {sha[:9]}"
    by_pr[key] += n
    labels[key] = (title, when)

print(f"fix !{fix_id}: {fix['title'][:90]}")
print(f"  {len(on_master)} commit(s) on {ref}, {sum(len(v) for v in ranges.values())} hunks, {total} blamed lines")
for key, n in by_pr.most_common(5):
    t, w = labels[key]
    print(f"  {100*n/total:5.1f}%  {('!'+str(key)) if isinstance(key,int) else key}  merged {w}  {t[:80]}")
fix_created = dt(fix["creationDate"])
total = sum(by_pr.values()) or 1
def age(k): return (fix_created - datetime.fromisoformat(labels[k][1]).replace(tzinfo=timezone.utc)).days
dom = [(k, n) for k, n in by_pr.items() if isinstance(k, int) and n / total >= 0.6]
recent = {k: n for k, n in by_pr.items() if isinstance(k, int) and age(k) <= 180}
rtot = sum(recent.values())
if dom:
    k, n = dom[0]
    conf = "certain" if n / total >= 0.8 else "probable"
    latent = f" | latent {age(k)} days" if age(k) > 180 else ""
    print(f"  => Caused-by: {repo}!{k} | owns {100*n/total:.0f}% of blamed lines | confidence {conf}{latent}")
elif rtot:
    k, n = max(recent.items(), key=lambda kv: kv[1])
    share = n / rtot
    conf = "certain" if share >= 0.8 else "probable" if share >= 0.5 else "none"
    print(f"  => Caused-by: {repo}!{k} | {100*share:.0f}% of recent-PR lines | confidence {conf}")
else:
    print("  => no PR owns these lines: confidence none")
# dependency bumps in the 30 days before the fix: blame cannot see them
since = (fix_created - timedelta(days=30)).isoformat()
bumps = git("log", f"{base}", "--since", since, "--format=%h %ad %s", "--date=short",
            "-G", r'"[@a-z0-9/.-]+": "[\^~]?[0-9]', "--", "package.json", "front/package.json").splitlines()
bumps = [b for b in bumps if not re.search(r"chore\(release\)|\[skip release\]", b)]
if bumps:
    print("  dependency changes in the 30 days before the fix (blame cannot see these):")
    for b in bumps[:6]:
        print("    " + b[:100])
