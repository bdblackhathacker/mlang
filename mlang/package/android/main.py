"""Android entry (Buildozer/p4a). Runs an MLang demo compile+run, shows output.
Full interactive CLI inside APK needs a terminal Activity; this proves the
toolchain path. Linux CLI (mlang/cli.py) stays primary."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
import mlang2
DEMO = 'let total = 0;\nfor i in range(3) { total = total + i; }\nprint total;\n'
def main():
    try:
        from kivy.app import App
        from kivy.uix.label import Label
        toks = mlang2.lex(DEMO, "demo")
        gl, f, c = mlang2.P(toks, "demo").parse()
        code = mlang2.gen(gl, f, c)
        class M(App):
            def build(self): return Label(text="MLang OK\n" + code[:2000])
        M().run()
    except ImportError:
        print("kivy not installed (normal outside buildozer). Demo compiles:")
        toks = mlang2.lex(DEMO, "demo")
        print(mlang2.gen(*mlang2.P(toks, "demo").parse()[0:1], *mlang2.P(toks, "demo").parse()[1:])[:500])
if __name__ == "__main__":
    main()
