# Emoji by letter

Every fully-qualified Unicode emoji, filed under the first letter of its CLDR
short name (a–z, plus # for names that start with a digit) and sorted
alphabetically within each letter. Open `index.html`.

- `emoji-test.txt` – Unicode's official emoji list (UTS #51), Emoji 18.0
- `build.py` – parses it and writes `emoji.json` and `index.html` from `template.html`

Skin-tone variants are hidden by default; a checkbox on the page shows them.
Q is the only letter with no emoji.
