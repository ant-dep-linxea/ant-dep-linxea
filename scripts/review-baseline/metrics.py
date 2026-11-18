import json,sys,collections,re,statistics as st
from datetime import datetime
S=sys.argv[1]
prs=json.load(open(S+'/all.json'))
def dt(s): return datetime.fromisoformat(s.replace('Z','')[:26])
def bot(n): return 'Build Service' in n or n.startswith('Microsoft.') or n.startswith('[')
def q(xs,p):
    xs=sorted(xs); 
    return xs[min(len(xs)-1,int(p*len(xs)))] if xs else None
rows=[]
for p in prs:
    th=json.load(open(f"{S}/threads/{p['repository']['id']}-{p['pullRequestId']}.json")).get('value',[])
    au=p['createdBy']['displayName']; c0=dt(p['creationDate'])
    firstsig=None; approvers=set(); hcom=0; botcom=0; selfvote=False
    for t in th:
        ty=(t.get('properties') or {}).get('CodeReviewThreadType',{}).get('$value')
        for c in t.get('comments',[]):
            a=c['author']['displayName']; d=dt(c['publishedDate'])
            if ty=='VoteUpdate':
                v=int(t['properties']['CodeReviewVoteResult']['$value'])
                if a==au and v>0: selfvote=True
                if a!=au and not bot(a):
                    if v>0: approvers.add(a)
                    firstsig=min(firstsig or d,d)
            elif ty is None and c.get('commentType')=='text':
                if bot(a): botcom+=1
                elif a!=au: hcom+=1; firstsig=min(firstsig or d,d)
    title=p['title']; tl=title.lower()
    typ=re.search(r'\b(feat|fix|hotfix|chore|refactor|test|docs|ci|build|perf|style|revert)\b',tl)
    rows.append(dict(repo=p['repository']['name'],status=p['status'],author=au,isbot=bot(au),
        created=c0,closed=dt(p['closedDate']) if p.get('closedDate') else None,
        firstsig=firstsig,approvers=len(approvers),hcom=hcom,botcom=botcom,selfvote=selfvote,
        revert=tl.startswith('revert'),typ=typ.group(1) if typ else 'other',draft=p.get('isDraft',False),
        target=p['targetRefName']))
json.dump([{k:(str(v) if isinstance(v,datetime) else v) for k,v in r.items()} for r in rows],open(S+'/rows.json','w'))
def report(name,R):
    M=[r for r in R if r['status']=='completed' and not r['isbot']]
    if not M: return
    ab=sum(r['status']=='abandoned' and not r['isbot'] for r in R)
    ttm=[(r['closed']-r['created']).total_seconds()/3600 for r in M]
    tfs=[(r['firstsig']-r['created']).total_seconds()/3600 for r in M if r['firstsig']]
    n=len(M)
    pct=lambda k:f"{100*k/n:.0f}%"
    print(f"\n## {name}: merged={n} (~{n/13:.0f}/wk), abandoned={ab} ({100*ab/(n+ab):.0f}%)")
    print(f"  time-to-merge h: p50={q(ttm,.5):.1f} p75={q(ttm,.75):.1f} p90={q(ttm,.9):.1f}")
    if tfs: print(f"  time-to-first-human-review h: p50={q(tfs,.5):.1f} p90={q(tfs,.9):.1f}  (n={len(tfs)})")
    print(f"  merged with 0 other-human approval: {pct(sum(r['approvers']==0 for r in M))} | with 0 other-human comment: {pct(sum(r['hcom']==0 for r in M))} | approval but no comment (rubber-stamp proxy): {pct(sum(r['approvers']>0 and r['hcom']==0 for r in M))}")
    print(f"  self-vote present: {pct(sum(r['selfvote'] for r in M))} | reverts: {sum(r['revert'] for r in M)} ({100*sum(r['revert'] for r in M)/n:.1f}%) | fix/hotfix PRs: {pct(sum(r['typ'] in('fix','hotfix') for r in M))}")
    print(f"  avg other-human comments/PR: {sum(r['hcom'] for r in M)/n:.2f} | quality-bot comments/PR: {sum(r['botcom'] for r in M)/n:.2f}")
report('ALL',rows)
for repo in ['Linxea-React','Linxea-Mobile','website','frontend-instructions','tunnels','design-system']:
    report(repo,[r for r in rows if r['repo']==repo])
# monthly trend
m=collections.Counter(r['closed'].strftime('%Y-%m') for r in rows if r['status']=='completed' and not r['isbot'])
print('\nmerged by month:',sorted(m.items()))
a=collections.Counter(r['author'] for r in rows if r['status']=='completed' and not r['isbot'])
tot=sum(a.values()); print('top-5 author share (%):',[round(100*v/tot) for k,v in a.most_common(5)])
