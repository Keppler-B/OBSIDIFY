# Style guide template (Obsidify) — hand one filled-in copy to each chapter subagent

Fill in the `<…>` placeholders. Translate the brief into the source's language if that
helps the agent stay in that language. Goal: a consistent, faithful transfer of one chapter
into Obsidian Markdown, safely in parallel with other agents.

---

You are transferring **Chapter <N> "<Chapter title>"** of the source into Obsidian Markdown.
Fidelity to the source outranks everything else — this is real study material someone will
revise from. An invented formula is worse than no note at all.

## Do this first
1. Read 2–3 sample files from the already-finished chapter 1 to absorb the style
   (frontmatter, callouts, LaTeX, section embeds): `<paths to 2–3 sample files>`.
2. Read the canonical name registry: `<path to _scratch/registry.md>`. It tells you which
   shared terms you own and which you may only link to.

## Sources
- **PDF (ground truth for formulas / matrices / figures):** `<PDF path>`
  Page mapping: **PDF page = printed page + <offset>**. Render with
  `pdftoppm -f <a> -l <b> -r 150 -png <pdf> <outdir>/p` and view the images.
- **Raw text (typing base; matrices are mangled):** `<path to raw.txt>`.

## Your material
- Raw text lines approx. **<start>–<end>** (chapter starts at "<anchor, e.g. Definition N.1>",
  ends before "<next chapter anchor>").
- PDF pages **<a>–<b>**.
  **Render every page of your chapter** and visually verify all matrices, tables,
  operation tables, figures, computation steps, and complex formulas.
  Do **not** rely on the raw text for these. Spot-recompute worked examples.

## Output folder
`<chapter folder path>`

## Topic files to create (exact names from the table of contents)
- `<Topic 1>.md`
- `<Topic 2>.md`
- …

## Shared atomic definitions YOU own
(own file + link target, because several chapters use them; canonical link `[[…]]`)
- `<Term>.md` — contains `<Definition X.Y>`; canonical `[[<Term>]]`. The corresponding topic
  file embeds it by section: `![[<Term>#<Heading>]]`. The heading string must match exactly.

## Link only — do not create (owned by other chapters / Fundamentals)
`<list of canonical link targets>` — dead forward links are fine here; the owning chapter
fills them in. Creating a second file for one of these breaks the vault, so don't.

## Boundaries
Write **only** inside your output folder and the atomic files listed above. Do not touch
`Contents.md`, the Fundamentals folder, or another chapter's folder — other agents are
working in parallel.

## Markdown / LaTeX conventions
- Inline `$...$`, display `$$...$$`. Number sets `\mathbb{Z,Q,R,N,C}`, fields `K`.
- Matrices `\begin{pmatrix}…\end{pmatrix}`, determinants `\begin{vmatrix}…\end{vmatrix}`,
  cases `\begin{cases}…\end{cases}`. Proofs end with `\qquad \blacksquare`.
- Proofs in collapsible callouts `> [!note]- Proof` (prefix every line with `> `);
  mnemonics/warnings `> [!tip]` / `> [!warning]` / `> [!info]`.
- Definitions/theorems/examples as `## Definition X.Y (Title)` with **the source's numbering**.
- **Bold** for newly defined technical terms.
- Figures: prefer extracting the real figure with `<path to crop_figure.py>` —
  `crop_figure.py grid <pdf> <page>` shows a coordinate grid to read the box off, then
  `crop_figure.py crop <pdf> <page> --box x0,y0,x1,y1 -o assets/fig-<N>-<k>.png --trim`.
  Embed as `![[assets/fig-<N>-<k>.png]]` and check the crop first. Only if that fails,
  describe the figure precisely in a `> [!info] Sketch` callout marked "replace with image
  if possible". Invent nothing.
- Fix typos in the source AND flag the intervention (e.g. a `[!warning]` note).

## File header (every file)
```
---
tags: [chapter-<N>, topic|definition|theorem|example]
source: <source> p. XX–YY
aliases: [<optional short link target>]
---
# <Title>

> Chapter <N> · <Chapter name>. Back to [[Contents]].
> Previous: [[…]] · Next: [[…]]
> Prerequisite: [[…]]
```

## When you finish
Return a compact report:
1. Files created (paths).
2. Atomic definition files created, with their exact canonical headings.
3. Uncertainties: hard-to-read PDF spots, formulas you are not confident about, examples
   whose arithmetic didn't check out, figures you could only describe. Be specific with page
   numbers — this list is worked through afterwards, so an honest "page 57, bottom matrix
   unreadable" is far more valuable than a confident guess.
