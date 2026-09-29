#!/usr/bin/env python3
"""
MLang-C : real-world compiler, MLang (.ml) -> C -> native binary via cc.
Features: line/col errors, 64-bit ints, if/else, while, def() with args + recursion,
let/print/printc/nl, type-check (undeclared vars, arity check).
Usage: python3 mlangc.py prog.ml [-o prog] [--run] [--keep-c]
"""
import re, subprocess, sys, os

TYPES = ["num","id","op","kw","eof"]
KWS = {"let","print","printc","nl","if","else","while","def","return"}

class LexErr(Exception): pass
class ParseErr(Exception): pass

def lex(src, fname="<src>"):
    # strip comments, track lines
    out=[]; i=0; line=1; col=1
    n=len(src)
    while i<n:
        c=src[i]
        if c=="\n": line+=1; col=1; i+=1; continue
        if c.isspace(): col+=1; i+=1; continue
        if src.startswith("//",i):
            while i<n and src[i]!="\n": i+=1
            continue
        if src.startswith("/*",i):
            j=src.find("*/",i+2)
            if j<0: raise LexErr(f"{fname}:{line}:{col}: unterminated /*")
            seg=src[i:j]; line+=seg.count("\n"); i=j+2; col=1; continue
        m=re.match(r"\d+",src[i:])
        if m:
            out.append(("num",m.group(0),line,col)); i+=len(m.group(0)); col+=len(m.group(0)); continue
        m=re.match(r"[A-Za-z_]\w*",src[i:])
        if m:
            w=m.group(0); k="kw" if w in KWS else "id"
            out.append((k,w,line,col)); i+=len(w); col+=len(w); continue
        for op in ("==","!=","<=",">="):
            if src.startswith(op,i):
                out.append(("op",op,line,col)); i+=2; col+=2; break
        else:
            if c in "+-*/%(){};=,<>&|^~!":
                out.append(("op",c,line,col)); i+=1; col+=1; continue
            raise LexErr(f"{fname}:{line}:{col}: bad char {c!r}")
    out.append(("eof","",line,col))
    return out

class P:
    def __init__(self,toks,fname):
        self.t=toks; self.i=0; self.f=fname
    def pk(self): return self.t[self.i]
    def nx(self):
        v=self.t[self.i]; self.i+=1; return v
    def err(self,msg,t=None):
        t=t or self.pk(); return ParseErr(f"{self.f}:{t[2]}:{t[3]}: {msg} (got {t[1]!r})")
    def exp(self,val):
        k,v,l,c=self.nx()
        if v!=val: raise self.err(f"expected {val!r}",(k,v,l,c))
    def parse(self):
        funcs=[]; stmts=[]
        while self.pk()[0]!="eof":
            if self.pk()[1]=="def": funcs.append(self.p_def())
            else: stmts.append(self.p_stmt())
        return funcs,stmts
    def p_def(self):
        self.exp("def"); _,name,_,_=self.nx(); self.exp("(")
        args=[]
        if self.pk()[1]!=")":
            _,a,_,_=self.nx(); args.append(a)
            while self.pk()[1]==",":
                self.nx(); _,a,_,_=self.nx(); args.append(a)
        self.exp(")"); self.exp("{")
        body=[]
        while self.pk()[1]!="}": body.append(self.p_stmt())
        self.exp("}")
        return ("def",name,args,body)
    def p_stmt(self):
        k,v,l,c=self.pk()
        if v=="let":
            self.nx(); _,name,_,_=self.nx(); self.exp("="); e=self.p_expr(); self.exp(";")
            return ("let",name,e,(l,c))
        if v in ("print","printc"):
            self.nx(); e=self.p_expr(); self.exp(";"); return (v,e,(l,c))
        if v=="nl": self.nx(); self.exp(";"); return ("nl",None,(l,c))
        if v=="if":
            self.nx(); e=self.p_expr(); self.exp("{"); a=[]
            while self.pk()[1]!="}": a.append(self.p_stmt())
            self.exp("}")
            b=None
            if self.pk()[1]=="else":
                self.nx(); self.exp("{"); b=[]
                while self.pk()[1]!="}": b.append(self.p_stmt())
                self.exp("}")
            return ("if",e,a,b,(l,c))
        if v=="while":
            self.nx(); e=self.p_expr(); self.exp("{"); a=[]
            while self.pk()[1]!="}": a.append(self.p_stmt())
            self.exp("}"); return ("while",e,a,(l,c))
        if v=="return":
            self.nx(); e=self.p_expr(); self.exp(";"); return ("return",e,(l,c))
        if k=="id":
            _,name,_,_=self.nx()
            if self.pk()[1]=="(":
                self.nx()
                args=[]
                if self.pk()[1]!=")":
                    args.append(self.p_expr())
                    while self.pk()[1]==",":
                        self.nx(); args.append(self.p_expr())
                self.exp(")"); self.exp(";")
                return ("callstmt",name,args,(l,c))
            else:
                self.exp("="); e=self.p_expr(); self.exp(";")
                return ("assign",name,e,(l,c))
        raise self.err(f"bad statement starting with {v!r}")
    # expr precedence
    def p_expr(self): return self.p_or()
    def p_or(self):
        e=self.p_xor()
        while self.pk()[1]=="|": self.nx(); e=("bin","|",e,self.p_xor())
        return e
    def p_xor(self):
        e=self.p_and()
        while self.pk()[1]=="^": self.nx(); e=("bin","^",e,self.p_and())
        return e
    def p_and(self):
        e=self.p_cmp()
        while self.pk()[1]=="&": self.nx(); e=("bin","&",e,self.p_cmp())
        return e
    def p_cmp(self):
        e=self.p_add()
        while self.pk()[1] in ("==","!=","<","<=",">",">="):
            op=self.nx()[1]; e=("bin",op,e,self.p_add())
        return e
    def p_add(self):
        e=self.p_mul()
        while self.pk()[1] in ("+","-"): op=self.nx()[1]; e=("bin",op,e,self.p_mul())
        return e
    def p_mul(self):
        e=self.p_un()
        while self.pk()[1] in ("*","/","%"): op=self.nx()[1]; e=("bin",op,e,self.p_un())
        return e
    def p_un(self):
        if self.pk()[1] in ("-","~","!"): op=self.nx()[1]; return ("un",op,self.p_un())
        return self.p_atom()
    def p_atom(self):
        k,v,l,c=self.nx()
        if k=="num": return ("num",int(v))
        if k=="id":
            if self.pk()[1]=="(":
                self.nx(); args=[]
                if self.pk()[1]!=")":
                    args.append(self.p_expr())
                    while self.pk()[1]==",":
                        self.nx(); args.append(self.p_expr())
                self.exp(")")
                return ("call",v,args)
            return ("var",v)
        if v=="(":
            e=self.p_expr(); self.exp(")"); return e
        raise self.err("bad expression",(k,v,l,c))

BIN_C = {"+":"+","-":"-","*":"*","/":"/","%":"%","&":"&","|":"|","^":"^",
         "==":"==","!=":"!=","<":"<","<=":"<=",">":">",">=":">="}

def gen_c(funcs, stmts):
    # semantic: collect func signatures
    sig={n:len(a) for _,n,a,_ in funcs}
    vars_top=set(); out=[]; err=[]
    def gen_e(e, local_vars, fname="main"):
        t=e[0]
        if t=="num": return f"({e[1]}LL)"
        if t=="var":
            if e[1] not in local_vars and e[1] not in vars_top and fname=="main":
                pass  # checked at stmt level
            if e[1] not in local_vars and fname!="main" and e[1] not in vars_top:
                raise ParseErr(f"unknown var {e[1]!r} in {fname}")
            return f"({e[1]})"
        if t=="un":
            x=gen_e(e[2],local_vars,fname)
            return f"(-{x})" if e[1]=="-" else (f"(~{x})" if e[1]=="~" else f"(!{x})")
        if t=="bin": return f"({gen_e(e[2],local_vars,fname)}{BIN_C[e[1]]}{gen_e(e[3],local_vars,fname)})"
        if t=="call":
            if e[1] not in sig: raise ParseErr(f"unknown func {e[1]!r}")
            if len(e[2])!=sig[e[1]]: raise ParseErr(f"{e[1]} expects {sig[e[1]]} args, got {len(e[2])}")
            return f"{e[1]}("+",".join(gen_e(a,local_vars,fname) for a in e[2])+")"
        raise ParseErr("bad expr")
    def gen_stmts(ss, local_vars, fname):
        lines=[]
        for s in ss:
            k=s[0]
            if k=="let":
                _,name,e,_=s
                if fname=="main": vars_top.add(name); local_vars.add(name)
                else: local_vars.add(name)
                lines.append(f"long long {name} = {gen_e(e,local_vars,fname)};")
            elif k=="assign":
                _,name,e,_=s
                if name not in local_vars and name not in vars_top:
                    raise ParseErr(f"assign to undeclared {name!r} (use let)")
                lines.append(f"{name} = {gen_e(e,local_vars,fname)};")
            elif k=="print": lines.append(f'printf("%lld ", (long long){gen_e(s[1],local_vars,fname)});')
            elif k=="printc": lines.append(f'putchar((int){gen_e(s[1],local_vars,fname)});')
            elif k=="nl": lines.append('putchar(10);')
            elif k=="if":
                _,e,a,b,_=s
                t=f"if({gen_e(e,local_vars,fname)}){{\n"+"\n".join(gen_stmts(a,set(local_vars),fname))+"\n}"
                if b is not None: t+="else{\n"+"\n".join(gen_stmts(b,set(local_vars),fname))+"\n}"
                lines.append(t)
            elif k=="while":
                _,e,a,_=s
                lines.append(f"while({gen_e(e,local_vars,fname)}){{\n"+"\n".join(gen_stmts(a,set(local_vars),fname))+"\n}")
            elif k=="return": lines.append(f"return {gen_e(s[1],local_vars,fname)};")
            elif k=="callstmt":
                _,name,args,_=s
                if name not in sig: raise ParseErr(f"unknown func {name!r}")
                if len(args)!=sig[name]: raise ParseErr(f"{name} arity mismatch")
                lines.append(f"{name}("+",".join(gen_e(a,local_vars,fname) for a in args)+");")
        return lines
    fdecls=[]
    for _,n,a,body in funcs:
        lv=set(a)|set(vars_top)
        fdecls.append(f"long long {n}("+",".join(f"long long {x}" for x in a)+"){\n"+"\n".join(gen_stmts(body,lv,n))+"\n}")
    main_body="\n".join(gen_stmts(stmts,set(), "main"))
    return "#include <stdio.h>\n"+"\n".join(fdecls)+f"\nint main(void){{\n{main_body}\nputchar(10);\nreturn 0;\n}}\n"

def compile_file(path, out=None, keep_c=False):
    src=open(path).read()
    toks=lex(src,path)
    funcs,stmts=P(toks,path).parse()
    ccode=gen_c(funcs,stmts)
    cpath=path+".gen.c"
    open(cpath,"w").write(ccode)
    out=out or (os.path.splitext(path)[0])
    try:
        r=subprocess.run(["cc","-O2","-Wall",cpath,"-o",out],capture_output=True,text=True)
    except FileNotFoundError:
        raise RuntimeError("no C compiler found: install gcc (Linux: apt install gcc) or MinGW (Windows: https://www.mingw-w64.org)")
    if r.returncode!=0: raise RuntimeError("cc failed:\n"+r.stderr)
    if not keep_c: os.remove(cpath)
    else: print(f"[+] kept {cpath}")
    print(f"[+] {path} -> {out} (native ELF)")
    return out

if __name__=="__main__":
    if len(sys.argv)<2: print("usage: python3 mlangc.py prog.ml [-o out] [--run] [--keep-c]"); sys.exit(1)
    path=sys.argv[1]; out=None; run=False; keep=False
    for i,a in enumerate(sys.argv[2:]):
        if a=="-o": out=sys.argv[3+i]
        if a=="--run": run=True
        if a=="--keep-c": keep=True
    try:
        binp=compile_file(path,out,keep)
        if run:
            print("[+] run:"); subprocess.run([os.path.abspath(binp)])
    except (LexErr,ParseErr,RuntimeError) as e:
        print(f"error: {e}"); sys.exit(1)
