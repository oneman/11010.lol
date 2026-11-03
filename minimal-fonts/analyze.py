#!/usr/bin/env python3
"""Extract and characterize two minimal lowercase pixel alphabets.

Reads source/3x5alphabet.png (26 glyphs, fixed 3-wide cells + 1px gap) and
source/vscii_5x5_font26.png (26 glyphs, variable width up to 5, separated by
blank columns), measures each glyph, and writes:

  glyphs.json    the raw bitmaps ('#' = ink, '.' = paper)
  analysis.json  every measured feature, per font and per letter
  index.html     the interactive report (report_template.html + data)

Usage:  python3 analyze.py        (needs Pillow)
"""
import json
import os
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LETTERS = [chr(97 + i) for i in range(26)]
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


# ---------------------------------------------------------------- extraction
def load_bits(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    return [[1 if sum(im.getpixel((x, y))) < 384 else 0 for x in range(w)] for y in range(h)], w, h


def extract_3x5(path):
    g, w, h = load_bits(path)
    assert (w, h) == (104, 5), (w, h)
    return {c: ["".join("#" if g[y][4 * i + x] else "." for x in range(3)) for y in range(5)]
            for i, c in enumerate(LETTERS)}


def extract_by_blank_columns(path):
    g, w, h = load_bits(path)
    cols = [any(g[y][x] for y in range(h)) for x in range(w)]
    runs, x = [], 0
    while x < w:
        if cols[x]:
            s = x
            while x < w and cols[x]:
                x += 1
            runs.append((s, x))
        else:
            x += 1
    assert len(runs) == 26, runs
    return {c: ["".join("#" if g[y][x] else "." for x in range(s, e)) for y in range(h)]
            for c, (s, e) in zip(LETTERS, runs)}


# ---------------------------------------------------------------- measuring
def flood(start, ok):
    seen, stack = {start}, [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in DIRS.values():
            n = (r + dr, c + dc)
            if n not in seen and ok(n):
                seen.add(n)
                stack.append(n)
    return seen


def components(cells, ok):
    left, out = set(cells), []
    while left:
        comp = flood(next(iter(sorted(left))), lambda n: n in left and ok(n))
        left -= comp
        out.append(sorted(comp))
    return out


def analyze(rows):
    H, W = len(rows), len(rows[0])
    ink = {(r, c) for r in range(H) for c in range(W) if rows[r][c] == "#"}
    paper = {(r, c) for r in range(H) for c in range(W)} - ink
    isink = lambda p: p in ink

    top = min(r for r, _ in ink); bot = max(r for r, _ in ink)
    lef = min(c for _, c in ink); rig = max(c for _, c in ink)
    inbox = lambda p: top <= p[0] <= bot and lef <= p[1] <= rig

    # Holes (loops): paper not reachable from outside with 4-connected moves.
    outside = flood((-1, -1), lambda n: -1 <= n[0] <= H and -1 <= n[1] <= W and n not in ink)
    hole_cells = [p for p in paper if p not in outside]
    holes = components(hole_cells, lambda n: True)

    # Bays: open paper regions inside the bounding box, with the box sides they reach.
    bay_cells = [p for p in paper if inbox(p) and p not in hole_cells]
    bays = []
    for comp in components(bay_cells, lambda n: True):
        sides = []
        if any(r == top for r, _ in comp): sides.append("up")
        if any(r == bot for r, _ in comp): sides.append("down")
        if any(c == lef for _, c in comp): sides.append("left")
        if any(c == rig for _, c in comp): sides.append("right")
        kind = {1: "concave", 2: "corner"}.get(len(sides), "open")
        if len(sides) == 2 and set(sides) in ({"up", "down"}, {"left", "right"}):
            kind = "channel"
        bays.append({"cells": comp, "size": len(comp), "sides": sides, "kind": kind})

    # Slots: straight 1-wide notches. Start next to ink (the closed end), walk away
    # from it while the cell is open paper and both flanks are ink.
    slots = []
    for name, (dr, dc) in DIRS.items():
        fl = [(dc, dr), (-dc, -dr)]  # perpendicular offsets
        for p in sorted(paper):
            if p in hole_cells or (p[0] - dr, p[1] - dc) not in ink:
                continue
            cells, q = [], p
            while q in paper and q not in hole_cells and all(isink((q[0] + a, q[1] + b)) for a, b in fl):
                cells.append(q)
                q = (q[0] + dr, q[1] + dc)
            if cells and q not in ink:  # must actually open somewhere
                slots.append({"dir": name, "depth": len(cells), "cells": cells})

    # Diagonal (slanted) links: two ink pixels touching only at a corner.
    diag = []
    for (r, c) in sorted(ink):
        for dc in (-1, 1):
            n = (r + 1, c + dc)
            if n in ink and (r + 1, c) not in ink and (r, c + dc) not in ink:
                diag.append({"a": [r, c], "b": list(n), "lean": "/" if dc == -1 else "\\"})

    # A diagonal link that joins a horizontal run to a vertical run is a rounded
    # corner (o, s); anything else is a real slanted stroke (k, v, x, y, z).
    def orth_axes(p):
        ax = set()
        for name, (dr, dc) in DIRS.items():
            if (p[0] + dr, p[1] + dc) in ink:
                ax.add("v" if dr else "h")
        return ax
    for d in diag:
        A, B = orth_axes(tuple(d["a"])), orth_axes(tuple(d["b"]))
        d["corner"] = {frozenset(A), frozenset(B)} == {frozenset("h"), frozenset("v")}
    slants = [d for d in diag if not d["corner"]]

    # Pixel graph: orthogonal neighbours + pure diagonal links.
    adj = {p: set() for p in ink}
    for p in ink:
        for dr, dc in DIRS.values():
            n = (p[0] + dr, p[1] + dc)
            if n in ink:
                adj[p].add(n)
    for d in diag:
        a, b = tuple(d["a"]), tuple(d["b"])
        adj[a].add(b); adj[b].add(a)
    pieces = components(ink, lambda n: True)
    # merge pieces joined only diagonally
    parent = {p: p for p in ink}
    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]; p = parent[p]
        return p
    for p in ink:
        for n in adj[p]:
            parent[find(p)] = find(n)
    groups = Counter(find(p) for p in ink)
    deg = {p: len(adj[p]) for p in ink}
    odd_by_group = Counter(find(p) for p in ink if deg[p] % 2)
    pen_strokes = sum(max(1, odd_by_group[g] // 2) for g in groups)
    edges = sum(deg.values()) // 2
    blocks2x2 = sum(1 for (r, c) in ink if {(r, c + 1), (r + 1, c), (r + 1, c + 1)} <= ink)

    t = [row[lef:rig + 1] for row in rows[top:bot + 1]]
    mirror_lr = t == [row[::-1] for row in t]
    mirror_ud = t == t[::-1]
    rot180 = t == [row[::-1] for row in t[::-1]]

    two_slots = [s for s in slots if s["depth"] == 2]
    return {
        "rows": rows, "width": W, "bbox": [top, lef, bot, rig],
        "box_w": rig - lef + 1, "box_h": bot - top + 1,
        "ink": len(ink), "paper_in_box": (rig - lef + 1) * (bot - top + 1) - len(ink),
        "rows_used": [top, bot],
        "holes": [{"cells": h, "size": len(h)} for h in holes],
        "loops": len(holes),
        "bays": bays,
        "concave_bays": [b for b in bays if b["kind"] == "concave"],
        "slots": slots,
        "slot_dirs": sorted(s["dir"] for s in slots),
        "two_block": len(two_slots),
        "two_block_dirs": sorted(s["dir"] for s in two_slots),
        "diag": diag, "slant": len(slants) > 0, "slant_links": len(slants),
        "round_corners": len(diag) - len(slants),
        "lean": "".join(sorted({d["lean"] for d in slants})),
        "parts": len(groups),
        "endpoints": sum(1 for p in ink if deg[p] == 1),
        "junctions": sum(1 for p in ink if deg[p] >= 3),
        "isolated": sum(1 for p in ink if deg[p] == 0),
        "cycles": edges - len(ink) + len(groups),
        "pen_strokes": pen_strokes,
        "blocks2x2": blocks2x2,
        "mirror_lr": mirror_lr, "mirror_ud": mirror_ud, "rot180": rot180,
        "nodes": {"end": [list(p) for p in sorted(ink) if deg[p] == 1],
                  "junction": [list(p) for p in sorted(ink) if deg[p] >= 3]},
    }


def trim(rows):
    a = analyze(rows)
    t, l, b, r = a["bbox"]
    return tuple(row[l:r + 1] for row in rows[t:b + 1])


def relations(font):
    """Letters that are mirrors / rotations / identical shapes of each other."""
    shapes = {c: trim(font[c]) for c in LETTERS}
    ops = {
        "mirror (left-right)": lambda t: tuple(r[::-1] for r in t),
        "flip (up-down)": lambda t: tuple(t[::-1]),
        "rotate 180°": lambda t: tuple(r[::-1] for r in t[::-1]),
        "rotate 90°": lambda t: tuple("".join(t[len(t) - 1 - i][j] for i in range(len(t))) for j in range(len(t[0]))),
        "rotate 270°": lambda t: tuple("".join(t[i][len(t[0]) - 1 - j] for i in range(len(t))) for j in range(len(t[0]))),
    }
    out = []
    for i, a in enumerate(LETTERS):
        for b in LETTERS[i + 1:]:
            if shapes[a] == shapes[b]:
                out.append({"a": a, "b": b, "op": "same shape"})
            for name, f in ops.items():
                if f(shapes[a]) == shapes[b]:
                    out.append({"a": a, "b": b, "op": name})
    return out


# ------------------------------------------------- handwriting reference data
# Lowercase manuscript formation. Cues follow the common classroom wording
# (e.g. the W&M T/TAC manuscript formation chart); stroke counts are pen-down
# strokes. "continuous" = modern continuous-stroke manuscript (Zaner-Bloser
# 2008+, Handwriting Without Tears style); "ball-and-stick" = traditional
# manuscript where circles and sticks are separate strokes.
HAND = {
    "a": ("Around, down", 1, 2, "curve,line", True, False),
    "b": ("Down, up, around", 1, 2, "line,curve", True, False),
    "c": ("Around, stop", 1, 1, "curve", False, False),
    "d": ("Around, up, down", 1, 2, "curve,line", True, False),
    "e": ("Across, around, stop", 1, 1, "line,curve", True, False),
    "f": ("Curve, down, cross", 2, 2, "curve,line", False, False),
    "g": ("Around, down, hook", 1, 2, "curve,line", True, False),
    "h": ("Down, hump", 1, 1, "line,curve", False, False),
    "i": ("Down, dot", 2, 2, "line,dot", False, False),
    "j": ("Down, hook, dot", 2, 2, "line,curve,dot", False, False),
    "k": ("Down, slant in, slant out", 2, 2, "line,slant", False, True),
    "l": ("Down", 1, 1, "line", False, False),
    "m": ("Down, hump, hump", 1, 1, "line,curve", False, False),
    "n": ("Down, hump", 1, 1, "line,curve", False, False),
    "o": ("Around, close", 1, 1, "curve", True, False),
    "p": ("Down, up, around", 1, 2, "line,curve", True, False),
    "q": ("Around, up, down", 1, 2, "curve,line", True, False),
    "r": ("Down, up, over", 1, 1, "line,curve", False, False),
    "s": ("Curve, slant, curve", 1, 1, "curve", False, False),
    "t": ("Down, cross", 2, 2, "line", False, False),
    "u": ("Down, curve up, down", 1, 1, "line,curve", False, False),
    "v": ("Slant down, slant up", 1, 1, "slant", False, True),
    "w": ("Slant down, up, down, up", 1, 1, "slant", False, True),
    "x": ("Slant right, lift, slant left", 2, 2, "slant", False, True),
    "y": ("Slant right, lift, slant left", 2, 2, "slant", False, True),
    "z": ("Across, slant, across", 1, 1, "line,slant", False, True),
}


def main():
    fonts = {
        "3x5": extract_3x5(os.path.join(HERE, "source", "3x5alphabet.png")),
        "5x5": extract_by_blank_columns(os.path.join(HERE, "source", "vscii_5x5_font26.png")),
    }
    with open(os.path.join(HERE, "glyphs.json"), "w") as f:
        json.dump(fonts, f, indent=1)

    data = {"letters": LETTERS, "fonts": {}, "relations": {}, "hand": {}}
    for name, font in fonts.items():
        data["fonts"][name] = {c: analyze(font[c]) for c in LETTERS}
        data["relations"][name] = relations(font)
    for c, (cue, cont, ball, parts, loop, slant) in HAND.items():
        data["hand"][c] = {"cue": cue, "continuous": cont, "ball": ball,
                           "parts": parts.split(","), "loop": loop, "slant": slant}
    data["same_in_both"] = [c for c in LETTERS if trim(fonts["3x5"][c]) == trim(fonts["5x5"][c])]

    with open(os.path.join(HERE, "analysis.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"))

    tpl = open(os.path.join(HERE, "report_template.html")).read()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    with open(os.path.join(HERE, "index.html"), "w") as f:
        f.write(html)

    # console summary
    for name in fonts:
        F = data["fonts"][name]
        print(f"== {name}")
        for c in LETTERS:
            a = F[c]
            print(f"{c} ink={a['ink']:2d} box={a['box_w']}x{a['box_h']} loops={a['loops']} "
                  f"slant={a['lean'] or '-':2s} slots={','.join(f'{s['dir']}{s['depth']}' for s in a['slots']) or '-':24s} "
                  f"bays={[(b['kind'], b['sides'], b['size']) for b in a['bays']]} "
                  f"pen={a['pen_strokes']} ends={a['endpoints']} junc={a['junctions']} 2x2={a['blocks2x2']}")
        print("relations:", [(r['a'], r['b'], r['op']) for r in data["relations"][name]])
    print("same in both:", data["same_in_both"])


if __name__ == "__main__":
    main()
