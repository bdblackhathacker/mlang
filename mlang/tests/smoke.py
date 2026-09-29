#!/usr/bin/env python3
"""Smoke tests: compile+run bundled examples."""
import subprocess, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
CLI=os.path.join(HERE,"..","cli.py")
EX=os.path.join(HERE,"..","examples")
fails=0
for f in sorted(os.listdir(EX)):
    if not f.endswith(".ml2"): continue
    p=os.path.join(EX,f)
    print(f"[test] {f} ...",end=" ",flush=True)
    r=subprocess.run([sys.executable,CLI,"run",p],capture_output=True,text=True)
    if r.returncode!=0: print("FAIL"); print(r.stdout+r.stderr); fails+=1
    else: print("OK")
sys.exit(1 if fails else 0)
