#!/usr/bin/env bash
# Usage: pull.sh <out_dir> <since ISO date, e.g. 2026-08-18T00:00:00Z>
# Read-only Azure DevOps REST calls. Auth: PAT in AZDO_PAT (or a proxy that injects it).
set -euo pipefail
S=$1; SINCE=$2; AUTH=":${AZDO_PAT:-dummy}"
mkdir -p "$S/prs" "$S/threads" "$S/changes"
for p in Linxea-React Linxea-Mobile; do
  for st in completed abandoned active; do
    skip=0
    while :; do
      out=$S/prs/$p-$st-$skip.json
      curl -sS -u "$AUTH" "https://dev.azure.com/linxea/$p/_apis/git/pullrequests?searchCriteria.status=$st&searchCriteria.minTime=$SINCE&searchCriteria.queryTimeRangeType=created&\$top=500&\$skip=$skip&api-version=7.1" -o "$out"
      n=$(python3 -c "import json;print(json.load(open('$out'))['count'])")
      [ "$n" -lt 500 ] && break; skip=$((skip+500))
    done
  done
done
python3 - "$S" <<'PY'
import json,glob,sys
S=sys.argv[1]; prs=[p for f in glob.glob(S+'/prs/*.json') for p in json.load(open(f))['value']]
json.dump(prs,open(S+'/all.json','w'))
with open(S+'/ids.txt','w') as a, open(S+'/cids.txt','w') as b:
  for p in prs:
    r=p['repository']; a.write(f"{r['project']['name']} {r['id']} {p['pullRequestId']}\n")
    if p['status']=='completed' and r['name'] in('Linxea-React','Linxea-Mobile','website','tunnels') and p.get('lastMergeCommit'):
      b.write(f"{r['project']['name']} {r['id']} {p['pullRequestId']} {p['lastMergeCommit']['commitId']}\n")
PY
xargs -P 12 -n 3 sh -c 'f='"$S"'/threads/$2-$3.json; [ -s $f ] || curl -sS -u "'"$AUTH"'" "https://dev.azure.com/linxea/$1/_apis/git/repositories/$2/pullRequests/$3/threads?api-version=7.1" -o $f' _ < "$S/ids.txt"
xargs -P 12 -n 4 sh -c 'f='"$S"'/changes/$2-$3.json; [ -s $f ] || curl -sS -u "'"$AUTH"'" "https://dev.azure.com/linxea/$1/_apis/git/repositories/$2/commits/$4/changes?top=2000&api-version=7.1" -o $f' _ < "$S/cids.txt"
# then: python3 metrics.py "$S" && python3 sensitive.py "$S"
