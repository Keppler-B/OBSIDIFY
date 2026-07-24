# OBSIDIFY

An [Agentic Skillset](https://agentskills.io) that turns a lecture script or textbook PDF into a
navigable Obsidian study vault: a table of contents with tick-off checkboxes, small atomic
linked notes, and a summary, formula sheet if needed, and exam checklist built on top.

Chapters are transferred **in parallel** by subagents, and the vault can be **updated in
place** when a newer edition of the source appears, touching only the affected notes, and
never overwriting annotations you added while studying.

## Install

**Any agent that supports the Agent Skills standard can use this skill** (Claude Code, Codex, Cursor, VS Code,
Gemini CLI, Goose, and others). Just clone into that tool's skills directory:

```bash
git clone https://github.com/Keppler-B/OBSIDIFY.git ~/$YOUR_PATH/skills/obsidify
```

Consult your tool's docs for its skills path; the directory layout is the same everywhere.

**If your model supports `.skill` files**: for direct use, archive the desired build with the following command and upload it

```bash
git archive --format=zip --prefix=obsidify/ -o ../obsidify.skill HEAD
```

Or just download the latest release of OBSIDIFY on the righthandside.

> [!NOTE]
> If you're going to archive the skill yourself, please note, that you will have to add any automatically created systemfiles from your specific OS into the .gitattributes file with the flag `export-ignore`.

---

## Requirements

| Requirement | Why it's needed |
|---|---|
| **Linux** — Debian/Ubuntu, Fedora, Arch | Supported platform. |
| **macOS 11+** (Big Sur or later) | Supported platform. |
| **poppler 0.68+** — `pdftotext`, `pdftoppm`, `pdfinfo` | Text extraction, page rendering, and page counts. Every script shells out to these. |
| **Python 3.8+** | Runs the bundled scripts. No third-party packages required. |
| **Pillow 9+** *(optional)* | Figure grid overlay and margin trimming in `crop_figure.py`. Plain crops fall back to poppler without it. |
| **An agent that can view rendered page images** | Visual verification of formulas against the PDF is the skill's core accuracy mechanism; a text-only model cannot do it. |
| **Subagents** *(optional)* | Parallel chapter transfer. Without them the skill runs the same contract sequentially — slower, identical output. |

Get poppler for Linux via
```bash
apt-get install poppler-utils

# or

dnf install poppler-utils

# or

pacman -S poppler
```

Get poppler for MacOS via
```bash
brew install poppler
```


> [!NOTE]
> Windows is not supported natively; run it under [WSL](https://learn.microsoft.com/de-de/windows/wsl/install).

## Scope

Text-layer PDFs only. `.tex`, `.epub`, `.docx`, and plain text are **not yet** supported by
the tooling; scanned PDFs need OCR first. See the "Scope" section in `SKILL.md`.

## Usage

Point your agent at a PDF with prompts the likes of:

> Obsidify `Lecture-Script.pdf`
> 
> Turn `Lecture-Script.pdf` into an Obsidian study vault.
> 
> Create a Knowledge graph from `Lecture-Script.pdf`

Later, when the lecturer publishes a new edition:

> Update the vault. Here is the new edition: `Lecture-Script-Update.pdf`.

The skill diffs the new source against the old one and rewrites only what changed. Notes you
edited by hand are flagged rather than regenerated; where your edit and the source change
collide, it shows both diffs side by side so the merge keeps your annotations verbatim.

## What's in here

| File | Purpose |
|---|---|
| `SKILL.md` | The workflow: build phases, parallelization contract, update procedure, conventions |
| `references/styleguide-template.md` | Per-chapter brief handed to each subagent |
| `scripts/check_links.py` | Wikilink, section-embed, duplicate-name, and orphan checker |
| `scripts/crop_figure.py` | Renders, grids, and crops PDF figures into `assets/` |
| `scripts/sync_source.py` | `init` / `status` / `diff` / `merge` — the update machinery |

Each script runs standalone; `--help` on any of them explains its own usage.

## How updates stay safe

`sync_source.py init` records, per note, the slice of source text it came from, a hash of
the note as generated, and a snapshot copy of it. That snapshot is what makes a later update
surgical: the hash detects that a note was touched, and the snapshot shows *which lines* you
added. Unchanged notes are skipped entirely; removed sections are archived, never deleted.
