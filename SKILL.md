---
name: obsidify
description: >-
  Turns a lecture script, textbook, or PDF (any subject, any language) into a
  navigable Obsidian study vault of linked Markdown notes: a table of contents with
  tick-off checkboxes, atomic topic and definition files, plus a summary, formula
  sheet, and exam checklist. Chapters are transferred in parallel by subagents.
  Use this skill whenever someone wants a script, PDF, book, or course material turned
  into Obsidian notes, a "study vault", a "knowledge net", a linked note collection,
  or Markdown study material — even if the word "obsidify" never comes up (e.g. "turn
  this lecture PDF into Obsidian notes", "build me a linked study vault from this book",
  "mach aus diesem Skript Obsidian-Notizen"). Use it just as much for maintaining a vault
  that already exists: "update the vault", "resume obsidification", "apply the changes",
  "I have a newer edition of the script", "the vault is out of date", "finish the missing
  chapters", or any request to sync, extend, repair, or re-verify notes against their source.
compatibility: >-
  Requires poppler (pdftotext, pdftoppm, pdfinfo) and Python 3.8+. Pillow is optional — it
  powers the figure grid overlay and margin trimming; plain crops fall back to poppler.
  Assumes the agent can view rendered page images, since visual verification of formulas is
  the core accuracy mechanism. Parallel chapter transfer needs subagents and degrades to
  sequential without them. The source must be a PDF with a text layer.
metadata:
  version: "1.0"
---

# Obsidify — Script → navigable Obsidian study vault

This skill transfers a source (usually a PDF script) faithfully into an Obsidian vault
of small, heavily linked notes, then builds study aids on top of it. The goal: find,
understand, and learn the material faster. **Fidelity to the source outranks everything
else** — this is real study material someone will revise from before an exam. An invented
formula is worse than no note at all.

## Which mode is this?

Check for an existing vault before doing anything — a rebuild over someone's annotated
notes destroys work they can't get back.

- **A `_obsidify/manifest.json` exists, or the folder already holds obsidified notes**
  → this is an **update**. Jump to "Updating an existing vault" and touch only what changed.
- **Nothing there yet** → fresh build, Phase 0 onwards.
- **Ambiguous** (notes exist but no manifest — built by hand or before indexing) → run
  `sync_source.py init` first, which only reads, then treat it as an update.

## Guiding principles

- **Fidelity before creativity.** Content, numbering (Definition/Theorem/Example X.Y),
  and order exactly as in the source. Your own didactic additions (mnemonics, intuitions)
  are welcome, but **mark them as yours** (e.g. inside `> [!tip]`) — never emit them as
  source content.
- **Atomic + linked.** Every definition or term used by **more than one topic** gets its
  **own file** and is referenced everywhere via `[[...]]`. Topic-specific definitions stay
  inside their topic file.
- **Language and naming follow the source.** If the script is German, folders are
  „Kapitel 1 …", „Grundlagen", „Inhaltsverzeichnis"; if English, "Chapter 1 …",
  "Fundamentals", "Contents". File and topic names **exactly** as in the source's table
  of contents. Frontmatter *keys* stay English (`tags:`, `source:`) so tooling works;
  everything a reader sees is in the source language.
- **Verify, don't guess.** Formulas, matrices, tables, and figures get checked **visually
  against the rendered PDF page**; worked examples get spot-recomputed. Fix typos in the
  source and flag that you did.
- **Work only inside the target folder**, leave the source file untouched.

## Setup

1. **Poppler** for PDF rendering and text extraction:
   - `pdftoppm` — renders pages to images so you can actually *look* at them; essential for formulas
   - `pdftotext` — raw text, used as a typing base only
   - `pdfinfo` — page count and metadata
   - Install: macOS `brew install poppler`, Debian/Ubuntu `apt-get install poppler-utils`
2. Extract raw text once: `pdftotext -layout script.pdf _scratch/raw.txt`.
   **Matrices and tables come out mangled → always cross-check the rendered page.**
3. Determine the **page offset** rather than assuming it: find a numbered heading in
   `raw.txt`, render the PDF page you expect it on, and compare. Record
   `PDF page = printed page + offset` — every subagent needs it.

## The workflow

Work the phases **in order**. Keep a todo list and report progress to the user.

### Phase 0 — Recon and plan

1. Page count (`pdfinfo`), source language, subject.
2. Read the source's **table of contents** (render the first pages): chapters,
   subsections, printed page numbers.
3. Locate chapter boundaries in `raw.txt`: `grep -n "Definition 3.1" _scratch/raw.txt`
   and similar anchors. Record for each chapter: raw-text line range + PDF page range.
4. Build the **canonical name registry** (see below) — this is what makes parallel work safe.
5. Show the user the planned structure (chapters, folders, roughly how many notes) before
   writing hundreds of files. Cheap to correct now, expensive later.

### Phase 1 — Scaffold (structure only, no topic content yet)

1. Write **`Contents.md`** (source-language name): all chapters and topics **as in the
   source**, each topic link as a **checkbox** `- [ ] [[Topic name]]` to tick off after
   studying, plus printed page numbers. A navigation block at the top links to
   `[[Summary]] · [[Formula sheet]] · [[Checklist]]` and to the Fundamentals hub.
2. Create the **folder structure**: `Fundamentals/` plus one folder per chapter.
   **No topic files yet** — folders only.

### Phase 2 — Faithful transfer (parallelized)

One file per topic, named after the subsection in the table of contents.
Write **chapter 1 and the core Fundamentals notes yourself first** — they become the
style seed every subagent reads. Then dispatch the remaining chapters in parallel
(see "Parallelizing with subagents").

Order within any chapter: read the raw-text slice → **render every PDF page of the chapter**
and verify formulas, matrices, figures → write files → recompute examples.

Move on only when **all** chapters are transferred.

### Phase 3 — Review and repair

- File overview: `find . -name '*.md' | sort`
- **Link and embed check** with the bundled script:
  `python3 scripts/check_links.py <vault-dir>`
  It reports unresolvable `[[wikilinks]]` (aliases and path links accounted for),
  `![[Embeds#Heading]]` whose target heading is missing, duplicate basenames (which make
  Obsidian links ambiguous), and orphan notes nothing links to. Expect 0 problems —
  except `[[Summary]]`/`[[Formula sheet]]`/`[[Checklist]]`, which Phase 4 creates.
- Fix everything it reports. Repairs across many chapters can be parallelized the same
  way the transfer was.
- Spot check: pick one computation-heavy page, view it against the PDF, and follow the
  arithmetic through.
- Read the uncertainty lists the subagents returned and resolve each one against the PDF.

### Phase 4 — Study aids (only after the transfer is complete and verified)

Now navigate your own vault — read the core definitions and theorem headings you produced
— and create:

1. **`Summary.md`** — a readable through-line across all chapters, linking to the major
   topic files. Its job is to show **how the topics connect**, not to restate them.
2. **`Formula sheet.md`** — every **exam-relevant** definition/formula, compact, grouped
   by chapter, each linked to its full derivation. Skip this file if the source has no
   formulas.
3. **`Checklist.md`** — per topic, **checkpoints** ("what must I understand / be able to
   apply?") as checkboxes, linked. Several per topic where warranted. This is what someone
   actually works through the week before the exam.

Optional, if the user wants it: `Flashcards.md` with `Question :: Answer` lines for
spaced-repetition plugins.

### Phase 5 — Index the vault (never skip this)

```bash
python3 scripts/sync_source.py init <vault> --pdf <source.pdf> --offset <N>
```

This records which note came from which part of the source, a hash of each note as you
wrote it, and a snapshot copy of every note, into `_obsidify/`. It costs seconds and it is
the only thing that makes a later update surgical instead of a rebuild: the hash detects
that a note was touched, and the snapshot shows *which lines* the user added — without it,
their annotations can only be guessed at by reading. Re-run it after every applied update
so the next one starts from a clean baseline.

## Updating an existing vault

Triggered by "update the vault", "resume obsidification", "apply the changes", a newer
edition of the script, or an interrupted build. Two rules govern everything here:
**touch only what changed**, and **never overwrite the user's own work**. They study in
this vault — ticked checkboxes, added mnemonics, and margin notes are the whole point of it.

**1. Find out what actually needs doing.**

```bash
python3 scripts/sync_source.py status <vault>              # missing + hand-edited notes
python3 scripts/sync_source.py diff <vault> --pdf <new.pdf>  # what the new edition changed
```

`diff` gives a per-note verdict — UNCHANGED, CHANGED, ANCHOR-LOST, USER-EDITED,
NO-ANCHOR — plus labels added or removed between editions (an inserted `Definition 3.4`)
and labels no note covers yet. Anchors are content strings, not line numbers, so they
survive repagination.

**2. Decide per verdict.**

| Verdict | Action |
|---|---|
| UNCHANGED | Do nothing. Do not re-read the pages, do not rewrite the file. |
| CHANGED | Re-transfer that note from the new PDF pages, verifying visually as always. |
| USER-EDITED, source unchanged | Leave it alone entirely. |
| USER-EDITED, source also changed | Run `sync_source.py merge <vault> <note> --pdf <new.pdf>` and follow it (see below). |
| ANCHOR-LOST | The section was renamed, renumbered, or dropped. Investigate in the PDF before assuming deletion. |
| Label with no note | New material — write a new note and add it to the contents file. |
| Label removed | **Archive, never delete.** Move to `_archive/` and report it. |
| Missing (from `status`) | An interrupted build: write it exactly as a fresh chapter agent would. |

**2a. Merging a note that is both user-edited and source-changed.** This is the only case
where two sets of changes collide, and it's the one worth slowing down for:

```bash
python3 scripts/sync_source.py merge <vault> "Chapter 2/Rings.md" --pdf <new.pdf>
```

It prints two panels: the exact lines the user added or removed since the note was
generated, and what the new edition did to that same section. Rewrite the source-derived
parts from the new PDF pages as usual, then re-apply every `+` line from the first panel
**verbatim**. If a user line no longer fits the updated text, keep it and flag it — a
mnemonic that took them twenty minutes to invent is not yours to discard. Note verdicts
carry a `[+3/-0 lines]` tag so you can see at a glance whether an edit is a ticked
checkbox or a rewritten paragraph.

**3. Show the plan before writing.** List the affected files and what will happen to each,
and get a nod. An update that silently rewrites 40 notes is indistinguishable from a
rebuild, which is what the user is trying to avoid.

**4. Apply, parallelized by affected chapter.** Dispatch one subagent per *affected*
chapter, with the same brief as a fresh build plus its verdict list and the instruction to
touch only the named files. Untouched chapters get no agent at all. That's where the speed
comes from: a new edition usually moves a handful of sections, not the whole book.

**5. Preserve the study surface.** In `Contents.md` and `Checklist.md`, *insert* new lines
rather than regenerating the files — regenerating resets every ticked checkbox. New entries
start unchecked; existing ones keep their state. Where a note's content changed materially,
consider unticking it so the user knows to re-read, and say that you did.

**6. Re-verify and re-index.**

```bash
python3 scripts/check_links.py <vault>
python3 scripts/sync_source.py init <vault> --pdf <new.pdf> --offset <N>
```

Renumbering is the dangerous case: inserting `Definition 3.4` shifts every later number,
and those headings are embed targets, so `![[Group#Definition 3.5 …]]` breaks silently
across the whole vault. Always finish with the link check.

**7. Report** what changed, what was archived, what you merged, and anything you weren't
sure about — with page numbers.

## Parallelizing with subagents

For anything beyond ~2 chapters, transferring chapters **in parallel** is dramatically
faster. Chapters are near-independent — the only real coupling is *shared names*, so
pin those down first and the rest is collision-free.

**1. Seed the style.** Write chapter 1 and the core Fundamentals notes yourself. They are
the worked example every agent imitates; a style guide alone is not enough.

**2. Write the canonical name registry** to `_scratch/registry.md` before dispatching.
Every cross-chapter term gets exactly *one* home chapter that creates its atomic file;
everyone else only links to it. Nothing can be created twice, and dead forward links
resolve themselves the moment the owning chapter lands — so chapter order doesn't matter.

```markdown
| Term        | Owner       | Canonical file    | Canonical heading        |
|-------------|-------------|-------------------|--------------------------|
| Group       | Chapter 2   | Group.md          | ## Definition 2.1 (Group)|
| Vector space| Chapter 4   | Vector space.md   | ## Definition 4.1 …      |
```

The exact heading string matters: `![[Group#Definition 2.1 (Group)]]` only resolves on an
exact match.

**3. Dispatch every chapter in one turn**, one agent per chapter. Each gets:
the filled-in **style guide** (`references/styleguide-template.md`), paths to **2–3 sample
files** from chapter 1, the **registry**, its **raw-text line range** and **PDF page range**,
the **exact filenames** of its topics, the **atomic shared files it owns**, and the duty of
**visual verification**.

**4. Enforce boundaries.** An agent writes only inside its own chapter folder plus the
atomic files assigned to it. It never touches `Contents.md`, `Fundamentals/`, or another
chapter's folder. This is what keeps concurrent writes safe.

**5. Size the units.** One agent per chapter is the default. Split a chapter above roughly
40 source pages into two agents by section range, with one of them owning the shared atomic
files. If the runtime struggles with many concurrent agents, dispatch in waves of about
five rather than serializing.

**6. Collect reports.** Each agent returns: files created (paths), atomic files created,
and **uncertainties / hard-to-read PDF spots**. Do not discard these — they drive Phase 3.

**No subagents available** (e.g. on claude.ai): run the same contract sequentially,
chapter by chapter, registry and all. It is slower but produces the identical vault.

## Conventions (binding for every file written)

### Split: `Fundamentals/` vs chapter folders

- **`Fundamentals/`** = cross-chapter *primitives* that **no chapter is named after**, and
  prerequisites assumed from earlier courses (for linear algebra: operations & closure,
  set notation, sum notation, equivalence relations, induction, mappings). Mark these
  as "revision" / "quick reference".
- **Chapter folders** = the structures the chapter is *named* after, as their own atomic
  note when several topics use them (e.g. "Group", "Ring", "Vector space").
- A cross-chapter definition that is *introduced* in chapter N lives in **chapter N**;
  later chapters only **link** to it (forward and backward links).
- `Fundamentals/` gets a hub file listing all fundamentals by category.

### File anatomy

Every file starts with frontmatter plus a navigation header:

```
---
tags: [chapter-N, topic|definition|theorem|example]
source: <source> p. XX–YY
aliases: [<short link target>]
---
# <Title>

> Chapter N · <Chapter name>. Back to [[Contents]].
> Previous: [[...]] · Next: [[...]]
> Prerequisite: [[...]]
```

- Definitions/theorems/examples as `## Definition X.Y (Title)` with **the source's numbering**.
- **Bold** for newly defined technical terms.
- **Proofs** in collapsible callouts: `> [!note]- Proof` (prefix every line with `> `),
  ending with `\qquad \blacksquare`.
- Mnemonics/warnings/intuition: `> [!tip]`, `> [!warning]`, `> [!info]`.
- **Embed shared atomic definitions by section:** in the topic file write
  `![[Filename#Heading]]` — the text appears in context but is maintained in one place.
  The heading must match **exactly**.

### Mathematics (Obsidian / KaTeX–MathJax)

- Inline `$...$`, display `$$...$$` on its own line.
- Number sets `\mathbb{Z,Q,R,N,C}`, fields usually `K`.
- Matrices `\begin{pmatrix}...\end{pmatrix}`, determinants `\begin{vmatrix}...\end{vmatrix}`,
  cases `\begin{cases}...\end{cases}`.
- Symbols `\ast \cdot \circ \times \oplus \odot \mapsto \to \in \notin \neq \emptyset
  \subseteq \setminus \Rightarrow \iff \forall \exists \sum \langle \rangle \mid`.
- Obsidian's renderer chokes on some LaTeX: avoid `\begin{align}` outside `$$`, `\text{}`
  with unbalanced braces, and `\\` line breaks inside inline math.

### Figures

Diagrams and sketches that aren't expressible as LaTeX have two options, in this order:

1. **Extract the real figure** with `scripts/crop_figure.py`. You can't guess crop
   coordinates from raw text, so the script overlays a labelled grid on the page for you
   to read them off:
   ```bash
   python3 scripts/crop_figure.py grid script.pdf 42          # view the grid overlay
   python3 scripts/crop_figure.py crop script.pdf 42 \
       --box 0.12,0.30,0.88,0.62 -o assets/fig-3-2.png --trim
   ```
   Then embed it with a caption: `![[assets/fig-3-2.png]]`. Look at the result before
   embedding — a half-cut axis label is worse than no figure. A real figure beats any
   description and keeps you from inventing detail.
2. **Describe it precisely** in a `> [!info] Sketch` callout, marked "replace with image
   if possible". Describe only what you can see. Invent nothing.

### Linking

- Link generously between related topics, across chapters too.
- Give cross-chapter terms **canonical filenames** (the registry) so every link resolves.
- Frontmatter `aliases: [...]` let short link targets like `[[Basis]]` resolve to a longer
  topic filename.
- Avoid two files with the same basename in different folders — Obsidian resolves such
  links ambiguously. `check_links.py` flags these.

## Scope: text-layer PDF only

This skill supports **PDFs with a text layer**, and nothing else. Be straight with the
user about that rather than improvising around it:

- **`.txt`, `.tex`, `.epub`, `.docx`, HTML, Markdown** — `crop_figure.py` and
  `sync_source.py` both shell out to poppler and will fail outright on these. You can still
  build a vault by hand from converted text (`pandoc -t plain`), but say plainly that the
  update, resume, and merge workflow won't be available for it, and that no formula was
  verified against a rendered page. Don't run `init` on a non-PDF source — a broken
  manifest is worse than none.
- **Scanned PDFs with no text layer** — `pdftotext` returns almost nothing and reports no
  error, so this fails *silently*. Before Phase 0, sanity-check the extraction: if the raw
  text holds fewer than ~200 characters per page, treat the source as scanned. Say so and
  stop; OCR (e.g. `ocrmypdf`) has to happen first, outside this skill.
- **`.tex` deserves a mention** because it would actually be a *better* source than PDF —
  formulas are already LaTeX, `\section` gives exact structure, `\label`/`\ref` map onto
  wikilinks. The tooling here doesn't handle it yet. If a user hands you `.tex` and also has
  the compiled PDF, use the PDF.

## Result structure (example, German-language script)

```
Quelle.pdf                      (unchanged)
Inhaltsverzeichnis.md           (checkboxes + links)
Zusammenfassung.md
Formelsammlung.md               (only if the source has formulas)
Checklist.md
assets/                         (extracted figures)
Grundlagen/                     (hub + cross-chapter primitives)
Kapitel 1 …/                    (topic files + atomic core definitions)
Kapitel 2 …/
…
```

## Bundled resources

- `scripts/check_links.py` — vault-wide wikilink, section-embed, duplicate-name, and
  orphan checker. Run it at the end of Phase 2 and again after Phase 4.
- `scripts/crop_figure.py` — renders, grids, and crops PDF pages so real figures land in
  `assets/` instead of being paraphrased. Subagents need its path in their brief.
- `scripts/sync_source.py` — `init` indexes a vault against its source and snapshots every
  note, `status` finds missing and hand-edited notes, `diff` reports what a new edition
  changed, `merge` shows the user's exact edits beside the source's for one note. Drives
  the update workflow above.
- `references/styleguide-template.md` — the per-chapter subagent brief. Fill in the
  placeholders and hand one to each chapter agent.
