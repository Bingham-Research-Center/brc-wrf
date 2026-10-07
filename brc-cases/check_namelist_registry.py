#!/usr/bin/env python3
"""Check rendered namelist key placement against the released build declarations.

This checks groups and duplicate/unknown keys, not Fortran value syntax or
scientific settings. The controlled render uses one assignment per line.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def declarations(*texts):
    expected={}
    for text in texts:
        for group,raw in re.findall(r'^\s*NAMELIST\s*/(\w+)/([^\n]+)',text,re.I|re.M):
            for key in raw.split('!',1)[0].split(','):
                key=key.strip().lower()
                assert re.fullmatch(r'\w+',key),('unsupported declaration',group,key)
                assert key not in expected or expected[key]==group.lower()
                expected[key]=group.lower()
    return expected


def check(text,expected):
    group=None;seen=set();errors=[]
    for number,line in enumerate(text.splitlines(),1):
        line=line.split('!',1)[0].strip()
        if line.startswith('&'):group=line[1:].lower();continue
        if line=='/':group=None;continue
        m=re.match(r'(\w+)\s*=',line)
        if not m:continue
        key=m[1].lower()
        if key in seen:errors.append({'line':number,'key':key,'error':'duplicate key'})
        seen.add(key)
        if expected.get(key)!=group or key not in expected:
            errors.append({'line':number,'key':key,'group':group,'compiled_group':expected.get(key)})
    return {'keys_checked':len(seen),'errors':errors,'accepted_groups':bool(seen) and not errors}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--namelist',type=Path,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    sources=[a.build/'inc/namelist_statements.inc',a.build/'frame/module_io_quilt_old.F']
    report=check(a.namelist.read_text(),declarations(*(p.read_text() for p in sources)))
    report['input_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources,a.namelist]}
    if a.output:a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['accepted_groups']:raise SystemExit('namelist group validation failed')

if __name__=='__main__':main()
