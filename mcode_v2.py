"""
M-CODE v2 - powerful general-purpose VM for LEGITIMATE learning
and AUTHORIZED testing only (own code / CTF labs with permission).

Features: stack + 256-cell memory + labels/jumps/functions.
No network, no persistence, no evasion, no exploit payloads by design.

Privacy as before: opcodes shuffled by secret key + XOR stream,
so .mcode2 files look random without key. With key + debugger
anyone can still read it - true human/AI-proof is impossible.
"""
import hashlib, random, struct, sys

# logical op ids
OPS = ["PUSH","POP","DUP","ADD","SUB","MUL","DIV","MOD",
       "AND","OR","XOR","NOT","EQ","LT","GT",
       "JMP","JZ","JNZ","LOAD","STORE",
       "PRINT_NUM","PRINT_CHR","CALL","RET","HALT"]
OP = {n:i for i,n in enumerate(OPS)}
HAS_OP = {OP["PUSH"],OP["JMP"],OP["JZ"],OP["JNZ"],OP["LOAD"],OP["STORE"],OP["CALL"]}

def _maps(key: bytes):
    seed = int.from_bytes(hashlib.sha256(b"M-CODE-V2:" + key).digest()[:8], "big")
    rng = random.Random(seed)
    pool = list(range(256)); rng.shuffle(pool)
    l2w = {i: pool[i] for i in range(len(OPS))}
    w2l = {v:k for k,v in l2w.items()}
    return l2w, w2l

def _ks(key: bytes, n: int) -> bytes:
    out=b""; c=0
    while len(out)<n:
        out+=hashlib.sha256(key+b":"+struct.pack(">I",c)).digest(); c+=1
    return out[:n]

def assemble_text(text: str, key: bytes) -> bytes:
    # pass1: collect labels -> instr index
    lines=[]
    labels={}
    idx=0
    for raw in text.splitlines():
        s=raw.split(";")[0].strip()
        if not s: continue
        if s.endswith(":"):
            labels[s[:-1].strip().upper()]=idx; continue
        if ":" in s:  # "label: PUSH 1"
            lab, rest = s.split(":",1)
            labels[lab.strip().upper()]=idx
            s=rest.strip()
            if not s: continue
        lines.append(s); idx+=1
    prog=[]
    for s in lines:
        p=s.split()
        name=p[0].upper()
        if name not in OP: raise ValueError(f"unknown {name}")
        lop=OP[name]
        arg=None
        if lop in HAS_OP:
            if len(p)<2: raise ValueError(f"{name} needs arg")
            a=p[1]
            try: arg=int(a,0)
            except:  # label
                if a.upper() not in labels: raise ValueError(f"unknown label {a}")
                arg=labels[a.upper()]
        prog.append((lop,arg))
    l2w,_=_maps(key)
    raw=bytearray()
    for lop,arg in prog:
        raw.append(l2w[lop])
        if lop in HAS_OP:
            raw.extend(struct.pack(">i",arg))
    ks=_ks(key,len(raw))
    return bytes(b^ks[i] for i,b in enumerate(raw))

def decode(blob: bytes, key: bytes):
    _,w2l=_maps(key)
    ks=_ks(key,len(blob))
    raw=bytes(b^ks[i] for i,b in enumerate(blob))
    pc=0; prog=[]
    while pc<len(raw):
        w=raw[pc]; pc+=1
        if w not in w2l: raise ValueError(f"bad opcode 0x{w:02x} (wrong key?)")
        lop=w2l[w]; arg=None
        if lop in HAS_OP:
            if pc+4>len(raw): raise ValueError("truncated")
            arg=struct.unpack(">i",raw[pc:pc+4])[0]; pc+=4
        prog.append((lop,arg))
    return prog

def run(prog, mem_size=256, step_limit=100000):
    mem=[0]*mem_size; stack=[]; call=[]; pc=0; steps=0
    out=[]
    def pop():
        if not stack: raise RuntimeError("stack underflow = bug in program")
        return stack.pop()
    while True:
        if not (0<=pc<len(prog)): raise RuntimeError(f"pc out of range {pc}")
        if steps>step_limit: raise RuntimeError("step limit - infinite loop?")
        steps+=1
        lop,arg=prog[pc]
        nxt=pc+1
        if lop==OP["PUSH"]: stack.append(arg)
        elif lop==OP["POP"]: pop()
        elif lop==OP["DUP"]:
            v=pop(); stack.append(v); stack.append(v)
        elif lop==OP["ADD"]: b=pop();a=pop(); stack.append(a+b)
        elif lop==OP["SUB"]: b=pop();a=pop(); stack.append(a-b)
        elif lop==OP["MUL"]: b=pop();a=pop(); stack.append(a*b)
        elif lop==OP["DIV"]:
            b=pop();a=pop()
            if b==0: raise RuntimeError("div by zero")
            stack.append(a//b)
        elif lop==OP["MOD"]:
            b=pop();a=pop()
            if b==0: raise RuntimeError("mod by zero")
            stack.append(a%b)
        elif lop==OP["AND"]: b=pop();a=pop(); stack.append(a&b)
        elif lop==OP["OR"]: b=pop();a=pop(); stack.append(a|b)
        elif lop==OP["XOR"]: b=pop();a=pop(); stack.append(a^b)
        elif lop==OP["NOT"]: stack.append(~pop())
        elif lop==OP["EQ"]: b=pop();a=pop(); stack.append(1 if a==b else 0)
        elif lop==OP["LT"]: b=pop();a=pop(); stack.append(1 if a<b else 0)
        elif lop==OP["GT"]: b=pop();a=pop(); stack.append(1 if a>b else 0)
        elif lop==OP["JMP"]: nxt=arg
        elif lop==OP["JZ"]:
            v=pop()
            if v==0: nxt=arg
        elif lop==OP["JNZ"]:
            v=pop()
            if v!=0: nxt=arg
        elif lop==OP["LOAD"]:
            if not (0<=arg<mem_size): raise RuntimeError("bad LOAD")
            stack.append(mem[arg])
        elif lop==OP["STORE"]:
            if not (0<=arg<mem_size): raise RuntimeError("bad STORE")
            mem[arg]=pop()
        elif lop==OP["PRINT_NUM"]: out.append(str(pop())); print(out[-1],end=" ")
        elif lop==OP["PRINT_CHR"]: out.append(chr(pop())); print(out[-1],end="")
        elif lop==OP["CALL"]: call.append(nxt); nxt=arg
        elif lop==OP["RET"]:
            if not call: raise RuntimeError("RET without CALL")
            nxt=call.pop()
        elif lop==OP["HALT"]: break
        pc=nxt
    print()
    return "".join(out) if out else ""

if __name__=="__main__":
    if len(sys.argv)<3:
        print("usage: python3 mcode_v2.py <key> <file.masm2|file.mcode2> [out]")
        sys.exit(1)
    key=sys.argv[1].encode(); path=sys.argv[2]
    data=open(path,"rb").read()
    if path.endswith(".masm2"):
        blob=assemble_text(data.decode(),key)
        out=sys.argv[3] if len(sys.argv)>3 else path.replace(".masm2",".mcode2")
        open(out,"wb").write(blob)
        print(f"[+] {out} {len(blob)} bytes hex:{blob.hex()[:80]}...")
        print("[+] run:"); run(decode(blob,key))
    else:
        run(decode(data,key))
