#!/usr/bin/env python3
"""Build theme.css for the Dark Lore theme.

    src/theme.css  +  the four fonts, embedded  ->  theme.css

The fonts are fetched once from github.com/google/fonts into .fonts/ (which git
ignores) and checked against the hashes below. Each is embedded complete and
unmodified: wrapped as WOFF 1.0, which is lossless, and proved identical to the
original, table for table, before anything is written. No subsetting, no
renaming, no changes to the fonts' own data.

    pip install fonttools zopfli
    python build.py
"""
import base64, hashlib, io, json, pathlib, sys, urllib.request

from fontTools.ttLib import TTFont, sfnt

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / ".fonts"
RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# family as the CSS names it, weight, style, path in google/fonts, sha256 of the original
FACES = [
    ("IM Fell English",   400, "normal", "imfellenglish/IMFeENrm28P.ttf",
     "fe9705bbde51af802719246d4608d08d37bde956ab99d9a590da996a5221a24c"),
    ("IM Fell English",   400, "italic", "imfellenglish/IMFeENit28P.ttf",
     "47cd75dce54b1f2e0831359d22d5e688f519d68ae45706b664fd310fd0e3ccf7"),
    ("Cinzel Decorative", 700, "normal", "cinzeldecorative/CinzelDecorative-Bold.ttf",
     "e854e68a388aa50d742a4415c1ae5c17a617ef7956c95a70021d0a4a44f20518"),
    ("VT323",             400, "normal", "vt323/VT323-Regular.ttf",
     "cf4de751ada78ceac033dbe16a687742939995b77bc2a052ae17a4957958594d"),
]


def fetch(rel: str, want: str) -> pathlib.Path:
    """The original font file, from the cache or from google/fonts, hash checked."""
    path = CACHE / rel
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"{RAW}/{rel}", timeout=60) as r:
            path.write_bytes(r.read())
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != want:
        sys.exit(f"{rel}: sha256 {got} is not the expected {want}")
    return path


def to_woff(ttf_path: pathlib.Path) -> bytes:
    """Wrap a TTF as WOFF 1.0 and prove nothing but the wrapper changed."""
    sfnt.USE_ZOPFLI = True
    # No table is opened, so each one is copied as it stands. The two switches
    # stop fontTools from re-stamping the date or re-measuring the glyphs.
    font = TTFont(ttf_path, recalcBBoxes=False, recalcTimestamp=False)
    font.flavor = "woff"
    buf = io.BytesIO()
    font.save(buf, reorderTables=False)
    woff = buf.getvalue()

    original, back = TTFont(ttf_path), TTFont(io.BytesIO(woff))
    tags = sorted(original.reader.keys())
    if tags != sorted(back.reader.keys()):
        sys.exit(f"{ttf_path.name}: the table list changed")
    for tag in tags:
        if original.reader[tag] != back.reader[tag]:
            sys.exit(f"{ttf_path.name}: table {tag} changed")
    return woff


def main() -> None:
    css = (ROOT / "src" / "theme.css").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    ofl = (ROOT / "OFL.txt").read_text(encoding="utf-8").strip()
    if "*/" in ofl:
        sys.exit("OFL.txt would close the CSS comment early")

    faces, report = [], []
    for family, weight, style, rel, want in FACES:
        path = fetch(rel, want)
        woff = to_woff(path)
        b64 = base64.b64encode(woff).decode("ascii")
        faces.append(
            "@font-face {\n"
            f"  font-family: '{family}';\n"
            f"  font-style: {style};\n"
            f"  font-weight: {weight};\n"
            f"  src: url(data:font/woff;base64,{b64}) format('woff');\n"
            "}"
        )
        report.append(f"  {path.name}: {path.stat().st_size} bytes, woff {len(woff)}, identical")

    licence = (
        "/* ════════════════════════════════════════════════════════════════════\n"
        "   THE FONTS, EMBEDDED\n"
        "   Complete and unmodified, wrapped as WOFF so the theme makes no\n"
        "   network calls. Their licence follows, as it stands in OFL.txt.\n\n"
        + "\n".join("   " + line if line else "" for line in ofl.splitlines())
        + "\n   ════════════════════════════════════════════════════════════════════ */\n"
    )

    css = css.replace("{{VERSION}}", manifest["version"])
    built = css.rstrip() + "\n\n\n" + licence + "\n" + "\n\n".join(faces) + "\n"
    (ROOT / "theme.css").write_text(built, encoding="utf-8", newline="\n")

    print(f"theme.css {manifest['version']}: {len(built.encode('utf-8'))} bytes")
    print("\n".join(report))


if __name__ == "__main__":
    main()
