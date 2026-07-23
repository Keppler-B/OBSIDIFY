#!/usr/bin/env python3
"""
Figure extraction helper for Obsidify vaults.

Cropping a figure out of a PDF page needs coordinates, and you can't guess those from
raw text. So the workflow is: overlay a labelled grid on the page, LOOK at it, read the
box off the grid, then crop.

  1. python3 crop_figure.py grid script.pdf 42
       -> _scratch/grid-p42.png  (the page with a 0.0-1.0 coordinate grid drawn on it)
       Open/view that image and read off the corners of the figure you want.

  2. python3 crop_figure.py crop script.pdf 42 --box 0.12,0.30,0.88,0.62 \
         -o assets/fig-3-2.png --trim
       -> a tight, high-resolution PNG ready to embed as ![[assets/fig-3-2.png]]

  Also available:
  python3 crop_figure.py page script.pdf 42 -o _scratch/p42.png --dpi 150

Coordinates are FRACTIONS of the page (0.0-1.0), origin top-left:
x0,y0 = left,top corner and x1,y1 = right,bottom corner. Fractions rather than pixels
so the same box works at any --dpi.

Requires: poppler (pdftoppm, pdfinfo). Pillow is used for the grid overlay and --trim;
without it, plain cropping still works via pdftoppm's own crop flags.
"""
import argparse
import os
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageDraw
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Command failed: {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout


def check_poppler():
    for tool in ("pdftoppm", "pdfinfo"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            sys.exit(f"'{tool}' not found. Install poppler "
                     "(macOS: brew install poppler, Debian/Ubuntu: apt-get install poppler-utils).")


def page_count(pdf):
    for line in run(["pdfinfo", pdf]).splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return None


def render_page(pdf, page, dpi, out_png):
    """Render one page to out_png at the given dpi."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)) or ".", exist_ok=True)
    prefix = os.path.splitext(out_png)[0]
    run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi),
         "-png", "-singlefile", pdf, prefix])
    return prefix + ".png"


def parse_box(s):
    try:
        vals = [float(v) for v in s.split(",")]
    except ValueError:
        sys.exit("--box must be four numbers: x0,y0,x1,y1")
    if len(vals) != 4:
        sys.exit("--box must be four numbers: x0,y0,x1,y1")
    x0, y0, x1, y1 = vals
    if not all(0.0 <= v <= 1.0 for v in vals):
        sys.exit("--box values are fractions of the page and must lie between 0 and 1.")
    if x1 <= x0 or y1 <= y0:
        sys.exit("--box needs x1 > x0 and y1 > y0 (left,top,right,bottom).")
    return x0, y0, x1, y1


def trim_margins(img, tolerance=8, pad=12):
    """Trim uniform near-white margins, then add a little padding back."""
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    threshold = 255 - tolerance

    def row_blank(y):
        return all(px[x, y] >= threshold for x in range(w))

    def col_blank(x):
        return all(px[x, y] >= threshold for y in range(h))

    top, bottom = 0, h - 1
    while top < bottom and row_blank(top):
        top += 1
    while bottom > top and row_blank(bottom):
        bottom -= 1
    left, right = 0, w - 1
    while left < right and col_blank(left):
        left += 1
    while right > left and col_blank(right):
        right -= 1

    if right - left < 4 or bottom - top < 4:
        return img  # nothing but blank page; hand back the original

    return img.crop((max(0, left - pad), max(0, top - pad),
                     min(w, right + 1 + pad), min(h, bottom + 1 + pad)))


def cmd_page(args):
    out = args.out or f"_scratch/p{args.page}.png"
    path = render_page(args.pdf, args.page, args.dpi, out)
    print(f"Rendered page {args.page} -> {path}")


def cmd_grid(args):
    if not HAVE_PIL:
        sys.exit("The grid overlay needs Pillow (pip install Pillow).")
    out = args.out or f"_scratch/grid-p{args.page}.png"
    with tempfile.TemporaryDirectory() as td:
        src = render_page(args.pdf, args.page, args.dpi, os.path.join(td, "page.png"))
        img = Image.open(src).convert("RGB")

    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    n = args.divisions
    for i in range(n + 1):
        frac = i / n
        x, y = int(frac * (w - 1)), int(frac * (h - 1))
        heavy = (i % 5 == 0)
        colour = (200, 0, 0, 190) if heavy else (0, 90, 200, 110)
        draw.line([(x, 0), (x, h)], fill=colour, width=2 if heavy else 1)
        draw.line([(0, y), (w, y)], fill=colour, width=2 if heavy else 1)
        if heavy:
            label = f"{frac:.1f}"
            draw.text((min(x + 3, w - 24), 3), label, fill=(200, 0, 0, 255))
            draw.text((3, min(y + 3, h - 14)), label, fill=(200, 0, 0, 255))

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    img.save(out)
    print(f"Grid overlay -> {out}")
    print("View it, read the figure's corners off the red labels, then:")
    print(f"  crop_figure.py crop {args.pdf} {args.page} "
          f"--box x0,y0,x1,y1 -o assets/fig-N-k.png --trim")


def cmd_crop(args):
    x0, y0, x1, y1 = parse_box(args.box)
    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)

    if HAVE_PIL:
        with tempfile.TemporaryDirectory() as td:
            src = render_page(args.pdf, args.page, args.dpi, os.path.join(td, "page.png"))
            img = Image.open(src)
            w, h = img.size
            crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
            if args.trim:
                crop = trim_margins(crop, pad=args.pad)
            crop.save(out)
            size = crop.size
    else:
        # Fallback: let pdftoppm crop, using its pixel-space flags.
        info = run(["pdfinfo", "-f", str(args.page), "-l", str(args.page), args.pdf])
        pts = next((l for l in info.splitlines() if l.startswith("Page")
                    and "size:" in l), None)
        if not pts:
            sys.exit("Could not read the page size; install Pillow for the reliable path.")
        parts = pts.split()
        wpt, hpt = float(parts[3]), float(parts[5])
        w, h = wpt * args.dpi / 72.0, hpt * args.dpi / 72.0
        prefix = os.path.splitext(out)[0]
        run(["pdftoppm", "-f", str(args.page), "-l", str(args.page), "-r", str(args.dpi),
             "-png", "-singlefile",
             "-x", str(int(x0 * w)), "-y", str(int(y0 * h)),
             "-W", str(int((x1 - x0) * w)), "-H", str(int((y1 - y0) * h)),
             args.pdf, prefix])
        size = (int((x1 - x0) * w), int((y1 - y0) * h))
        if args.trim:
            print("Note: --trim needs Pillow; wrote the untrimmed crop.")

    print(f"Cropped page {args.page} -> {out}  ({size[0]}x{size[1]} px)")
    rel = out
    for marker in ("/assets/", "assets/"):
        if marker in out:
            rel = "assets/" + out.split("assets/", 1)[1]
            break
    print(f"Embed it with:  ![[{rel}]]")
    print("Check the crop before embedding — a half-cut axis label is worse than no figure.")


def main():
    check_poppler()
    p = argparse.ArgumentParser(
        description="Render, grid, and crop PDF figures for an Obsidian vault.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grid", help="render a page with a 0.0-1.0 coordinate grid")
    g.add_argument("pdf"); g.add_argument("page", type=int)
    g.add_argument("-o", "--out"); g.add_argument("--dpi", type=int, default=100)
    g.add_argument("--divisions", type=int, default=20)
    g.set_defaults(func=cmd_grid)

    r = sub.add_parser("page", help="render a whole page")
    r.add_argument("pdf"); r.add_argument("page", type=int)
    r.add_argument("-o", "--out"); r.add_argument("--dpi", type=int, default=150)
    r.set_defaults(func=cmd_page)

    c = sub.add_parser("crop", help="crop a figure out of a page")
    c.add_argument("pdf"); c.add_argument("page", type=int)
    c.add_argument("--box", required=True, help="x0,y0,x1,y1 as fractions of the page")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--dpi", type=int, default=200)
    c.add_argument("--trim", action="store_true", help="trim blank margins off the crop")
    c.add_argument("--pad", type=int, default=12, help="padding kept when trimming")
    c.set_defaults(func=cmd_crop)

    args = p.parse_args()
    n = page_count(args.pdf)
    if n and not (1 <= args.page <= n):
        sys.exit(f"Page {args.page} is out of range — the PDF has {n} pages. "
                 "Remember PDF page = printed page + offset.")
    args.func(args)


if __name__ == "__main__":
    main()
