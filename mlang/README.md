# MLang — Real-World Native Compiler

> Designed & Developed by **Shiboshree Roy**

MLang2 is a small Python-like language that compiles to C then to a native ELF via `cc -O2`.

## Layout

```
mlang/
  src/mcode.py      encrypted stack VM v1 (secret opcodes demo)
  src/mcode_v2.py   full VM v2 (memory+jumps+calls)
  src/mlang.py      assembler: readable asm -> encrypted VM blob
  src/mlangc.py     MLang (ints) -> C -> native (recursion, functions)
  src/mlang2.py     MLang2 (Python subset) -> C -> native
  cli.py            unified CLI: build/run/check/examples/version
  grammar.ebnf      full EBNF grammar for MLang2
  examples/         01_factorial, 02_python_subset, 03_class
  tests/smoke.py    compile+run all examples
  kernel/           minimal freestanding stub (QEMU). Full MLang-on-bare-metal is future work.
  docs/             (this README is the doc; add design notes here)
```

## Requirements

- Python 3.10+, `cc`/`gcc`, Linux x86-64

## CLI (all frontends)

```
python3 mlang/cli.py build prog.ml2 [-o out] [--keep-c] [-v]  # Python/C/JS aliases
python3 mlang/cli.py build prog.ml [-o out]                   # C-like ints (mlangc)
python3 mlang/cli.py run mlang/examples/04_js_style.ml2
python3 mlang/cli.py run mlang/examples/05_c_style.ml
python3 mlang/cli.py check prog.ml2
python3 mlang/cli.py vm mykey prog.masm2   # secret VM path
python3 mlang/cli.py examples
python3 mlang/cli.py version                # mlang 2.2.0
```

Aliases (same compiler): `let|var`, `def|function`, `print|log`.

Old frontends still work:

```
python3 mlang/src/mlangc.py prog.ml --run
python3 mlang/src/mlang2.py prog.ml2 --run --keep-c
```

## Language (MLang2 subset)

See `grammar.ebnf` for the full grammar.

```js
import math;                 // no-op hook, builtins always available
let n = 5;                   // int | "str" | [1,2,3] | true/false/none
print n;                     // polymorphic: int/str/list/None
let s = "hi" + "!";          // string concat (+), int+str also works
let a = [1, 2, 3];           // int list
print a[0]; a[1] = 99;       // index get/set (bounds-checked, try/catchable)
print len(a);                // len(list/str)
for i in range(3) {}         // 0..2
for i in range(1, 4) {}       // 1..3
for x in a {}                // for-in over list
while n > 1 { n = n - 1; }
if n == 1 { print "one"; } else { print "other"; }
def add(a, b) { return a + b; }
print add(2, 3);
fwrite("f.txt", "hi");       // files
fappend("f.txt", "!");
let t = fread("f.txt");
let s2 = input("name: ");    // stdin line
print sqrt(16);              // math helper (string result)
try { print a[99]; } catch { print "bad"; }  // div0/index/len/fopen errors
throw "boom";                // user throw -> nearest catch else exit(1)
class Point { x; y; }        // fields only (phase 1)
let p = new Point();         // heap object
p.x = 3; print p.x + p.y;
```

Operators: `+ - * / % & | ^ == != < <= > >= and or not - ~ !` with C-like precedence.
`/` and `%` by zero, OOB index, `len()` mistype, `fread` missing file throw to `catch`.

## What is NOT Python (yet)

- No inheritance / polymorphism / magic methods / exceptions hierarchy — needs GC + runtime (phase 2).
- No `dict`/`set`/`tuple` full semantics — use lists + `len`/index for now.
- No NumPy/Pandas/Django/Matplotlib/ML/MySQL/Mongo — those are libraries, not syntax.
  Pattern for real binding: add C helper in `mlang2.py:RUNTIME` + builtin in `call`.
- No floats — ints + numeric strings only. Add `double` Val arm for real floats.

## VM path (encrypted demo)

```
python3 mlang/src/mcode.py mykey demo.masm demo.mcode
python3 mlang/src/mcode_v2.py mykey prog.masm2
python3 mlang/src/mlang.py mykey prog.masm  # high-level mlang->VM (0-arg funcs)
```

VM privacy = secret opcode shuffle + XOR stream. Looks random without key.
Not unbreakable: key + debugger can always dump it at decode/run.

## Kernel

`kernel/` is a minimal freestanding x86-64 stub proving the boot path, not a full
MLang kernel. A real MLang kernel needs: bare-metal Val runtime (no libc),
no `malloc/printf`, linker script + syscalls. See `kernel/README.md`.

Build (if `gcc` + `qemu-system-x86_64` present):

```
make -C mlang/kernel
make -C mlang/kernel run
```

## Dist / packaging

- Linux CLI binary (built here): `mlang/package/linux/mlang` (7.2M, PyInstaller onefile)
  `./mlang/package/linux/mlang version|run|build|check`
- Windows `.exe` with logo icon: cannot be cross-built on Linux.
  On Windows follow `mlang/package/windows/BUILD_WINDOWS.txt`
  (save chat logo as `package/assets/logo.png`, `make_icon.py`, PyInstaller `--icon`),
  or push and use `.github/workflows/build.yml` (builds `dist/mlang.exe`).
- Android APK: `mlang/package/android/` (`buildozer.spec`, `main.py`, `BUILD_ANDROID.txt`).
  Needs SDK/NDK + `logo.png` -> icon-512; run `buildozer android debug` on Linux.
  Full terminal CLI inside APK is out of scope; APK is a Kivy demo launcher.

## Tests

```
python3 mlang/tests/smoke.py
```
