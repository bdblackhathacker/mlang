"""
MLang - high-level language compiling to M-CODE v2 (encrypted).
Example:
  let n = 5;
  let r = 1;
  while n > 1 { r = r * n; n = n - 1; }
  print r;
  if r == 120 { printc 72; }
  def add2(a) { return a + 2; }  -- v1.1 supports 0-arg funcs only for simplicity?
Full v1: vars, arithmetic, if/else, while, def/call/return (0 args), print/printc.
Usage: python3 mlang.py <key> prog.ml [out.mcode2]
"""
import re, sys
sys.path.insert(0, "/home/shiboshree_roy/Malware")
from mcode_v2 import assemble_text, decode, run

TOKEN = re.compile(r"""\s*(?:
(?P<num>\d+)|(?P<id>[A-Za-z_]\w*)|(?P<op>==|!=|<=|>=|[+\-*/%(){};=,<>&|^~!])
)""", re.X)

KEYWORDS = {"let","print","printc","if","else","while","def","return","call"}

class Lex:
    def __init__(self, s):
        s = re.sub(r"//.*", "", s)
        self.t=[]
        pos=0
        while pos < len(s):
            if s[pos].isspace(): pos+=1; continue
            m=TOKEN.match(s,pos)
            if not m or m.end()==pos: raise SyntaxError(f"bad char {s[pos]!r} at {pos}")
            pos=m.end()
            for k,v in m.groupdict().items():
                if v is not None:
                    self.t.append((k,v)); break
        self.t.append(("eof","")); self.i=0
    def peek(self): return self.t[self.i]
    def next(self):
        v=self.t[self.i]; self.i+=1; return v
    def expect(self, val):
        k,v=self.next()
        if v!=val: raise SyntaxError(f"expected {val} got {v}")
        return v

class Compiler:
    def __init__(self):
        self.vars={}; self.next_cell=0
        self.asm=[]; self.lbl=0
        self.funcs={}  # name -> label
    def newlabel(self, p="L"): self.lbl+=1; return f"{p}{self.lbl}"
    def var(self, name):
        if name not in self.vars:
            if self.next_cell>=200: raise SyntaxError("too many vars (max 200)")
            self.vars[name]=self.next_cell; self.next_cell+=1
        return self.vars[name]
    def emit(self, s): self.asm.append(s)

    # ---- expr codegen: leaves value on stack ----
    def c_expr(self, lex):
        self.c_or(lex)
    def c_or(self, lex):
        self.c_xor(lex)
        while lex.peek()[1]=="|":
            lex.next(); self.c_xor(lex); self.emit("OR")
    def c_xor(self, lex):
        self.c_and(lex)
        while lex.peek()[1]=="^":
            lex.next(); self.c_and(lex); self.emit("XOR")
    def c_and(self, lex):
        self.c_cmp(lex)
        while lex.peek()[1]=="&":
            lex.next(); self.c_cmp(lex); self.emit("AND")
    def c_cmp(self, lex):
        self.c_add(lex)
        while lex.peek()[1] in ("==","!=","<","<=",">",">="):
            op=lex.next()[1]; self.c_add(lex)
            if op=="==": self.emit("EQ")
            elif op=="<": self.emit("LT")
            elif op==">": self.emit("GT")
            elif op=="!=": self.emit("EQ"); self.emit("PUSH 1"); self.emit("XOR")
            elif op=="<=": self.emit("GT"); self.emit("PUSH 1"); self.emit("XOR")
            elif op==">=": self.emit("LT"); self.emit("PUSH 1"); self.emit("XOR")
    def c_add(self, lex):
        self.c_mul(lex)
        while lex.peek()[1] in ("+","-"):
            op=lex.next()[1]; self.c_mul(lex)
            self.emit("ADD" if op=="+" else "SUB")
    def c_mul(self, lex):
        self.c_un(lex)
        while lex.peek()[1] in ("*","/","%"):
            op=lex.next()[1]; self.c_un(lex)
            self.emit({"*":"MUL","/":"DIV","%":"MOD"}[op])
    def c_un(self, lex):
        if lex.peek()[1]=="-": lex.next(); self.c_un(lex); self.emit("PUSH -1"); self.emit("MUL")
        elif lex.peek()[1]=="~": lex.next(); self.c_un(lex); self.emit("NOT")
        elif lex.peek()[1]=="!": lex.next(); self.c_un(lex); self.emit("PUSH 0"); self.emit("EQ")
        else: self.c_atom(lex)
    def c_atom(self, lex):
        k,v=lex.next()
        if k=="num": self.emit(f"PUSH {v}")
        elif k=="id":
            if lex.peek()[1]=="(":  # call name()
                lex.next(); lex.expect(")")
                if v not in self.funcs: raise SyntaxError(f"unknown func {v}")
                self.emit(f"CALL {self.funcs[v]}")
            else:
                if v not in self.vars: raise SyntaxError(f"unknown var {v}")
                self.emit(f"LOAD {self.vars[v]}")
        elif v=="(":
            self.c_expr(lex); lex.expect(")")
        else: raise SyntaxError(f"bad atom {v}")

    def c_block(self, lex):
        lex.expect("{")
        while lex.peek()[1]!="}": self.c_stmt(lex)
        lex.expect("}")

    def c_stmt(self, lex):
        k,v=lex.peek()
        if v=="let":
            lex.next(); _,name=lex.next(); lex.expect("="); self.c_expr(lex); lex.expect(";")
            self.emit(f"STORE {self.var(name)}")
        elif v=="print":
            lex.next(); self.c_expr(lex); lex.expect(";"); self.emit("PRINT_NUM")
        elif v=="printc":
            lex.next(); self.c_expr(lex); lex.expect(";"); self.emit("PRINT_CHR")
        elif v=="if":
            lex.next(); self.c_expr(lex); le=self.newlabel("ELSE"); ln=self.newlabel("ENDIF")
            self.emit(f"JZ {le}")
            self.c_block(lex)
            if lex.peek()[1]=="else":
                lex.next(); self.emit(f"JMP {ln}"); self.emit(f"{le}:")
                self.c_block(lex); self.emit(f"{ln}:")
            else: self.emit(f"{le}:")
        elif v=="while":
            lex.next(); ls=self.newlabel("LOOP"); le=self.newlabel("WEND")
            self.emit(f"{ls}:"); self.c_expr(lex); self.emit(f"JZ {le}")
            self.c_block(lex); self.emit(f"JMP {ls}"); self.emit(f"{le}:")
        elif v=="return":
            lex.next(); self.c_expr(lex); lex.expect(";")
            self.emit(f"JMP {self.cur_end}")
        elif k=="id":
            # assign x = expr;  or call-statement foo();
            _,name=lex.next()
            if lex.peek()[1]=="(":
                lex.next(); lex.expect(")"); lex.expect(";")
                if name not in self.funcs: raise SyntaxError(f"unknown func {name}")
                self.emit(f"CALL {self.funcs[name]}"); self.emit("POP")
            else:
                lex.expect("="); self.c_expr(lex); lex.expect(";")
                if name not in self.vars: raise SyntaxError(f"unknown var {name} (use let)")
                self.emit(f"STORE {self.vars[name]}")
        else: raise SyntaxError(f"bad stmt {v}")

    def compile(self, src):
        lex=Lex(src)
        # collect defs first
        top=[]  # (type, data)
        while lex.peek()[0]!="eof":
            if lex.peek()[1]=="def":
                lex.next(); _,name=lex.next(); lex.expect("("); lex.expect(")"); lex.expect("{")
                # capture body tokens until matching }
                # easier: parse directly with function context
                flabel=f"FUNC_{name}"
                self.funcs[name]=flabel
                self.cur_end=f"END_{name}"
                self.emit(f"JMP SKIP_{name}")
                self.emit(f"{flabel}:")
                while lex.peek()[1] not in ("}",):
                    if lex.peek()[1]=="return":
                        self.c_stmt(lex)
                    else: self.c_stmt(lex)
                lex.expect("}")
                self.emit(f"{self.cur_end}:"); self.emit("RET")
                self.emit(f"SKIP_{name}:")
            else:
                self.c_stmt(lex)
        self.emit("HALT")
        return "\n".join(self.asm)

def build(src, key: bytes):
    c=Compiler()
    masm=c.compile(src)
    blob=assemble_text(masm, key)
    return masm, blob

if __name__=="__main__":
    if len(sys.argv)<3:
        print("usage: python3 mlang.py <key> <prog.ml> [out.mcode2]"); sys.exit(1)
    key=sys.argv[1].encode(); path=sys.argv[2]
    src=open(path).read()
    masm,blob=build(src,key)
    out=sys.argv[3] if len(sys.argv)>3 else path.replace(".ml",".mcode2")
    open(out,"wb").write(blob)
    print(f"[+] compiled {len(src)} chars -> {out} ({len(blob)} bytes)")
    print("--- generated ASM ---"); print(masm)
    print("--- run ---"); run(decode(blob,key))
