#!/usr/bin/env python3
"""
Source-sync checker for Obsidify vaults.

Answers three questions about an existing vault:
  - Which notes were planned but never written?   (interrupted run)
  - Which notes has the user edited by hand?      (do not overwrite these)
  - What changed in the source since the vault was built?  (new edition)

Commands
--------
  sync_source.py init   <vault> --pdf <pdf> [--offset N]
      Record a manifest: which note came from which part of the source, hashes of both.
      Run this at the end of every build, and again after every applied update.

  sync_source.py status <vault>
      Notes planned in the contents file but missing, and notes edited since the build.
      No PDF needed.

  sync_source.py diff   <vault> --pdf <new-or-same-pdf>
      Compare the stored source text against the given PDF and report, per note:
      UNCHANGED / CHANGED / ANCHOR-LOST / USER-EDITED, plus labels added or removed
      (e.g. an inserted "Definition 3.4") and sections with no note yet.

  sync_source.py merge  <vault> <note> [--pdf <new.pdf>]
      For one note, print exactly which lines the user added or removed since it was
      generated, and what the source did to the same section. Use this whenever a note
      is both user-edited and source-changed, so the merge is mechanical rather than
      guesswork.

Add --json for machine-readable output. Exit code 0 = nothing to do, 1 = work to do.

Anchors are content strings ("Definition 3.1"), never line numbers, because line
numbers shift the moment an edition changes. Requires poppler (pdftotext, pdfinfo).
"""

"""
NOTICE:

OBSIDIFY - An Agentic Skillset that turns lecture scripts into knowledge graphs
Copyright (C) 2026  Bela Keppler

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

MANIFEST_DIR = "_obsidify"
MANIFEST = "manifest.json"
RAW_SNAPSHOT = "source-text.txt"
SNAPSHOT_DIR = "snapshots"
SKIP_DIRS = {"_obsidify", "_archive", "_scratch", ".git", ".obsidian", "assets"}

# "Definition 3.1", "Satz 2.14", "Theorem 4.2.1" — a word followed by a dotted number.
LABEL_RE = re.compile(r"\b([A-Z][A-Za-zÄÖÜäöüß]{2,})\s+(\d+(?:\.\d+)+)")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Command failed: {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout


def pdf_text(pdf):
    if not os.path.exists(pdf):
        sys.exit(f"PDF not found: {pdf}")
    return run(["pdftotext", "-layout", pdf, "-"])


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def normalize(text):
    """Whitespace-collapsed, page-furniture-free view of a text slice.

    Reflowed lines and shifted page numbers are not content changes; comparing raw
    slices directly would flag every note in the vault on any reprint.
    """
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.isdigit():
            continue
        out.append(re.sub(r"\s+", " ", s))
    return "\n".join(out)


def md_files(vault):
    found = []
    for root, dirs, names in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in sorted(names):
            if n.endswith(".md"):
                found.append(os.path.relpath(os.path.join(root, n), vault))
    return sorted(found)


def read(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8") as fh:
        return fh.read()


def note_anchors(text):
    """Content anchors for a note: its numbered labels, in order, deduplicated."""
    seen, anchors = set(), []
    for line in text.splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if not m:
            continue
        for lm in LABEL_RE.finditer(m.group(1)):
            label = f"{lm.group(1)} {lm.group(2)}"
            if label not in seen:
                seen.add(label)
                anchors.append(label)
    return anchors


def note_title(text):
    m = re.search(r"^#\s+(.*)$", text, re.M)
    return m.group(1).strip() if m else None


def frontmatter_pages(text):
    m = re.search(r"^source:.*?(\d+)\s*[-–—]\s*(\d+)", text, re.M)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    m = re.search(r"^source:.*?(\d+)\s*$", text, re.M)
    return [int(m.group(1)), int(m.group(1))] if m else None


def locate(raw, anchor, start=0):
    """First occurrence of an anchor at or after `start`, else -1."""
    idx = raw.find(anchor, start)
    return idx


def slice_for(raw, anchors, next_pos):
    """Text from a note's first anchor up to where the following note begins."""
    if not anchors:
        return None
    first = locate(raw, anchors[0])
    if first < 0:
        return None
    end = next_pos if (next_pos and next_pos > first) else len(raw)
    return raw[first:end]


def manifest_path(vault):
    return os.path.join(vault, MANIFEST_DIR, MANIFEST)


def snapshot_path(vault, rel):
    """Where the as-generated copy of a note lives."""
    return os.path.join(vault, MANIFEST_DIR, SNAPSHOT_DIR, rel)


def write_snapshot(vault, rel):
    dst = snapshot_path(vault, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(os.path.join(vault, rel), dst)


def read_snapshot(vault, rel):
    p = snapshot_path(vault, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def user_delta(vault, rel):
    """(added, removed) line counts between the generated note and the current one.

    Returns None when no snapshot exists (vault indexed before snapshots, or the
    note is gone), so callers can fall back to 'edited somewhere'.
    """
    base = read_snapshot(vault, rel)
    full = os.path.join(vault, rel)
    if base is None or not os.path.exists(full):
        return None
    mine = read(vault, rel)
    added = removed = 0
    for line in difflib.unified_diff(base.splitlines(), mine.splitlines(), n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


def delta_tag(vault, rel):
    d = user_delta(vault, rel)
    return f"+{d[0]}/-{d[1]} lines" if d else "no snapshot — extent unknown"


def load_manifest(vault):
    p = manifest_path(vault)
    if not os.path.exists(p):
        sys.exit(f"No manifest at {p}.\n"
                 "This vault has never been indexed — run 'sync_source.py init' first "
                 "(it only reads the vault and the PDF; it changes no notes).")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def contents_file(vault):
    """The vault's index note, whatever the source language called it."""
    candidates = [f for f in md_files(vault) if os.sep not in f]
    for name in ("Contents.md", "Inhaltsverzeichnis.md", "Index.md", "Sommaire.md"):
        if name in candidates:
            return name
    # otherwise: the root note with the most wikilinks
    best, best_n = None, 0
    for c in candidates:
        n = len(re.findall(r"(?<!\!)\[\[", read(vault, c)))
        if n > best_n:
            best, best_n = c, n
    return best


def planned_topics(vault):
    """Checkbox topics listed in the contents note -> their link targets."""
    cf = contents_file(vault)
    if not cf:
        return cf, []
    targets = []
    for m in re.finditer(r"-\s*\[[ xX]\]\s*.*?(?<!\!)\[\[([^\]]+)\]\]", read(vault, cf)):
        targets.append(m.group(1).split("|")[0].split("#")[0].strip())
    return cf, targets


def existing_basenames(vault):
    return {os.path.splitext(os.path.basename(f))[0] for f in md_files(vault)}


# --------------------------------------------------------------------------- init

def cmd_init(args):
    vault, pdf = args.vault, args.pdf
    raw = pdf_text(pdf)
    files = md_files(vault)
    if not files:
        sys.exit(f"No .md files under {vault!r} — is that the right folder?")

    # Order notes by where their first anchor appears in the source, so each note's
    # slice can end where the next one starts.
    entries = []
    for rel in files:
        text = read(vault, rel)
        anchors = note_anchors(text)
        pos = locate(raw, anchors[0]) if anchors else -1
        entries.append({"path": rel, "anchors": anchors, "pos": pos,
                        "title": note_title(text), "pages": frontmatter_pages(text),
                        "note_hash": file_sha(os.path.join(vault, rel))})
    ordered = sorted([e for e in entries if e["pos"] >= 0], key=lambda e: e["pos"])
    for i, e in enumerate(ordered):
        nxt = ordered[i + 1]["pos"] if i + 1 < len(ordered) else None
        sl = slice_for(raw, e["anchors"], nxt)
        e["source_hash"] = sha(normalize(sl)) if sl else None

    notes = []
    for e in entries:
        notes.append({"path": e["path"], "anchors": e["anchors"], "title": e["title"],
                      "pages": e["pages"], "note_hash": e["note_hash"],
                      "source_hash": e.get("source_hash")})

    outdir = os.path.join(vault, MANIFEST_DIR)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, RAW_SNAPSHOT), "w", encoding="utf-8") as fh:
        fh.write(raw)

    # Keep a copy of every note as generated. A hash proves a file was touched;
    # only the text can tell you which lines the user added.
    snapdir = os.path.join(outdir, SNAPSHOT_DIR)
    if os.path.exists(snapdir):
        shutil.rmtree(snapdir)
    for rel in files:
        write_snapshot(vault, rel)

    manifest = {
        "schema": 1,
        "captured": date.today().isoformat(),
        "source": {"path": os.path.relpath(pdf, vault) if os.path.isabs(pdf) else pdf,
                   "sha256": file_sha(pdf),
                   "offset": args.offset,
                   "text_snapshot": f"{MANIFEST_DIR}/{RAW_SNAPSHOT}"},
        "notes": notes,
    }
    with open(manifest_path(vault), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    anchored = sum(1 for n in notes if n["anchors"])
    print(f"Manifest written: {manifest_path(vault)}")
    print(f"  {len(notes)} notes indexed, {anchored} with source anchors, "
          f"{len(notes) - anchored} without (hubs/summaries — reviewed by hand on update).")
    print(f"  Source text snapshot: {MANIFEST_DIR}/{RAW_SNAPSHOT}")
    print(f"  Note snapshots:       {MANIFEST_DIR}/{SNAPSHOT_DIR}/ ({len(files)} files)")
    return 0


# ------------------------------------------------------------------------- status

def cmd_status(args):
    vault = args.vault
    man = load_manifest(vault)
    have = existing_basenames(vault)
    cf, targets = planned_topics(vault)
    missing = [t for t in targets if t.split("/")[-1] not in have]

    edited, gone = [], []
    for n in man["notes"]:
        full = os.path.join(vault, n["path"])
        if not os.path.exists(full):
            gone.append(n["path"])
        elif n.get("note_hash") and file_sha(full) != n["note_hash"]:
            edited.append(n["path"])

    if args.json:
        print(json.dumps({"missing_notes": missing, "user_edited": edited,
                          "deleted_since_build": gone}, indent=2, ensure_ascii=False))
    else:
        print(f"Vault: {vault}   (indexed {man['captured']})")
        print("=" * 60)
        print(f"Planned but not written ({len(missing)}):"
              if missing else "Planned but not written: NONE ✓")
        for t in missing:
            print(f"  [[{t}]]   (listed in {cf})")
        print(f"Edited by hand since the build ({len(edited)}):"
              if edited else "Edited by hand since the build: NONE ✓")
        for t in edited:
            print(f"  {t}   ({delta_tag(vault, t)})")
        if edited:
            print("  -> Do not regenerate these wholesale; the changes are the user's.")
            print("  -> See the exact lines with: sync_source.py merge <vault> <path>")
        if gone:
            print(f"Indexed but no longer present ({len(gone)}):")
            for t in gone:
                print(f"  {t}")
    return 1 if (missing or edited or gone) else 0


# --------------------------------------------------------------------------- diff

def cmd_diff(args):
    vault = args.vault
    man = load_manifest(vault)
    new_raw = pdf_text(args.pdf)
    snap = os.path.join(vault, MANIFEST_DIR, RAW_SNAPSHOT)
    old_raw = open(snap, encoding="utf-8").read() if os.path.exists(snap) else ""

    same_file = man["source"].get("sha256") == file_sha(args.pdf)

    # Note-level verdicts.
    anchored = [n for n in man["notes"] if n["anchors"]]
    positions = []
    for n in anchored:
        positions.append((locate(new_raw, n["anchors"][0]), n))
    positions.sort(key=lambda t: (t[0] < 0, t[0]))
    order = [p for p in positions if p[0] >= 0]

    verdicts = {"UNCHANGED": [], "CHANGED": [], "ANCHOR-LOST": [],
                "USER-EDITED": [], "NO-ANCHOR": []}
    for n in man["notes"]:
        full = os.path.join(vault, n["path"])
        user_edited = (os.path.exists(full) and n.get("note_hash")
                       and file_sha(full) != n["note_hash"])
        if not n["anchors"]:
            verdicts["NO-ANCHOR"].append(n["path"])
            continue
        pos = locate(new_raw, n["anchors"][0])
        if pos < 0:
            verdicts["ANCHOR-LOST"].append(f"{n['path']}  (anchor '{n['anchors'][0]}')")
            continue
        idx = next((i for i, (p, e) in enumerate(order) if e is n), None)
        nxt = order[idx + 1][0] if idx is not None and idx + 1 < len(order) else None
        sl = slice_for(new_raw, n["anchors"], nxt)
        new_hash = sha(normalize(sl)) if sl else None
        changed = n.get("source_hash") and new_hash and new_hash != n["source_hash"]
        if changed and user_edited:
            verdicts["USER-EDITED"].append(
                f"{n['path']}  [{delta_tag(vault, n['path'])}]  (source ALSO changed — MERGE)")
        elif changed:
            verdicts["CHANGED"].append(n["path"])
        elif user_edited:
            verdicts["USER-EDITED"].append(
                f"{n['path']}  [{delta_tag(vault, n['path'])}]  (source unchanged — leave alone)")
        else:
            verdicts["UNCHANGED"].append(n["path"])

    # Label-level structural diff.
    def labels(text):
        return {f"{m.group(1)} {m.group(2)}" for m in LABEL_RE.finditer(text)}

    old_labels, new_labels = labels(old_raw), labels(new_raw)
    added = sorted(new_labels - old_labels) if old_raw else []
    removed = sorted(old_labels - new_labels) if old_raw else []
    claimed = {a for n in man["notes"] for a in n["anchors"]}
    unclaimed = sorted(l for l in (new_labels - claimed))

    if args.json:
        print(json.dumps({"same_source_file": same_file, "verdicts": verdicts,
                          "labels_added": added, "labels_removed": removed,
                          "labels_without_note": unclaimed},
                         indent=2, ensure_ascii=False))
        return 0 if same_file and not (verdicts["CHANGED"] or added or removed) else 1

    print(f"Vault: {vault}")
    print(f"Indexed against: {man['source']['path']}  ({man['captured']})")
    print(f"Comparing with:  {args.pdf}")
    if same_file:
        print("The PDF is byte-identical to the indexed source — no edition change.")
    print("=" * 60)
    for k in ("CHANGED", "ANCHOR-LOST", "USER-EDITED", "NO-ANCHOR", "UNCHANGED"):
        v = verdicts[k]
        if k == "UNCHANGED":
            print(f"UNCHANGED:    {len(v)} note(s) — skip these entirely.")
            continue
        if not v:
            continue
        print(f"{k}:  {len(v)} note(s)")
        for item in v:
            print(f"  {item}")
    if added:
        print(f"\nLabels new in this edition ({len(added)}):")
        for l in added:
            print(f"  + {l}")
    if removed:
        print(f"\nLabels gone from this edition ({len(removed)}):")
        for l in removed:
            print(f"  - {l}   (archive the note, don't delete it)")
    if unclaimed:
        print(f"\nLabels in the source with no note covering them ({len(unclaimed)}):")
        for l in unclaimed[:40]:
            print(f"  ? {l}")
        if len(unclaimed) > 40:
            print(f"  … and {len(unclaimed) - 40} more")
    if added or removed:
        print("\nNumbering may have cascaded: an inserted definition shifts every later")
        print("number, and headings are embed targets. Re-run check_links.py afterwards.")
    return 0 if same_file and not (verdicts["CHANGED"] or added or removed) else 1


# -------------------------------------------------------------------------- merge

def cmd_merge(args):
    """Three-way view for one note: generated baseline vs the user's copy vs the source."""
    vault, rel = args.vault, args.note
    man = load_manifest(vault)
    entry = next((n for n in man["notes"] if n["path"] == rel), None)
    if entry is None:
        matches = [n for n in man["notes"] if n["path"].endswith(rel)
                   or os.path.basename(n["path"]) == rel]
        if len(matches) == 1:
            entry, rel = matches[0], matches[0]["path"]
        elif len(matches) > 1:
            sys.exit("Ambiguous note name; use the full relative path:\n  " +
                     "\n  ".join(m["path"] for m in matches))
        else:
            sys.exit(f"{rel!r} is not in the manifest. Re-run 'init' if it is new.")

    base = read_snapshot(vault, rel)
    full = os.path.join(vault, rel)
    if not os.path.exists(full):
        sys.exit(f"Note missing from the vault: {rel}")
    mine = read(vault, rel)

    print(f"Note: {rel}")
    print("=" * 70)

    # 1) What the user did to the generated note.
    if base is None:
        print("\n[1] USER CHANGES: no snapshot for this note.")
        print("    The vault was indexed before snapshots existed, so the user's edits")
        print("    can only be identified by reading. Re-run 'init' after this update")
        print("    to enable line-level merges next time.")
        user_patch = []
    elif base == mine:
        print("\n[1] USER CHANGES: none — the note is exactly as generated.")
        user_patch = []
    else:
        user_patch = list(difflib.unified_diff(
            base.splitlines(), mine.splitlines(),
            fromfile="generated", tofile="current (user's)", lineterm="", n=args.context))
        added = sum(1 for l in user_patch if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in user_patch if l.startswith("-") and not l.startswith("---"))
        print(f"\n[1] USER CHANGES to preserve  (+{added}/-{removed} lines):")
        print("-" * 70)
        for l in user_patch:
            print("   " + l)

    # 2) What the source did, if a PDF was supplied.
    if args.pdf:
        snap = os.path.join(vault, MANIFEST_DIR, RAW_SNAPSHOT)
        old_raw = open(snap, encoding="utf-8").read() if os.path.exists(snap) else ""
        new_raw = pdf_text(args.pdf)

        def slice_in(raw):
            if not entry["anchors"]:
                return None
            others = []
            for n in man["notes"]:
                if n is entry or not n["anchors"]:
                    continue
                p = locate(raw, n["anchors"][0])
                if p >= 0:
                    others.append(p)
            first = locate(raw, entry["anchors"][0])
            if first < 0:
                return None
            after = [p for p in others if p > first]
            return raw[first:min(after)] if after else raw[first:]

        old_slice, new_slice = slice_in(old_raw), slice_in(new_raw)
        print(f"\n[2] SOURCE CHANGES  ({man['source']['path']} -> {args.pdf}):")
        print("-" * 70)
        if new_slice is None:
            print("   Anchor not found in the new PDF — the section was renamed,")
            print("   renumbered, or removed. Check the pages by eye before deciding.")
        elif old_slice is None:
            print("   No baseline slice; treat the section as new material.")
        else:
            sd = list(difflib.unified_diff(
                normalize(old_slice).splitlines(), normalize(new_slice).splitlines(),
                fromfile="source (indexed)", tofile="source (new)",
                lineterm="", n=args.context))
            if sd:
                for l in sd:
                    print("   " + l)
            else:
                print("   None — this note's section is unchanged in the new edition.")

    print("\n" + "=" * 70)
    if user_patch and args.pdf:
        print("Merge procedure: rewrite the source-derived parts from the new PDF pages")
        print("(verifying visually), then re-apply every '+' line from [1] verbatim.")
        print("Never drop a user line silently — if one no longer fits the updated text,")
        print("keep it and flag it to the user rather than deciding for them.")
    elif user_patch:
        print("Pass --pdf <new.pdf> to see what the source did to this same section.")
    return 0


def main():
    # Output is routinely piped to head/grep; don't traceback when the reader exits.
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    for tool in ("pdftotext", "pdfinfo"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            sys.exit(f"'{tool}' not found. Install poppler.")
    p = argparse.ArgumentParser(description="Check an Obsidify vault against its source.",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="index a vault against its source PDF")
    i.add_argument("vault"); i.add_argument("--pdf", required=True)
    i.add_argument("--offset", type=int, default=0,
                   help="PDF page = printed page + offset")
    i.set_defaults(func=cmd_init)

    s = sub.add_parser("status", help="missing notes and hand-edited notes")
    s.add_argument("vault"); s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    d = sub.add_parser("diff", help="compare the vault against a new source edition")
    d.add_argument("vault"); d.add_argument("--pdf", required=True)
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_diff)

    m = sub.add_parser("merge", help="three-way view of one note before merging")
    m.add_argument("vault")
    m.add_argument("note", help="note path relative to the vault (or just its filename)")
    m.add_argument("--pdf", help="new edition, to also show what the source changed")
    m.add_argument("--context", type=int, default=3, help="diff context lines")
    m.set_defaults(func=cmd_merge)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
