# Minimal alphabet atlas

A study of two near-minimal lowercase pixel alphabets: a fixed 3×5 font and a
variable-width 5×5 font (VSCII). Open `index.html` in a browser for the
interactive report.

- `source/` the two original PNGs
- `analyze.py` extracts the glyphs from the PNGs and measures loops, slants,
  notch concavities (depth and opening direction), symmetry, shape families
  and pixel stroke counts, and compares them with classroom manuscript
  stroke instructions
- `glyphs.json` extracted bitmaps (`#` ink, `.` paper)
- `analysis.json` every measured feature
- `report_template.html` page template; `analyze.py` writes `index.html` from it

Rebuild: `python3 analyze.py` (needs Pillow).
