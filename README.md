# MLang — Programming Language, Compilers, VM, Tools, Kernel

![MLang logo](mlang/package/assets/logo.png)

> Designed & Developed by **Shiboshree Roy**

MLang is a hobby programming-language project with **all frontends in one repo**:
a secret-opcode VM, assemblers, two native compilers (C-like + Python/JS-like),
a unified CLI, cross-platform packaging (Linux / Windows / Android), and a
bare-metal kernel stub.

Repo: `https://github.com/bdblackhathacker/mlang` · CLI version `mlang 2.2.0`

## Layout

```
README.md                  <- you are here (full docs)
mcode.py                   secret-opcode stack VM v1 demo
mcode_v2.py                full VM v2 (memory + jumps + calls)
mlang.py                   assembler: readable asm -> encrypted VM blob
mlangc.py                  MLang (C-like ints) -> C -> native ELF, recursion
mlang2.py                  MLang2 (Python/C/JS subset) -> C -> native ELF
mlang/
  cli.py                   unified CLI: build/run/check/vm/examples/version
  grammar.ebnf             full MLang2 grammar (EBNF)
  src/                     copies of the 5 compilers
  examples/                01_factorial, 02_python_subset, 03_class,
                           04_js_style, 05_c_style
  tests/smoke.py           compile+run all .ml2 examples (4/4 OK)
  README.md                deep docs (language reference, VM, kernel)
  kernel/                  freestanding x86-64 multiboot stub (boot.S,
                           kernel.c, linker.ld, kernel.elf)
  package/
    linux/mlang            Linux onefile CLI binary (7.2M, PyInstaller)
    windows/               mlang.spec + BUILD_WINDOWS.txt (build on Windows)
    android/               buildozer.spec + main.py + BUILD_ANDROID.txt
    assets/                logo.png, icon.ico, icon-192/512.png, make_icon.py
    pyproject.toml         pip entry point
  .github/workflows/       (root) CI: builds Linux binary + Windows .exe
.github/workflows/build.yml  CI: ubuntu + windows runners, uploads artifacts
```

## Quickstart (Linux)

```
python3 mlang/cli.py version
python3 mlang/cli.py run mlang/examples/04_js_style.ml2
python3 mlang/cli.py run mlang/examples/05_c_style.ml
python3 mlang/tests/smoke.py
./mlang/package/linux/mlang run mlang/examples/01_factorial.ml2
```

## Language (MLang2)

One compiler accepts three styles at once: `let|var`, `def|function`,
`print|log`. Full grammar in `mlang/grammar.ebnf`.

```js
import math;
let n = 5;  var s = "hi" + "!";  log s;
let a = [1, 2, 3];  print a[0];  a[1] = 99;  print len(a);
for i in range(3) { print i; }   // 0..2
for i in range(1, 4) { print i; }
for x in a { print x + 1; }
while n > 1 { n = n - 1; }
if n == 1 { print "one"; } else { print "other"; }
function add(a, b) { return a + b; }
log add(2, 3);
fwrite("f.txt", "hi");  fappend("f.txt", "!");
let t = fread("f.txt");          // files
let name = input("name: ");      // stdin
print sqrt(16);
try { print a[99]; } catch { print "bad"; }  // div0/OOB/len/fopen
throw "boom";
class Point { x; y; }            // fields only (phase 1)
let p = new Point();
p.x = 3;  print p.x + p.y;
print sha256("abc");             // crypto: sha256/b64enc/b64dec/xor/rand
print b64enc(xor("hi", "K"));
```

Operators: `+ - * / % & | ^ == != < <= > >= and or not - ~ !`.
`/` and `%` by zero, out-of-range index, bad `len()`, missing file ->
nearest `catch`, else exit(1).

## How it works

Two pipelines, one repo:

**A. Native path** (`.ml2` / `.ml` -> real binary):
`lex()` turns source into tokens with line/col ->
`P().parse()` builds statements/expressions (precedence: `or/and/cmp/add/mul/unary`) ->
`gen()` emits C (MLang2 uses a `Val` tagged union: int/str/list/object, so
`print`/`+`/`len` work on any type; `mlangc` emits plain `long long`) ->
`cc -O2` compiles to a native ELF binary. Errors carry `file:line:col`.

**B. Secret-VM path** (`.masm2` -> `.mcode2` blob):
`assemble_text()` maps each logical opcode through a key-derived shuffle
(`SHA256("M-CODE..."+key)` seeded) so wire bytes differ per key, then XORs
everything with a `SHA256(key:counter)` stream. Because only `PUSH` carries
an operand and the mapping is secret, instruction boundaries are hidden
without the key. `decode()` + `run()` (stack + 256 memory cells + call stack,
step limit, bounds checks) execute it.

## Example: all code

**1. MLang2 Python-style** (`mlang/examples/02_python_subset.ml2`):
```js
let nums = [1, 2, 3];
print nums;            // [1,2,3]
print len(nums);       // 3
for i in range(3) { print i; }       // 0 1 2
for x in nums { print x + 1; }       // 2 3 4
let s = "hi" + "!";  print s;        // hi!
fwrite("hello.txt", "hello");
let t = fread("hello.txt");  print t;
try { print nums[99]; } catch { print "bad-index"; }
```

**2. JS-style aliases** (`mlang/examples/04_js_style.ml2`, same compiler):
```js
var total = 0;
function add(a, b) { return a + b; }
log add(2, 3);         // 5
for i in range(3) { log i;  total = total + i; }
log total;             // 3
```

**3. Class fields** (`mlang/examples/03_class.ml2`):
```js
class Point { x; y; }
let p = new Point();
p.x = 3;  p.y = 4;
print p.x + p.y;       // 7
```

**4. C-style ints + recursion** (`mlang/examples/05_c_style.ml`, via `mlangc`):
```c
def fact(n) {
  if n <= 1 { return 1; }
  else { return n * fact(n - 1); }
}
let r = fact(5);
print r;               // 120
```

**5. Secret-VM assembly** (via `mcode_v2`, needs a key):
```
PUSH 5
STORE 0
PUSH 1
STORE 1
loop:
LOAD 0
PUSH 1
GT
JZ end
LOAD 1
LOAD 0
MUL
STORE 1
LOAD 0
PUSH 1
SUB
STORE 0
JMP loop
end:
LOAD 1
PRINT_NUM
HALT
```
```
python3 mlang/cli.py vm mysecret123 prog.masm2   # -> prog.mcode2 (random-looking) + runs it
python3 mcode.py mykey demo.masm demo.mcode
```

**6. CLI, packaging, kernel:**
```
python3 mlang/cli.py build prog.ml2 -o prog --keep-c -v
python3 mlang/cli.py run mlang/examples/01_factorial.ml2   # 120
python3 mlang/cli.py check prog.ml2
python3 mlang/tests/smoke.py                               # 4/4 OK
./mlang/package/linux/mlang version
python3 mlang/package/assets/make_icon.py   # logo.png -> icon.ico + android pngs
make -C mlang/kernel kernel.elf             # multiboot i386 stub
```

## Compilers

| File | Input | Output | Notes |
|---|---|---|---|
| `mlang2.py` | `.ml2` Python/C/JS subset | C -> native ELF | strings, lists, for-range/in, files, input, try/catch, classes-fields |
| `mlangc.py` | `.ml` C-like ints | C -> native ELF | 64-bit ints, recursion, `def/while/if` |
| `mlang.py` | `.masm` readable asm | encrypted VM blob | 0-arg funcs, secret opcodes |
| `mcode.py` / `mcode_v2.py` | `.masm`/`.masm2` / `.mcode*` | run encrypted VM | opcode shuffle + XOR stream per key |
| `mlang/cli.py` | `.ml2`/`.ml` + `vm <key>` | routes to above | single entry point |

## Secret VM (encrypted demo)

```
python3 mcode.py mykey demo.masm demo.mcode
python3 mcode_v2.py mykey prog.masm2
python3 mlang/cli.py vm mykey prog.masm2
```

Privacy = opcode map shuffled from the key + SHA256 XOR stream, so blobs
look random and instruction boundaries are hidden without the key.
**Not unbreakable**: key + debugger can always dump decode/run. See
`mlang/README.md` for the full security note.

## CLI

```
python3 mlang/cli.py build prog.ml2 [-o out] [--keep-c] [-v]
python3 mlang/cli.py build prog.ml [-o out]
python3 mlang/cli.py run  mlang/examples/04_js_style.ml2
python3 mlang/cli.py check prog.ml2
python3 mlang/cli.py vm mykey prog.masm2
python3 mlang/cli.py examples
python3 mlang/cli.py version
```

## Packaging: Linux / Windows / Android

- **Linux** (done here): `mlang/package/linux/mlang` — PyInstaller onefile,
  verified `version` + example runs.
- **Windows `.exe` with logo icon**: PyInstaller can't cross-compile, so it
  builds on a Windows runner. Either follow
  `mlang/package/windows/BUILD_WINDOWS.txt` on a Windows PC
  (save logo as `package/assets/logo.png`, `make_icon.py`, then
  `pyinstaller --icon ...`), or push and take the `mlang-windows`
  artifact from GitHub Actions (`.github/workflows/build.yml`).
- **Android APK**: `mlang/package/android/` (`buildozer.spec`, Kivy-launcher
  `main.py`, `BUILD_ANDROID.txt`). Needs SDK/NDK + `buildozer android debug`.
  The APK is a demo launcher; the Linux CLI stays primary.
- Icons: `mlang/package/assets/` — `logo.png` (1254px, from project logo),
  `make_icon.py` (needs `pip install pillow`) generates
  `icon.ico` + `icon-192/512.png`.

## Kernel

`mlang/kernel/` is a minimal freestanding i386 multiboot stub (GAS `boot.S`,
no-libc `kernel.c`, `linker.ld`) proving the boot path — `kernel.elf`
builds with stock `gcc -m32`. A full MLang-on-bare-metal kernel (Val runtime
without libc, arena allocator, drivers) is future work. Details +
`make` targets in `mlang/kernel/README.md`.

## Releases

GitHub Actions builds `mlang-linux` + `mlang-windows` artifacts per push.
Publish them via Releases (`gh release create v2.2.0 ...`) with the Linux
binary, `mlang.exe`, icons, and `kernel.elf`.

## Roadmap

- Classes phase 2: methods, inheritance, magic methods (needs GC/runtime)
- Full types: floats, dict/set/tuple, modules, exception hierarchy
- Library bindings (NumPy/Pandas/DB pattern: C helpers + builtins)
- Bare-metal Val runtime for a real MLang kernel
