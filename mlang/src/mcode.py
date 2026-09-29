"""
M-CODE - private machine-only demo language.
NOT truly un-readable by humans/AI (impossible).
It is unreadable WITHOUT the secret key, because:
1. opcodes are randomly shuffled from key (no fixed header)
2. instruction boundaries are hidden (only PUSH has operand, but
   attacker doesn't know which wire-byte is PUSH)
3. all bytes are XOR-encrypted with SHA256(key, counter) keystream

With key -> machine runs it.
Without key -> bytes look like random noise.
But debugger + key = human/AI can read it. That's unavoidable.
"""
import hashlib
import random
import struct
import sys

# Logical ops (never appear on disk)
OP_PUSH = 0
OP_ADD = 1
OP_SUB = 2
OP_MUL = 3
OP_DIV = 4
OP_PRINT_NUM = 5
OP_PRINT_CHR = 6
OP_HALT = 7

LOGICAL_OPS = {
    "PUSH": OP_PUSH,
    "ADD": OP_ADD,
    "SUB": OP_SUB,
    "MUL": OP_MUL,
    "DIV": OP_DIV,
    "PRINT_NUM": OP_PRINT_NUM,
    "PRINT_CHR": OP_PRINT_CHR,
    "HALT": OP_HALT,
}

HAS_OPERAND = {OP_PUSH}

def _derive_maps(key: bytes):
    # wire opcode <-> logical opcode, derived secretly from key
    seed = int.from_bytes(hashlib.sha256(b"M-CODE-MAP:" + key).digest()[:8], "big")
    rng = random.Random(seed)
    pool = list(range(256))
    rng.shuffle(pool)
    logical_to_wire = {i: pool[i] for i in range(8)}
    wire_to_logical = {v: k for k, v in logical_to_wire.items()}
    return logical_to_wire, wire_to_logical

def _keystream(key: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + b":" + struct.pack(">I", counter)).digest()
        counter += 1
    return out[:length]

def assemble(source_lines, key: bytes) -> bytes:
    """source_lines like [('PUSH', 72), ('PRINT_CHR', None), ...]"""
    logical_to_wire, _ = _derive_maps(key)
    raw = bytearray()
    for op_name, arg in source_lines:
        lop = LOGICAL_OPS[op_name]
        raw.append(logical_to_wire[lop])
        if lop in HAS_OPERAND:
            raw.extend(struct.pack(">i", arg))
    ks = _keystream(key, len(raw))
    return bytes(b ^ ks[i] for i, b in enumerate(raw))

def disassemble_or_run(blob: bytes, key: bytes, run=True):
    _, wire_to_logical = _derive_maps(key)
    ks = _keystream(key, len(blob))
    raw = bytes(b ^ ks[i] for i, b in enumerate(blob))
    # decode
    pc = 0
    prog = []  # list of (lop, arg)
    while pc < len(raw):
        w = raw[pc]
        pc += 1
        if w not in wire_to_logical:
            raise ValueError(f"invalid wire opcode 0x{w:02x} at offset {pc-1} (wrong key?)")
        lop = wire_to_logical[w]
        arg = None
        if lop in HAS_OPERAND:
            if pc + 4 > len(raw):
                raise ValueError("truncated operand")
            arg = struct.unpack(">i", raw[pc:pc+4])[0]
            pc += 4
        prog.append((lop, arg))
    if not run:
        return prog
    # execute stack machine
    stack = []
    out_chars = []
    pc = 0
    while pc < len(prog):
        lop, arg = prog[pc]
        if lop == OP_PUSH:
            stack.append(arg)
        elif lop == OP_ADD:
            b = stack.pop(); a = stack.pop(); stack.append(a + b)
        elif lop == OP_SUB:
            b = stack.pop(); a = stack.pop(); stack.append(a - b)
        elif lop == OP_MUL:
            b = stack.pop(); a = stack.pop(); stack.append(a * b)
        elif lop == OP_DIV:
            b = stack.pop(); a = stack.pop(); stack.append(a // b)
        elif lop == OP_PRINT_NUM:
            v = stack.pop(); print(v, end=" "); out_chars.append(str(v))
        elif lop == OP_PRINT_CHR:
            v = stack.pop(); print(chr(v), end=""); out_chars.append(chr(v))
        elif lop == OP_HALT:
            break
        pc += 1
    print()
    return prog

def parse_asm(text: str):
    prog = []
    for line in text.strip().splitlines():
        line = line.split(";")[0].strip()
        if not line:
            continue
        parts = line.split()
        op = parts[0].upper()
        if op not in LOGICAL_OPS:
            raise ValueError(f"unknown op {op}")
        arg = int(parts[1]) if len(parts) > 1 else None
        prog.append((op, arg))
    return prog

if __name__ == "__main__":
    # Usage: python3 mcode.py <key> <file.masm> [out.mcode]
    #        python3 mcode.py <key> <file.mcode>  (to run)
    if len(sys.argv) < 3:
        print("usage:")
        print("  assemble+run from asm text: python3 mcode.py mysecret demo.masm")
        print("  run encrypted blob:         python3 mcode.py mysecret demo.mcode")
        sys.exit(1)
    key = sys.argv[1].encode()
    path = sys.argv[2]
    with open(path, "rb") as f:
        data = f.read()
    if path.endswith(".masm"):
        prog = parse_asm(data.decode())
        blob = assemble(prog, key)
        out = sys.argv[3] if len(sys.argv) > 3 else path.replace(".masm", ".mcode")
        with open(out, "wb") as f:
            f.write(blob)
        print(f"[+] assembled {len(prog)} instr -> {out} ({len(blob)} bytes, looks random)")
        print(f"    hex: {blob.hex()[:96]}...")
        print("[+] running with correct key:")
        disassemble_or_run(blob, key, run=True)
    else:
        print("[+] running encrypted blob with given key:")
        disassemble_or_run(data, key, run=True)
