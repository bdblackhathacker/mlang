"""Android entry (Buildozer/p4a). Runs an MLang demo compile+run, shows output.
Full interactive CLI inside APK needs a terminal Activity; this proves the
toolchain path. Linux CLI (mlang/cli.py) stays primary."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
import mlang2
DEMO = 'let total = 0;\nfor i in range(3) { total = total + i; }\nprint total;\n'
def main():
    toks = mlang2.lex(DEMO, "demo")
    gl, funcs, classes, ifaces = mlang2.P(toks, "demo").parse()
    code = mlang2.gen(gl, funcs, classes, ifaces)
    try:
        from kivy.app import App
        from kivy.uix.label import Label
        class M(App):
            def build(self): return Label(text="MLang OK\n" + code[:2000])
        M().run()
    except ImportError:
        print("kivy not installed (normal outside buildozer). Demo C output:")
        print(code[:500])
if __name__ == "__main__":
    main()
