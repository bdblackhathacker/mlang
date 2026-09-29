#!/usr/bin/env python3
"""Make icon.ico (Windows) from the MLANG logo PNG.
Steps:
  1. Save the MLANG logo from chat as mlang/package/assets/logo.png
  2. python3 mlang/package/assets/make_icon.py
Produces icon.ico (256,128,64,48,32,16) + icon-192.png / icon-512.png (Android).
Needs: pip install pillow
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "logo.png")
ICO = os.path.join(HERE, "icon.ico")
try:
    from PIL import Image
except ImportError:
    print("install pillow first: pip install pillow"); raise SystemExit(1)
if not os.path.exists(SRC):
    print(f"missing {SRC}: save the MLANG logo image as logo.png first"); raise SystemExit(1)
img = Image.open(SRC).convert("RGBA")
img.save(ICO, sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
img.resize((192,192)).save(os.path.join(HERE,"icon-192.png"))
img.resize((512,512)).save(os.path.join(HERE,"icon-512.png"))
print(f"wrote {ICO} + icon-192/512.png")
