import json,sys,collections,re
S=sys.argv[1]
prs=json.load(open(S+'/all.json')); rows=json.load(open(S+'/rows.json'))
CATS={
 'auth':r'(auth|authentification|account-recovery|oauth|login|password|session|token)',
 'money/signature':r'(signature|verificationcode|transaction|payment|sourceoffunds|withdraw|arbitrage|iban|\brib\b|subscription|versement|rachat)',
 'identity/personal-data':r'(identity|kyc|personalinformation|customerprofile|dcr)',
 'pipeline/deps':r'(azure-pipelines|\.ya?ml$|dockerfile|package\.json$|lock\.yaml$|lock\.json$|bun\.lock$|\.npmrc|eas\.json|app\.config)',
}
agg=collections.defaultdict(lambda:[0,0]); per=collections.defaultdict(lambda:[0,0]); any_=[0,0]; examples=collections.defaultdict(list)
for p,r in zip(prs,rows):
    f=f"{S}/changes/{p['repository']['id']}-{p['pullRequestId']}.json"
    if r['isbot']: continue
    try: ch=json.load(open(f)).get('changes',[])
    except: continue
    paths=[c['item'].get('path','').lower() for c in ch if not c['item'].get('isFolder')]
    noappr = r['approvers']==0
    hit=False
    for cat,rx in CATS.items():
        if any(re.search(rx,x) for x in paths):
            hit=True; agg[cat][0]+=1; agg[cat][1]+=noappr
            per[(p['repository']['name'],cat)][0]+=1; per[(p['repository']['name'],cat)][1]+=noappr
            if noappr and cat!='pipeline/deps' and len(examples[cat])<4: examples[cat].append(f"{p['repository']['name']}!{p['pullRequestId']} {p['title'][:70]}")
    if hit: any_[0]+=1; any_[1]+=noappr
print('ANY sensitive: %d PRs, %d (%.0f%%) merged without another human approval'%(any_[0],any_[1],100*any_[1]/any_[0]))
for c,(n,u) in agg.items(): print(f"{c}: {n} PRs, {u} ({100*u/n:.0f}%) no other-human approval")
print()
for (repo,c),(n,u) in sorted(per.items()): print(f"  {repo:14} {c:24} {n:4} PRs  {u:4} ({100*u/n:.0f}%) unapproved")
print()
for c,e in examples.items(): print(c, e)
