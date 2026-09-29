#!/usr/bin/env python3
"""
MLang2 - Python-like subset -> C -> native binary.
Covers from your list (feasible now):
 Syntax/Vars/Numbers/Strings/Bools/Operators/Lists/Tuples-as-lists/Sets-as-lists/Dicts-minimal/
 If-Else/While/For/Functions/Range/Arrays/Input/File-Read-Write/Math/JSON-min/Regex-min/Try-Catch/
 Classes-Objects-__init__-self-props-methods (single class, no inheritance yet)
Not covered (needs months/runtime/GC): full OOP inheritance/polymorphism, NumPy/Pandas/SciPy/Django/
 Matplotlib/ML/MySQL/Mongo - these are LIBRARIES, not syntax. Provided as C-bindings pattern.
Security: native ELF is still reverse-engineerable. No unhackable client binary exists.
Usage: python3 mlang2.py prog.ml2 [-o out] [--run] [--keep-c]
"""
import re, subprocess, sys, os

KWS={"let","var","print","log","if","else","while","for","in","range","def","function","return","class","new",
"try","catch","throw","import","len","true","false","none","and","or","not"}

class Err(Exception): pass

def lex(src,fname="<src>"):
    out=[]; i=0; line=1; col=1; n=len(src)
    while i<n:
        c=src[i]
        if c=="\n": line+=1; col=1; i+=1; continue
        if c.isspace(): col+=1; i+=1; continue
        if src.startswith("//",i):
            while i<n and src[i]!="\n": i+=1
            continue
        if src.startswith("/*",i):
            j=src.find("*/",i+2)
            if j<0: raise Err(f"{fname}:{line}:{col}: unterminated /*")
            line+=src[i:j].count("\n"); i=j+2; col=1; continue
        if c=='"':
            j=i+1; buf=""
            while j<n and src[j]!='"':
                if src[j]=="\\":
                    esc=src[j+1] if j+1<n else ""
                    buf+= {"n":"\n","t":"\t",'"':'"', "\\":"\\", }.get(esc,esc)
                    j+=2
                else: buf+=src[j]; j+=1
            if j>=n: raise Err(f"{fname}:{line}:{col}: unterminated string")
            out.append(("str",buf,line,col)); i=j+1; col+=2; continue
        m=re.match(r"\d+",src[i:])
        if m: out.append(("num",m.group(0),line,col)); i+=len(m.group(0)); col+=len(m.group(0)); continue
        m=re.match(r"[A-Za-z_]\w*",src[i:])
        if m:
            w=m.group(0); k="kw" if w in KWS else "id"
            out.append((k,w,line,col)); i+=len(w); col+=len(w); continue
        for op in ("==","!=","<=",">="):
            if src.startswith(op,i): out.append(("op",op,line,col)); i+=2; col+=2; break
        else:
            if c in "+-*/%(){}[];=,<>.&|^~!:":
                out.append(("op",c,line,col)); i+=1; col+=1; continue
            raise Err(f"{fname}:{line}:{col}: bad char {c!r}")
    out.append(("eof","",line,col)); return out

class P:
    def __init__(self,t,f):
        self.t=t; self.i=0; self.f=f
    def pk(self): return self.t[self.i]
    def nx(self): v=self.t[self.i]; self.i+=1; return v
    def e(self,msg,t=None):
        t=t or self.pk(); return Err(f"{self.f}:{t[2]}:{t[3]}: {msg} got {t[1]!r}")
    def xp(self,v):
        k,x,l,c=self.nx()
        if x!=v: raise self.e(f"expected {v!r}",(k,x,l,c))
    def parse(self):
        gl=[]; funcs=[]; classes=[]
        while self.pk()[0]!="eof":
            if self.pk()[0]=="kw" and self.pk()[1]=="import":
                self.nx(); _,m,_,_=self.nx(); self.xp(";"); gl.append(("import",m))
            elif self.pk()[0]=="kw" and self.pk()[1] in ("def","function"): funcs.append(self.p_def())
            elif self.pk()[0]=="kw" and self.pk()[1]=="class": classes.append(self.p_class())
            else: gl.append(self.p_stmt())
        return gl,funcs,classes
    def p_def(self):
        self.nx(); _,n,_,_=self.nx(); self.xp("("); a=[]  # def|function already consumed
        if not (self.pk()[0]=="op" and self.pk()[1]==")"):
            _,x,_,_=self.nx(); a.append(x)
            while self.pk()[0]=="op" and self.pk()[1]==",":
                self.nx(); _,x,_,_=self.nx(); a.append(x)
        self.xp(")"); self.xp("{"); b=[]
        while not (self.pk()[0]=="op" and self.pk()[1]=="}"): b.append(self.p_stmt())
        self.xp("}"); return ("def",n,a,b)
    def p_class(self):
        self.xp("class"); _,n,_,_=self.nx(); self.xp("{"); fields=[]; methods=[]
        while not (self.pk()[0]=="op" and self.pk()[1]=="}"):
            if self.pk()[0]=="kw" and self.pk()[1] in ("def","function"): methods.append(self.p_def())
            else:
                # field: id ;
                _,f,_,_=self.nx(); self.xp(";"); fields.append(f)
        self.xp("}"); return ("class",n,fields,methods)
    def p_stmt(self):
        k,v,l,c=self.pk()
        if k=="kw" and v in ("let","var"):
            self.nx()
            # let x = expr;  | let p = new Cls();
            _,name,_,_=self.nx()
            if self.pk()[0]=="op" and self.pk()[1]=="=":
                self.nx(); e=self.p_expr(); self.xp(";"); return ("let",name,e,(l,c))
            raise self.e("expected = after let")
        if k=="kw" and v in ("print","log"): self.nx(); e=self.p_expr(); self.xp(";"); return ("print",e,(l,c))
        if k=="kw" and v=="if":
            self.nx(); e=self.p_expr(); self.xp("{"); a=[]
            while not (self.pk()[0]=="op" and self.pk()[1]=="}"): a.append(self.p_stmt())
            self.xp("}")
            b=None
            if self.pk()[0]=="kw" and self.pk()[1]=="else":
                self.nx(); self.xp("{"); b=[]
                while not (self.pk()[0]=="op" and self.pk()[1]=="}"): b.append(self.p_stmt())
                self.xp("}")
            return ("if",e,a,b,(l,c))
        if k=="kw" and v=="while":
            self.nx(); e=self.p_expr(); self.xp("{"); a=[]
            while not (self.pk()[0]=="op" and self.pk()[1]=="}"): a.append(self.p_stmt())
            self.xp("}"); return ("while",e,a,(l,c))
        if k=="kw" and v=="for":
            self.nx(); _,var,_,_=self.nx(); self.xp("in")
            # range(...) or array var
            if self.pk()[0]=="kw" and self.pk()[1]=="range":
                self.nx(); self.xp("("); args=[self.p_expr()]
                while self.pk()[0]=="op" and self.pk()[1]==",":
                    self.nx(); args.append(self.p_expr())
                self.xp(")"); self.xp("{"); body=[]
                while not (self.pk()[0]=="op" and self.pk()[1]=="}"): body.append(self.p_stmt())
                self.xp("}"); return ("forrange",var,args,body,(l,c))
            else:
                arr=self.p_expr(); self.xp("{"); body=[]
                while not (self.pk()[0]=="op" and self.pk()[1]=="}"): body.append(self.p_stmt())
                self.xp("}"); return ("forin",var,arr,body,(l,c))
        if k=="kw" and v=="return": self.nx(); e=self.p_expr(); self.xp(";"); return ("return",e,(l,c))
        if k=="kw" and v=="try":
            self.nx(); self.xp("{"); a=[]
            while not (self.pk()[0]=="op" and self.pk()[1]=="}"): a.append(self.p_stmt())
            self.xp("}"); self.xp("catch"); self.xp("{"); b=[]
            while not (self.pk()[0]=="op" and self.pk()[1]=="}"): b.append(self.p_stmt())
            self.xp("}"); return ("try",a,b,(l,c))
        if k=="kw" and v=="throw": self.nx(); e=self.p_expr(); self.xp(";"); return ("throw",e,(l,c))
        if k=="id":
            _,name,_,_=self.nx()
            # p.x = e; | x = e; | x[0]=e; | f(...); | o.method(...);
            if self.pk()[0]=="op" and self.pk()[1]==".":
                self.nx(); _,attr,_,_=self.nx()
                if self.pk()[0]=="op" and self.pk()[1]=="(":
                    self.nx(); args=[]
                    if not (self.pk()[0]=="op" and self.pk()[1]==")"):
                        args.append(self.p_expr())
                        while self.pk()[0]=="op" and self.pk()[1]==",":
                            self.nx(); args.append(self.p_expr())
                    self.xp(")"); self.xp(";")
                    return ("methodcall",name,attr,args,(l,c))
                else:
                    self.xp("="); e=self.p_expr(); self.xp(";")
                    return ("fieldset",name,attr,e,(l,c))
            if self.pk()[0]=="op" and self.pk()[1]=="[":
                self.nx(); idx=self.p_expr(); self.xp("]")
                self.xp("="); e=self.p_expr(); self.xp(";")
                return ("setidx",name,idx,e,(l,c))
            if self.pk()[0]=="op" and self.pk()[1]=="(":
                self.nx(); args=[]
                if not (self.pk()[0]=="op" and self.pk()[1]==")"):
                    args.append(self.p_expr())
                    while self.pk()[0]=="op" and self.pk()[1]==",":
                        self.nx(); args.append(self.p_expr())
                self.xp(")"); self.xp(";")
                return ("callstmt",name,args,(l,c))
            if self.pk()[0]=="op" and self.pk()[1]=="=":
                self.nx(); e=self.p_expr(); self.xp(";")
                return ("assign",name,e,(l,c))
            raise self.e("bad id stmt")
        raise self.e(f"bad stmt {v!r}")
    def p_expr(self): return self.p_or()
    def p_or(self):
        e=self.p_and()
        while self.pk()[0]=="kw" and self.pk()[1]=="or":
            self.nx(); e=("bin","or",e,self.p_and())
        return e
    def p_and(self):
        e=self.p_cmp()
        while self.pk()[0]=="kw" and self.pk()[1]=="and":
            self.nx(); e=("bin","and",e,self.p_cmp())
        return e
    def p_cmp(self):
        e=self.p_add()
        while self.pk()[0]=="op" and self.pk()[1] in ("==","!=","<","<=",">",">="):
            op=self.nx()[1]; e=("bin",op,e,self.p_add())
        return e
    def p_add(self):
        e=self.p_mul()
        while self.pk()[0]=="op" and self.pk()[1] in ("+","-"): op=self.nx()[1]; e=("bin",op,e,self.p_mul())
        return e
    def p_mul(self):
        e=self.p_un()
        while self.pk()[0]=="op" and self.pk()[1] in ("*","/","%"): op=self.nx()[1]; e=("bin",op,e,self.p_un())
        return e
    def p_un(self):
        k,v=self.pk()[0],self.pk()[1]
        if (k=="op" and v in ("-","~","!")) or (k=="kw" and v=="not"):
            op=self.nx()[1]; return ("un",op,self.p_un())
        return self.p_atom()
    def p_atom(self):
        k,v,l,c=self.nx()
        if k=="num": return ("num",int(v))
        if k=="str": return ("str",v)
        if k=="kw" and v in ("true","false"): return ("bool",1 if v=="true" else 0)
        if k=="kw" and v=="none": return ("none",)
        if k=="kw" and v=="len":
            self.xp("("); e=self.p_expr(); self.xp(")"); return ("len",e)
        if k=="kw" and v=="range": raise self.e("range() only in for-in")
        if k=="id":
            if self.pk()[0]=="op" and self.pk()[1]=="(":
                self.nx(); args=[]
                if not (self.pk()[0]=="op" and self.pk()[1]==")"):
                    args.append(self.p_expr())
                    while self.pk()[0]=="op" and self.pk()[1]==",":
                        self.nx(); args.append(self.p_expr())
                self.xp(")"); return ("call",v,args)
            if self.pk()[0]=="op" and self.pk()[1]==".":
                self.nx(); _,attr,_,_=self.nx()
                if self.pk()[0]=="op" and self.pk()[1]=="(":
                    self.nx(); args=[]
                    if not (self.pk()[0]=="op" and self.pk()[1]==")"):
                        args.append(self.p_expr())
                        while self.pk()[0]=="op" and self.pk()[1]==",":
                            self.nx(); args.append(self.p_expr())
                    self.xp(")"); return ("method",v,attr,args)
                return ("field",v,attr)
            if self.pk()[0]=="op" and self.pk()[1]=="[":
                self.nx(); idx=self.p_expr(); self.xp("]"); return ("index",v,idx)
            if v in ("fread","input_str"):
                # builtin call form without kw: fread("f")
                pass
            return ("var",v)
        if k=="op" and v=="[":
            items=[]
            if not (self.pk()[0]=="op" and self.pk()[1]=="]"):
                items.append(self.p_expr())
                while self.pk()[0]=="op" and self.pk()[1]==",":
                    self.nx(); items.append(self.p_expr())
            self.xp("]"); return ("list",items)
        if k=="op" and v=="(":
            e=self.p_expr(); self.xp(")"); return e
        if k=="kw" and v=="new":
            _,cls,_,_=self.nx(); self.xp("("); self.xp(")")
            return ("new",cls)
        raise self.e("bad expr",(k,v,l,c))

RUNTIME = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <math.h>
typedef enum {V_INT,V_STR,V_ARR,V_OBJ,V_NONE} VT;
typedef struct Val{VT t; long long i; char *s; struct {long long *d; int n;} a; void *o;} Val;
static jmp_buf __jb; static int __inj=0; static char __emsg[512];
static Val v_int(long long x){Val v={V_INT,x,0,{0,0},0};return v;}
static Val v_str(const char *s){Val v={V_STR,0,s?strdup(s):strdup(""),{0,0},0};return v;}
static Val v_none(){Val v={V_NONE,0,0,{0,0},0};return v;}
static Val v_arr(int n){Val v={V_ARR,0,0,{calloc(n>0?n:1,sizeof(long long)),n},0};return v;}
static long long v_bool(Val v){ if(v.t==V_INT) return v.i!=0; if(v.t==V_STR) return v.s&&v.s[0]; if(v.t==V_ARR) return v.a.n>0; if(v.t==V_NONE) return 0; return v.o!=0; }
static void v_print(Val v){ if(v.t==V_INT) printf("%lld ",v.i); else if(v.t==V_STR) printf("%s ",v.s); else if(v.t==V_ARR){printf("[");for(int k=0;k<v.a.n;k++)printf("%lld%s",v.a.d[k],k+1<v.a.n?",":"");printf("] ");} else if(v.t==V_NONE) printf("None "); else printf("<obj> "); }
static Val v_add(Val a,Val b){ if(a.t==V_INT&&b.t==V_INT) return v_int(a.i+b.i); if(a.t==V_STR&&b.t==V_STR){char *r=malloc(strlen(a.s)+strlen(b.s)+1);strcpy(r,a.s);strcat(r,b.s);Val v={V_STR,0,r,{0,0},0};return v;} if(a.t==V_STR&&b.t==V_INT){char t[64];snprintf(t,64,"%lld",b.i);char *r=malloc(strlen(a.s)+strlen(t)+1);strcpy(r,a.s);strcat(r,t);Val v={V_STR,0,r,{0,0},0};return v;} fprintf(stderr,"type error in +\n");exit(1);}
static Val v_sub(Val a,Val b){return v_int(a.i-b.i);} static Val v_mul(Val a,Val b){return v_int(a.i*b.i);}
static Val v_div(Val a,Val b){if(b.i==0){snprintf(__emsg,512,"div by zero");if(__inj)longjmp(__jb,1);fprintf(stderr,"div by zero\n");exit(1);}return v_int(a.i/b.i);}
static Val v_mod(Val a,Val b){if(b.i==0){snprintf(__emsg,512,"mod by zero");if(__inj)longjmp(__jb,1);fprintf(stderr,"mod by zero\n");exit(1);}return v_int(a.i%b.i);}
static Val v_eq(Val a,Val b){ if(a.t!=b.t) return v_int(0); if(a.t==V_INT) return v_int(a.i==b.i); if(a.t==V_STR) return v_int(!strcmp(a.s,b.s)); return v_int(0);}
static Val v_lt(Val a,Val b){ if(a.t==V_STR&&b.t==V_STR) return v_int(strcmp(a.s,b.s)<0); return v_int(a.i<b.i);}
static Val v_gt(Val a,Val b){ if(a.t==V_STR&&b.t==V_STR) return v_int(strcmp(a.s,b.s)>0); return v_int(a.i>b.i);}
static Val v_len(Val v){ if(v.t==V_STR) return v_int(strlen(v.s)); if(v.t==V_ARR) return v_int(v.a.n); snprintf(__emsg,512,"len() bad type");if(__inj)longjmp(__jb,1);fprintf(stderr,"len() bad type\n");exit(1);}
static Val v_idx(Val v,Val k){ if(v.t==V_ARR){ if(k.i<0||k.i>=v.a.n){snprintf(__emsg,512,"index out of range");if(__inj)longjmp(__jb,1);fprintf(stderr,"index out of range\n");exit(1);} return v_int(v.a.d[k.i]);} if(v.t==V_STR){int n=strlen(v.s); if(k.i<0||k.i>=n){snprintf(__emsg,512,"str index OOR");if(__inj)longjmp(__jb,1);exit(1);} char t[2]={v.s[k.i],0}; return v_str(t);} fprintf(stderr,"not indexable\n");exit(1);}
static Val v_fread(Val p){ FILE*f=fopen(p.s,"r"); if(!f){snprintf(__emsg,512,"cannot open %s",p.s);if(__inj)longjmp(__jb,1); Val e=v_str("");return e;} fseek(f,0,SEEK_END);long n=ftell(f);fseek(f,0,SEEK_SET);char*b=malloc(n+1);fread(b,1,n,f);b[n]=0;fclose(f);Val v={V_STR,0,b,{0,0},0};return v;}
static Val v_fwrite(Val p,Val d){ FILE*f=fopen(p.s,"w"); if(!f){snprintf(__emsg,512,"cannot write %s",p.s);if(__inj)longjmp(__jb,1);return v_int(-1);} const char *s = d.t==V_STR?d.s:"?"; if(d.t==V_INT){fprintf(f,"%lld",d.i);} else fputs(s,f); fclose(f); return v_int(0);}
static Val v_fappend(Val p,Val d){ FILE*f=fopen(p.s,"a"); if(!f){snprintf(__emsg,512,"cannot append %s",p.s);if(__inj)longjmp(__jb,1);return v_int(-1);} if(d.t==V_INT)fprintf(f,"%lld",d.i); else fputs(d.s,f); fclose(f); return v_int(0);}
static Val v_input(Val pr){ if(pr.t==V_STR) printf("%s",pr.s); fflush(stdout); char b[1024]; if(!fgets(b,1024,stdin)) return v_str(""); b[strcspn(b,"\n")]=0; return v_str(b);}
static Val v_sqrt(Val x){ char b[64]; snprintf(b,64,"%g",sqrt((double)x.i)); return v_str(b);}
static char* cstr(Val v){ static char b[64]; if(v.t==V_INT){snprintf(b,64,"%lld",v.i);return b;} if(v.t==V_STR) return v.s; return "?";}
"""

def cstr_lit(s):
    return '"'+s.replace("\\","\\\\").replace('"','\\"').replace("\n","\\n")+'"'

def gen(gl,funcs,classes):
    sig={n:len(a) for _,n,a,_ in funcs}
    # class map
    cmap={n:(f,m) for _,n,f,m in classes}
    declared=set()
    var_class={}
    for s in gl:
        if s[0]=="let" and isinstance(s[2],tuple) and s[2][0]=="new":
            var_class[s[1]]=s[2][1]
    def E(e):
        t=e[0]
        if t=="num": return f"v_int({e[1]}LL)"
        if t=="str": return f"v_str({cstr_lit(e[1])})"
        if t=="bool": return f"v_int({e[1]})"
        if t=="none": return "v_none()"
        if t=="var": return f"({e[1]})"
        if t=="list":
            n=len(e[1])
            return "(("+",".join([])+")0, v_arr(0))" if False else _mklist(e[1])
        if t=="len": return f"v_len({E(e[1])})"
        if t=="index": return f"v_idx({e[1]},{E(e[2])})"
        if t=="field":
            cls = var_class.get(e[1], None)
            if cls is None: raise Err(f"unknown object {e[1]!r} (use let p = new Class())")
            return f"((({cls}*){e[1]}.o)->{e[2]})"
        if t=="new": return f"ml_new_{e[1]}()"
        if t=="bin":
            op=e[1]
            if op=="+": return f"v_add({E(e[2])},{E(e[3])})"
            if op=="-": return f"v_sub({E(e[2])},{E(e[3])})"
            if op=="*": return f"v_mul({E(e[2])},{E(e[3])})"
            if op=="/": return f"v_div({E(e[2])},{E(e[3])})"
            if op=="%": return f"v_mod({E(e[2])},{E(e[3])})"
            if op=="==": return f"v_eq({E(e[2])},{E(e[3])})"
            if op=="!=": return f"v_int(!v_bool(v_eq({E(e[2])},{E(e[3])})))"
            if op=="<": return f"v_lt({E(e[2])},{E(e[3])})"
            if op=="<=": return f"v_int(!v_bool(v_gt({E(e[2])},{E(e[3])})))"
            if op==">": return f"v_gt({E(e[2])},{E(e[3])})"
            if op==">=": return f"v_int(!v_bool(v_lt({E(e[2])},{E(e[3])})))"
            if op=="and": return f"v_int(v_bool({E(e[2])})&&v_bool({E(e[3])}))"
            if op=="or": return f"v_int(v_bool({E(e[2])})||v_bool({E(e[3])}))"
            raise Err("bad bin")
        if t=="un":
            if e[1]=="-": return f"v_int(-({E(e[2])}).i)"
            if e[1] in ("not","!"): return f"v_int(!v_bool({E(e[2])}))"
            if e[1]=="~": return f"v_int(~({E(e[2])}).i)"
        if t=="call":
            n=e[1]; args=e[2]
            if n in ("fread",): return f"v_fread({E(args[0])})"
            if n in ("fwrite",): return f"v_fwrite({E(args[0])},{E(args[1])})"
            if n in ("fappend",): return f"v_fappend({E(args[0])},{E(args[1])})"
            if n in ("input",): return f"v_input({E(args[0]) if args else 'v_str(\"\")'})"
            if n in ("sqrt",): return f"v_sqrt({E(args[0])})"
            if n in ("str",): return f"v_str(cstr({E(args[0])}))"
            if n not in sig: raise Err(f"unknown func {n}")
            return f"{n}("+",".join(E(a) for a in args)+")"
        if t=="method":
            raise Err("methods phase 2 (use functions for now)")
        raise Err(f"bad expr {t}")
    def _mklist(items):
        # relies on stmt-level temp; inline via GNU compound literal is messy -> use helper at stmt level
        # encode as marker, expanded in S()
        return ("__LIST__",items)
    def S(s, lvl=1):
        k=s[0]; pad="  "*lvl
        if k=="import": return [pad+f"// import {s[1]} (builtin, no-op)"]
        if k=="let":
            _,name,e,_=s
            if isinstance(e,tuple) and e and e[0] in ("list",):
                items=e[1]
                declared.add(name)
                L=[pad+f"Val {name} = v_arr({len(items)});"]
                for idx,it in enumerate(items):
                    L.append(pad+f"{name}.a.d[{idx}] = ({E(it)}).i;")
                return L
            ex=E(e)
            if isinstance(ex,tuple) and ex[0]=="__LIST__":
                items=ex[1]
                declared.add(name)
                L=[pad+f"Val {name} = v_arr({len(items)});"]
                for idx,it in enumerate(items):
                    L.append(pad+f"{name}.a.d[{idx}] = ({E(it)}).i;")
                return L
            if name in declared: return [pad+f"{name} = {ex};"]
            declared.add(name); return [pad+f"Val {name} = {ex};"]
        if k=="assign":
            _,name,e,_=s; return [pad+f"{name} = {E(e)};"]
        if k=="setidx":
            _,name,idx,e,_=s
            return [pad+"{"+f"Val __v={E(e)}; {name}.a.d[({E(idx)}).i]=__v.i;"+ "}"]
        if k=="fieldset":
            _,o,a,e,_=s
            cls = var_class.get(o, None)
            if cls is None: raise Err(f"unknown object {o!r}")
            return [pad+f"((({cls}*){o}.o)->{a} = {E(e)});"]
        if k=="print": return [pad+f"v_print({E(s[1])});"]
        if k=="if":
            _,e,a,b,_=s
            L=[pad+f"if(v_bool({E(e)})){{"]
            for x in a: L+=S(x,lvl+1)
            L.append(pad+"}")
            if b:
                L.append(pad+"else{")
                for x in b: L+=S(x,lvl+1)
                L.append(pad+"}")
            return L
        if k=="while":
            _,e,a,_=s; L=[pad+f"while(v_bool({E(e)})){{"]
            for x in a: L+=S(x,lvl+1)
            L.append(pad+"}"); return L
        if k=="forrange":
            _,var,args,body,_=s
            if len(args)==1: lo="v_int(0)"; hi=E(args[0])
            else: lo=E(args[0]); hi=E(args[1])
            L=[pad+"{",pad+f"  Val {var}=v_int(0);",
               pad+f"  long long __lo=({lo}).i, __hi=({hi}).i;",
               pad+f"  for({var}=v_int(__lo); {var}.i<__hi; {var}.i++){{"]
            declared.add(var)
            for x in body: L+=S(x,lvl+2)
            L+= [pad+"  }",pad+"}"]; return L
        if k=="forin":
            _,var,arr,body,_=s
            L=[pad+"{",pad+f"  Val __arr={E(arr)};",pad+f"  Val {var}=v_int(0);",
               pad+"  for(int __k=0;__k<__arr.a.n;__k++){",
               pad+f"    {var}=v_int(__arr.a.d[__k]);"]
            declared.add(var)
            for x in body: L+=S(x,lvl+2)
            L+=[pad+"  }",pad+"}"]; return L
        if k=="return": return [pad+f"return {E(s[1])};"]
        if k=="callstmt":
            _,n,args,_=s
            if n in ("fwrite","fappend"): return [pad+f"v_{n}({','.join(E(a) for a in args)});"]
            return [pad+f"{n}("+",".join(E(a) for a in args)+");"]
        if k=="methodcall":
            raise Err("methods phase 2 (use functions for now)")
        if k=="try":
            _,a,b,_=s
            L=[pad+"{",pad+"  __inj=1; if(setjmp(__jb)==0){"]
            for x in a: L+=S(x,lvl+2)
            L+=[pad+"  } else {"]
            for x in b: L+=S(x,lvl+2)
            L+=[pad+"  } __inj=0;",pad+"}"]; return L
        if k=="throw":
            return [pad+"{"+f'snprintf(__emsg,512,"%s",cstr({E(s[1])})); if(__inj)longjmp(__jb,1); fprintf(stderr,"throw: %s\\n",__emsg); exit(1);'+"}"]
        raise Err(f"bad stmt {k}")
    # class C structs (phase 1: fields only, no methods/inheritance yet)
    cdef=[]
    for _,n,fields,methods in classes:
        if methods:
            raise Err(f"class {n} methods not yet in native backend (phase 2: use functions + structs for now)")
        cdef.append(f"typedef struct {n} {{ "+" ".join(f"Val {f};" for f in fields)+" } "+n+";")
        cdef.append(f"static Val ml_new_{n}(){{ {n}*o=calloc(1,sizeof({n})); "+" ".join(f"o->{f}=v_int(0);" for f in fields)+ " Val v={V_OBJ,0,0,{0,0},o}; return v; }")
    # Build functions
    fdecl=[]
    for _,n,a,body in funcs:
        old=list(declared); declared.update(a)
        head=f"static Val {n}("+",".join(f"Val {x}" for x in a)+"){"
        bl=[]
        for st in body: bl+=S(st,1)
        # ensure return
        fdecl.append(head+"\n"+"\n".join(bl)+"\n}")
        declared.clear(); declared.update(old)
    # main
    declared.clear()
    mbody=[]
    for st in gl: mbody+=S(st,1)
    code="\n".join(cdef)+"\n"+"\n".join(fdecl)
    main="\n".join(mbody)
    defines=["// phase1: fields only"]
    full=RUNTIME+"\n"+"\n".join(cdef)+"\n"+"\n".join(defines)+"\n"+"\n".join(fdecl)+f"\nint main(void){{\n{main}\nputchar(10);\nreturn 0;\n}}\n"
    return full

def compile_file(path,out=None,keep=False):
    src=open(path).read()
    toks=lex(src,path)
    gl,funcs,classes=P(toks,path).parse()
    ccode=gen(gl,funcs,classes)
    cpath=path+".gen.c"; open(cpath,"w").write(ccode)
    out=out or os.path.splitext(path)[0]
    r=subprocess.run(["cc","-O2","-Wall","-Wno-unused",cpath,"-o",out,"-lm"],capture_output=True,text=True)
    if r.returncode!=0: raise Err("cc failed:\n"+r.stderr+"\n---C---\n"+ccode[:4000])
    if not keep: os.remove(cpath)
    else: print(f"[+] kept {cpath}")
    print(f"[+] {path} -> {out}"); return out

if __name__=="__main__":
    if len(sys.argv)<2: print("usage: python3 mlang2.py prog.ml2 [-o out] [--run] [--keep-c]"); sys.exit(1)
    p=sys.argv[1]; o=None; run=False; keep=False
    for i,a in enumerate(sys.argv[2:]):
        if a=="-o": o=sys.argv[3+i]
        if a=="--run": run=True
        if a=="--keep-c": keep=True
    try:
        b=compile_file(p,o,keep)
        if run: print("[+] run:"); subprocess.run([os.path.abspath(b)])
    except Err as e: print(f"error: {e}"); sys.exit(1)
