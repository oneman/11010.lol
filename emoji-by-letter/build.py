#!/usr/bin/env python3
"""Group every Unicode emoji by the first letter of its CLDR short name.

Reads emoji-test.txt (Unicode's official emoji list, UTS #51) and keeps the
fully-qualified entries. Each emoji is filed under the first letter of its
short name (accents folded, so "piñata" is under p); names that start with a
digit ("1st place medal") go in a "#" group. Within a letter, emoji are sorted
alphabetically by name.

Writes:
  emoji.json   [{"e", "name", "v", "tone", "group", "letter"}, ...]
  index.html   the page (template.html + data)

Usage:  python3 build.py
"""
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TONES = {0x1F3FB, 0x1F3FC, 0x1F3FD, 0x1F3FE, 0x1F3FF}
LINE = re.compile(r"^([0-9A-F ]+?)\s*;\s*fully-qualified\s*#\s*(\S+)\s+E([\d.]+)\s+(.+)$")


def letter_of(name):
    first = unicodedata.normalize("NFKD", name)[0].lower()
    return first if "a" <= first <= "z" else "#"


def sort_key(name):
    folded = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return (folded.casefold(), name)


def main():
    with open(os.path.join(HERE, "emoji-test.txt"), encoding="utf-8") as f:
        text = f.read()
    version = re.search(r"^# Version: (\S+)", text, re.M).group(1)
    date = re.search(r"^# Date: (\d{4}-\d\d-\d\d)", text, re.M).group(1)

    rows, group = [], ""
    for line in text.splitlines():
        if line.startswith("# group:"):
            group = line.split(":", 1)[1].strip()
            continue
        m = LINE.match(line)
        if not m:
            continue
        cps = [int(c, 16) for c in m.group(1).split()]
        name = m.group(4).strip()
        rows.append({
            "e": "".join(chr(c) for c in cps),
            "name": name,
            "v": m.group(3),
            "tone": any(c in TONES for c in cps),
            "group": group,
            "letter": letter_of(name),
        })

    rows.sort(key=lambda r: (r["letter"] == "#", r["letter"], sort_key(r["name"])))

    with open(os.path.join(HERE, "emoji.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))

    compact = [[r["e"], r["name"], r["v"], 1 if r["tone"] else 0] for r in rows]
    meta = {"version": version, "date": date, "total": len(rows),
            "base": sum(1 for r in rows if not r["tone"])}
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*DATA*/null", json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("/*META*/null", json.dumps(meta))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Emoji {version}: {meta['total']} emoji ({meta['base']} without skin-tone variants)")


if __name__ == "__main__":
    main()
