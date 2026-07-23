#!/usr/bin/env python3
"""
Vault-wide wikilink & section-embed checker for Obsidify vaults.

Usage:  python3 check_links.py <vault-directory> [--strict]

Checks:
  1. Every [[wikilink]] (alias |, section #, folder/path all handled) resolves to an
     existing target — filename, frontmatter alias, or relative path.
  2. Every ![[File#Heading]] section embed: does the file exist AND the heading match?
  3. Duplicate basenames across folders — Obsidian resolves [[Name]] ambiguously
     when two files share a name. (warning)
  4. Orphan notes — nothing in the vault links to them. (warning)

Exit code 0 = all references resolve, 1 = problems found.
With --strict, warnings (3 and 4) also cause exit code 1.
"""
import os, re, sys, glob

# Vault machinery, not notes. Snapshots in particular are copies — scanning them
# double-counts every note and reports duplicate/unresolved links that don't exist.
SKIP_DIRS = {"_obsidify", "_archive", "_scratch", ".git", ".obsidian", ".trash"}


def main(root=".", strict=False):
    files = [f for f in glob.glob(os.path.join(root, "**/*.md"), recursive=True)
             if not (SKIP_DIRS & set(f.split(os.sep)))]
    if not files:
        print(f"No .md files found in {root!r}."); return 1

    names = set()        # filenames (without .md) + aliases
    paths = set()        # relative paths without .md (for [[Folder/File]])
    headings = {}        # filename -> {headings}
    basename_files = {}  # filename -> [relative paths]
    content = {}

    for f in files:
        txt = open(f, encoding="utf-8").read()
        content[f] = txt
        base = os.path.splitext(os.path.basename(f))[0]
        names.add(base)
        rel = os.path.splitext(os.path.relpath(f, root))[0].replace(os.sep, "/")
        paths.add(rel)
        basename_files.setdefault(base, []).append(rel)
        hs = set()
        for line in txt.splitlines():
            m = re.match(r"#{1,6}\s+(.*)", line)
            if m:
                hs.add(m.group(1).strip())
        headings[base] = hs
        # frontmatter aliases
        fm = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
        if fm:
            am = re.search(r"aliases:\s*\[(.*?)\]", fm.group(1))
            if am:
                for a in am.group(1).split(","):
                    a = a.strip().strip('"').strip("'").strip()
                    if a:
                        names.add(a)

    def resolvable(tgt):
        return (tgt in names or tgt in paths or tgt.split("/")[-1] in names)

    # 1) wikilinks (no leading ! -> embeds excluded here)
    linkre = re.compile(r"(?<!\!)\[\[([^\]]+)\]\]")
    unresolved = {}
    linked_targets = set()
    for f in files:
        for mt in linkre.finditer(content[f]):
            tgt = mt.group(1).split("|")[0].split("#")[0].strip()
            if not tgt:
                continue
            linked_targets.add(tgt.split("/")[-1])
            if not resolvable(tgt):
                unresolved.setdefault(tgt, set()).add(os.path.relpath(f, root))

    # 2) section embeds
    embedre = re.compile(r"!\[\[([^\]#]+)#([^\]]+)\]\]")
    embed_problems = []
    for f in files:
        for m in embedre.finditer(content[f]):
            tgt, head = m.group(1).strip(), m.group(2).strip()
            base = tgt.split("/")[-1]
            linked_targets.add(base)
            if base not in headings:
                embed_problems.append(
                    f"MISSING FILE: ![[{tgt}#{head}]]  in {os.path.relpath(f, root)}")
            elif head not in headings[base]:
                avail = sorted(headings[base])[:8]
                embed_problems.append(
                    f"MISSING HEADING: ![[{tgt}#{head}]]  in {os.path.relpath(f, root)}\n"
                    f"     available in '{base}': {avail}")

    # plain embeds ![[File]] also count as inbound links
    for f in files:
        for m in re.finditer(r"!\[\[([^\]#|]+)\]\]", content[f]):
            linked_targets.add(m.group(1).strip().split("/")[-1])

    # 3) duplicate basenames
    duplicates = {b: p for b, p in basename_files.items() if len(p) > 1}

    # 4) orphans
    orphans = sorted(b for b in basename_files if b not in linked_targets)

    print(f"Vault: {root}   ({len(files)} .md files)")
    print("=" * 60)
    if not unresolved:
        print("Wikilinks:      ALL RESOLVE ✓")
    else:
        print(f"Wikilinks:      {len(unresolved)} unresolved target(s):")
        for tgt in sorted(unresolved):
            print(f"  [[{tgt}]]  <- {sorted(unresolved[tgt])}")
    if not embed_problems:
        print("Section embeds: ALL MATCH ✓")
    else:
        print(f"Section embeds: {len(embed_problems)} problem(s):")
        for p in embed_problems:
            print("  " + p)
    if not duplicates:
        print("Duplicate names: NONE ✓")
    else:
        print(f"Duplicate names: {len(duplicates)} ambiguous basename(s) (warning):")
        for b, ps in sorted(duplicates.items()):
            print(f"  '{b}' -> {ps}")
    if not orphans:
        print("Orphan notes:   NONE ✓")
    else:
        print(f"Orphan notes:   {len(orphans)} note(s) nothing links to (warning):")
        for b in orphans:
            print(f"  {b}")
        print("  (the vault's own index note is expected here)")

    hard_fail = bool(unresolved or embed_problems)
    soft_fail = bool(duplicates or orphans)
    return 1 if (hard_fail or (strict and soft_fail)) else 0


if __name__ == "__main__":
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    args = [a for a in sys.argv[1:] if a != "--strict"]
    sys.exit(main(args[0] if args else ".", "--strict" in sys.argv))
