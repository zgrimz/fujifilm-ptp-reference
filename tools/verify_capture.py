#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check supplied public captures against pinned scalar expectations. Never downloads inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import ptpcap


def check(path):
    expected=json.loads((Path(__file__).resolve().parents[1]/'fixtures/captures/expected.json').read_text())['captures']
    with open(path,'rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    match=next((x for x in expected if x['sha256']==digest),None)
    if match is None: raise ValueError('capture hash is not one of the documented inputs')
    issues=[];tx=ptpcap.transactions(path,True,issues)
    profiles=ptpcap.profile_rows(tx);writes={str(r['tid']):r for r in profiles if r['direction']=='write'}
    errors=[]
    if len(writes)!=match['write_count']: errors.append('profile write count differs')
    if 'transaction_count' in match and len(tx)!=match['transaction_count']: errors.append('transaction count differs')
    for tid,changes in match.get('changes',{}).items():
        actual=[[c['cell'],c['before'],c['after']] for c in writes.get(tid,{}).get('changes',[])]
        if actual!=changes: errors.append(f'tid {tid}: profile cell diff differs')
    by_tid={str(r['tid']):r for r in profiles}
    for tid,fields in match.get('profiles',{}).items():
        r=by_tid.get(tid,{})
        for key,value in fields.items():
            actual=r.get('cells',[])[24:] if key=='tail' else r.get(key)
            if actual!=value: errors.append(f'tid {tid}: {key} differs')
    for tid,prop in match.get('bank_tail',{}).items():
        t=tx.get(int(tid),{})
        if t.get('op')!=0x1016 or t.get('params')!=[prop] or t.get('resp')!=0x2001:
            errors.append(f'tid {tid}: bank/live tail differs')
    if match.get('metadata'):
        metadata={str(r['tid']):r for r in ptpcap.metadata_rows(tx)}
        for tid,fields in match['metadata'].items():
            obs=metadata.get(tid,{}).get('metadata',{}).get('observations',{})
            for field,value in fields.items():
                if obs.get(field,{}).get('value')!=value: errors.append(f'tid {tid}: {field} differs')
    return {'capture':match['filename'],'sha256':digest,'passed':not errors,'errors':errors,
            'profile_writes':len(writes),'recovery_events':sum(i['reason']=='packet_boundary_resync' for i in issues),
            'pixels_validated':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('captures',nargs='+');args=p.parse_args(argv)
    results=[]
    try:
        for path in args.captures: results.append(check(path))
    except (OSError,ValueError) as exc:
        print(f'verify_capture: {exc}',file=sys.stderr);return 2
    print(json.dumps(results,indent=2));return 0 if all(r['passed'] for r in results) else 1


if __name__=='__main__': sys.exit(main())
