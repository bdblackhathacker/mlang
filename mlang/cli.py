#!/usr/bin/env python3
"""MLang unified CLI - all frontends.
Usage:
  python3 cli.py build <file> [-o out] [--keep-c] [-v]   # .ml2/.ml auto-routed
  python3 cli.py run <file> [--keep-c]
  python3 cli.py check <file>        # syntax only (.ml2/.ml)
  python3 cli.py vm <key> <file.masm2|mcode2>  # secret-VM path (mcode_v2)
  python3 cli.py examples
  python3 cli.py version
Frontends:
  .ml2 -> mlang2 (Python/C/JS aliases: let|var, def|function, print|log)
  .ml  -> mlangc  (C-like ints, recursion)
  .masm2/.mcode2 -> mcode_v2 secret VM (needs key)
"""
import argparse, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
SRC=os.path.join(HERE,"src")
sys.path.insert(0,SRC)
import mlang2

VERSION="mlang 2.3.0 (all frontends) — Designed & Developed by Shiboshree Roy"

def backend(path):
    if path.endswith(".ml2"): return "ml2"
    if path.endswith(".ml"): return "ml"
    if path.endswith(".masm2") or path.endswith(".mcode2"): return "vm"
    raise mlang2.Err(f"unknown extension for {path} (use .ml2/.ml/.masm2/.mcode2)")

def cmd_build(a):
    b=backend(a.file)
    if b=="ml2":
        out=mlang2.compile_file(a.file,a.out,a.keep_c)
    elif b=="ml":
        import mlangc
        out=mlangc.compile_file(a.file,a.out,a.keep_c)
    else: raise mlang2.Err("vm path needs a key: use `cli.py vm <key> <file>`")
    if a.v: print(f"[cli] built {out} via {b}")
    return out

def cmd_run(a):
    import subprocess
    b=backend(a.file)
    if b=="ml2": out=mlang2.compile_file(a.file,None,a.keep_c)
    elif b=="ml": import mlangc; out=mlangc.compile_file(a.file,None,a.keep_c)
    else: raise mlang2.Err("vm path needs a key: use `cli.py vm <key> <file>`")
    print("[cli] run:")
    subprocess.run([os.path.abspath(out)])

def cmd_check(a):
    if backend(a.file)=="ml":
        import mlangc
        src=open(a.file).read(); mlangc.P(mlangc.lex(src,a.file),a.file).parse()
    else:
        src=open(a.file).read(); mlang2.P(mlang2.lex(src,a.file),a.file).parse()
    print(f"[cli] {a.file}: syntax OK")

def cmd_vm(a):
    import mcode_v2
    key=a.key.encode(); data=open(a.file,"rb").read()
    if a.file.endswith(".masm2"):
        blob=mcode_v2.assemble_text(data.decode(),key)
        out=a.file.replace(".masm2",".mcode2")
        open(out,"wb").write(blob)
        print(f"[cli] assembled -> {out}"); mcode_v2.run(mcode_v2.decode(blob,key))
    else: mcode_v2.run(mcode_v2.decode(data,key))

def cmd_examples(_):
    d=os.path.join(HERE,"examples")
    for f in sorted(os.listdir(d)): print(f"  {f}")

def main():
    p=argparse.ArgumentParser(prog="mlang",description="MLang all-frontends compiler")
    sub=p.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build",help="compile (.ml2/.ml)"); b.add_argument("file"); b.add_argument("-o",dest="out",default=None); b.add_argument("--keep-c",action="store_true"); b.add_argument("-v",action="store_true")
    r=sub.add_parser("run",help="compile + run"); r.add_argument("file"); r.add_argument("--keep-c",action="store_true")
    c=sub.add_parser("check",help="syntax check"); c.add_argument("file")
    v=sub.add_parser("vm",help="secret-VM assemble/run"); v.add_argument("key"); v.add_argument("file")
    sub.add_parser("examples",help="list examples"); sub.add_parser("version",help="show version")
    a=p.parse_args()
    try:
        if a.cmd=="build": cmd_build(a)
        elif a.cmd=="run": cmd_run(a)
        elif a.cmd=="check": cmd_check(a)
        elif a.cmd=="vm": cmd_vm(a)
        elif a.cmd=="examples": cmd_examples(a)
        elif a.cmd=="version": print(VERSION)
    except (mlang2.Err,Exception) as e:
        print(f"error: {e}"); sys.exit(1)

if __name__=="__main__": main()
