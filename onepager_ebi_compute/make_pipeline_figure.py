#!/usr/bin/env python3
"""Draw the DOME ML Observatory pipeline figure for the EMBL-EBI compute one-pager.

Deterministic: pure matplotlib, icons drawn from basic shapes, fixed sizes, no
timestamps in the output files. Running it twice gives byte-identical PNG and SVG.

    python3 onepager_ebi_compute/make_pipeline_figure.py

Numbers shown (sources in onepager_ebi_compute/README.md):
  classify tokens  8,667 in / 172 out   DeepSeek V4.1-Flash, dome-ml-observatory-triage/pricing/token_profiles.yaml
  enrich tokens    3,148 in / 1,481 out DeepSeek V4.1-Flash (production reference),
                                        dome-ml-observatory-triage/COST_DASHBOARD.md:45
  GLM test box     3,116 in / 346 out   GLM-5.3-Flash (experimental), runs/spend_log.csv (350 papers)
  parallelism      DeepSeek classify 400; enrich 800 -> 418 papers/min, 40 -> 53/min
                   dome-ml-observatory-triage/README.md:139,222-223, pricing/token_profiles.yaml:41
                   GLM 50 -> 230-300 papers/min, runs/spend_log.csv
  agreement + CIs  dome-triage/analysis/paper_figures/04_llm_second_curator/output/
                   table_llm_benchmark_paper_table.md (held-out 1,000, flash)
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (Arc, Circle, Ellipse, FancyArrowPatch,
                                FancyBboxPatch, Polygon, Rectangle)

OUT = Path(__file__).resolve().parent

# Observatory brand colours (dome-ml-observatory/observatory-ui/src/styles.scss)
NAVY = "#103344"
ORANGE = "#f66729"
ORANGE_DK = "#d94e13"
ORANGE_LT = "#fde6db"
GREEN = "#1b7a4d"
RED = "#c0392b"
GREY = "#55606b"
PALE = "#eef4f7"
WHITE = "#ffffff"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "svg.hashsalt": "dome-observatory",
    "svg.fonttype": "path",
    "path.simplify": False,
})

W, H = 124, 66          # drawing units; 1 unit = 0.1 inch
TILE_W, GAP = 21.6, 2.9
X0 = (W - (5 * TILE_W + 4 * GAP)) / 2
TILE_Y, TILE_H = 17.5, 39.0
ICON_Y = TILE_Y + TILE_H - 7.5
ICON_R = 5.4


def tile_x(i):
    return X0 + i * (TILE_W + GAP)


def text(ax, x, y, s, size=10, color=NAVY, weight="normal", **kw):
    ax.text(x, y, s, ha=kw.pop("ha", "center"), va=kw.pop("va", "center"),
            fontsize=size, color=color, fontweight=weight, **kw)


# ---------------------------------------------------------------- icons
def icon_search(ax, cx, cy):
    for k, dx in enumerate((-2.2, -1.1, 0.0)):              # stack of pages
        x, y = cx - 3.4 + dx, cy - 3.2 + dx * -0.6
        ax.add_patch(Rectangle((x, y), 4.6, 6.0, fc=WHITE, ec=NAVY, lw=1.2, zorder=4 + k))
    for j in range(4):
        ax.plot([cx - 2.8, cx + 0.4], [cy + 1.8 - j * 1.2] * 2, color=GREY, lw=0.9, zorder=7)
    ax.add_patch(Circle((cx + 1.6, cy - 0.4), 2.0, fc=PALE, ec=NAVY, lw=2.2, zorder=8))
    ax.plot([cx + 3.0, cx + 4.6], [cy - 1.8, cy - 3.4], color=NAVY, lw=3.2,
            solid_capstyle="round", zorder=8)


def icon_classify(ax, cx, cy):
    ax.add_patch(FancyBboxPatch((cx - 2.8, cy - 2.4), 5.6, 5.6, boxstyle="round,pad=0,rounding_size=0.8",
                                fc=NAVY, ec=NAVY, zorder=4))
    for t in (-1.6, 0.0, 1.6):                               # chip pins
        ax.plot([cx + t, cx + t], [cy + 3.2, cy + 4.0], color=NAVY, lw=1.4, zorder=3)
        ax.plot([cx + t, cx + t], [cy - 2.4, cy - 3.2], color=NAVY, lw=1.4, zorder=3)
        ax.plot([cx - 2.8, cx - 3.6], [cy + 0.4 + t] * 2, color=NAVY, lw=1.4, zorder=3)
        ax.plot([cx + 2.8, cx + 3.6], [cy + 0.4 + t] * 2, color=NAVY, lw=1.4, zorder=3)
    text(ax, cx, cy + 0.4, "AI", 11, WHITE, "bold", zorder=5)
    # yes / no badges
    ax.add_patch(Circle((cx - 4.0, cy - 3.6), 1.35, fc=GREEN, ec=WHITE, lw=1.0, zorder=6))
    ax.plot([cx - 4.6, cx - 4.1, cx - 3.3], [cy - 3.6, cy - 4.2, cy - 3.0], color=WHITE, lw=1.6, zorder=7)
    ax.add_patch(Circle((cx + 4.0, cy - 3.6), 1.35, fc=RED, ec=WHITE, lw=1.0, zorder=6))
    ax.plot([cx + 3.5, cx + 4.5], [cy - 4.1, cy - 3.1], color=WHITE, lw=1.6, zorder=7)
    ax.plot([cx + 3.5, cx + 4.5], [cy - 3.1, cy - 4.1], color=WHITE, lw=1.6, zorder=7)


def _tag(ax, x, y, fc, z):
    pts = [(x, y), (x + 4.4, y), (x + 6.0, y + 1.3), (x + 4.4, y + 2.6), (x, y + 2.6)]
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=NAVY, lw=1.1, zorder=z))
    ax.add_patch(Circle((x + 4.5, y + 1.3), 0.35, fc=WHITE, ec=NAVY, lw=0.8, zorder=z + 1))


def icon_enrich(ax, cx, cy):
    _tag(ax, cx - 3.6, cy + 1.2, ORANGE, 4)
    _tag(ax, cx - 2.6, cy - 1.0, "#ffb38e", 5)
    _tag(ax, cx - 1.6, cy - 3.2, WHITE, 6)


def icon_terms(ax, cx, cy):
    nodes = [(cx, cy + 2.6), (cx - 3.4, cy - 0.6), (cx + 3.4, cy - 0.6),
             (cx - 1.6, cy - 3.6), (cx + 1.8, cy - 3.6)]
    edges = [(0, 1), (0, 2), (1, 3), (2, 4), (1, 2), (3, 4)]
    for a, b in edges:
        ax.plot([nodes[a][0], nodes[b][0]], [nodes[a][1], nodes[b][1]], color=GREY, lw=1.3, zorder=3)
    for k, (x, y) in enumerate(nodes):
        ax.add_patch(Circle((x, y), 1.25 if k else 1.6, fc=NAVY if k else ORANGE, ec=WHITE, lw=1.0, zorder=4))


def icon_website(ax, cx, cy):
    # database cylinder
    x, y, w, h = cx - 4.2, cy - 3.6, 4.4, 5.6
    ax.add_patch(Rectangle((x, y), w, h, fc=NAVY, ec=NAVY, zorder=3))
    ax.add_patch(Ellipse((x + w / 2, y), w, 1.6, fc=NAVY, ec=NAVY, zorder=3))
    ax.add_patch(Ellipse((x + w / 2, y + h), w, 1.6, fc="#2f5b70", ec=NAVY, lw=1.0, zorder=4))
    for t in (1.9, 3.8):
        ax.add_patch(Arc((x + w / 2, y + t), w, 1.6, ec="#6f93a5", lw=0.9,
                         theta1=180, theta2=360, zorder=4))
    # globe
    gx, gy, r = cx + 2.4, cy - 0.6, 2.9
    ax.add_patch(Circle((gx, gy), r, fc=WHITE, ec=ORANGE, lw=1.8, zorder=5))
    ax.add_patch(Ellipse((gx, gy), r * 1.0, r * 2, fc="none", ec=ORANGE, lw=1.0, zorder=6))
    ax.plot([gx, gx], [gy - r, gy + r], color=ORANGE, lw=1.0, zorder=6)
    ax.plot([gx - r, gx + r], [gy, gy], color=ORANGE, lw=1.0, zorder=6)
    for t in (-1.4, 1.4):
        half = (r ** 2 - t ** 2) ** 0.5
        ax.plot([gx - half, gx + half], [gy + t, gy + t], color=ORANGE, lw=0.8, zorder=6)


# ---------------------------------------------------------------- tiles
STEPS = [
    dict(icon=icon_search, title="1  Search", llm=False,
         lines=["Europe PMC", "\"AI\" OR \"machine learning\""],
         big="876k", big_sub="papers screened"),
    dict(icon=icon_classify, title="2  Classify", llm=True,
         lines=["Does the paper", "apply AI/ML?  yes / no"],
         big="367k", big_sub="say yes",
         tokens=("~8,700 in", "~170 out"),
         prompt="classification prompt v1 (39 kB)"),
    dict(icon=icon_enrich, title="3  Enrich", llm=True,
         lines=["Tag: field, learning type,", "model family, model type"],
         big="~1%", big_sub="done (4 journals)",
         tokens=("~3,150 in", "~1,480 out"),
         prompt="enrichment prompt e1 (12 kB)"),
    dict(icon=icon_terms, title="4  Standard terms", llm=False,
         lines=["EDAM  ·  MeSH", "AI Ontology"],
         big="OLS + ZOOMA", big_sub="EMBL-EBI tools"),
    dict(icon=icon_website, title="5  Open website", llm=False,
         lines=["Search, filter, trends", "open data on Zenodo"],
         big="observatory", big_sub=".dome-ml.org"),
]


def draw_tile(ax, i, s):
    x = tile_x(i)
    cx = x + TILE_W / 2
    llm = s["llm"]
    ax.add_patch(FancyBboxPatch((x, TILE_Y), TILE_W, TILE_H,
                                boxstyle="round,pad=0,rounding_size=1.6",
                                fc=ORANGE_LT if llm else PALE,
                                ec=ORANGE if llm else "#c9d8e0", lw=2.4 if llm else 1.2, zorder=1))
    ax.add_patch(Circle((cx, ICON_Y), ICON_R + 0.6, fc=WHITE, ec=ORANGE if llm else "#c9d8e0",
                        lw=1.6, zorder=2))
    s["icon"](ax, cx, ICON_Y)
    if llm:
        ax.add_patch(FancyBboxPatch((x + TILE_W - 6.6, TILE_Y + TILE_H - 3.6), 5.4, 2.4,
                                    boxstyle="round,pad=0,rounding_size=0.8",
                                    fc=ORANGE, ec=ORANGE, zorder=9))
        text(ax, x + TILE_W - 3.9, TILE_Y + TILE_H - 2.4, "LLM", 9.5, WHITE, "bold", zorder=10)

    y = ICON_Y - ICON_R - 3.0
    text(ax, cx, y, s["title"], 13.5 if len(s["title"]) < 15 else 12.5, NAVY, "bold")
    y -= 3.4
    for ln in s["lines"]:
        text(ax, cx, y, ln, 9.5, GREY)
        y -= 2.3
    y -= 1.6
    big_size = 17 if len(s["big"]) <= 5 else 12.5
    text(ax, cx, y, s["big"], big_size, ORANGE_DK if llm else NAVY, "bold")
    y -= 3.0 if big_size > 13 else 2.6
    text(ax, cx, y, s["big_sub"], 9.5, GREY)

    if llm:
        by, bh = TILE_Y + 1.2, 7.4
        ax.add_patch(FancyBboxPatch((x + 1.2, by), TILE_W - 2.4, bh,
                                    boxstyle="round,pad=0,rounding_size=1.0",
                                    fc=WHITE, ec=ORANGE, lw=1.2, zorder=3))
        text(ax, cx, by + bh - 1.5, "tokens per paper (DeepSeek)", 8.5, GREY, zorder=4)
        text(ax, cx, by + bh - 3.9, f"{s['tokens'][0]} · {s['tokens'][1]}", 10, NAVY, "bold", zorder=4)
        text(ax, cx, by + 1.3, s["prompt"], 7.8, GREY, style="italic", zorder=4)


def main():
    fig = plt.figure(figsize=(W / 10, H / 10), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    text(ax, W / 2, H - 3.3, "DOME ML Observatory: how papers become a searchable map of applied AI/ML",
         15, NAVY, "bold")
    text(ax, W / 2, H - 6.6, "Two steps use an LLM (orange). These are the steps EMBL-EBI local models could run.",
         10.5, GREY)

    for i, s in enumerate(STEPS):
        draw_tile(ax, i, s)
    for i in range(4):                                    # arrows between tiles
        x1 = tile_x(i) + TILE_W + 0.3
        x2 = tile_x(i + 1) - 0.3
        ax.add_patch(FancyArrowPatch((x1, ICON_Y), (x2, ICON_Y), arrowstyle="-|>",
                                     mutation_scale=16, lw=2.2, color=NAVY, zorder=0))

    # bracket under the two LLM tiles + validation note (left side)
    bx1, bx2, by = tile_x(1) + 1.0, tile_x(2) + TILE_W - 1.0, TILE_Y - 1.6
    ax.plot([bx1, bx1, bx2, bx2], [by + 0.9, by, by, by + 0.9], color=ORANGE, lw=1.8)
    lx = (tile_x(0) + tile_x(2) + TILE_W) / 2
    text(ax, lx, by - 2.4, "Classify vs experts (1,000 papers): 91% agree (95% CI 89–93%)", 9, GREEN, "bold")
    text(ax, lx, by - 4.6, "→ 99% (95% CI 98.2–99.5%) after re-checking each disagreement*", 9, GREEN)
    text(ax, lx, by - 6.8, "*the reviewer saw the model's answer, so the 99% is not independent", 8, GREY)
    text(ax, lx, by - 9.2, "DeepSeek runs (cloud API): classify at 400 parallel requests", 8.8, NAVY, "bold")
    text(ax, lx, by - 11.3, "enrich at 800 parallel → 418 papers/min  (53/min at 40 parallel)", 8.8, NAVY, "bold")

    # experimental GLM-5.3 box (right side, under tiles 4-5)
    gx0, gx1 = tile_x(3), tile_x(4) + TILE_W
    gy0, gy1 = 2.0, TILE_Y - 2.0
    rx = (gx0 + gx1) / 2
    ax.add_patch(FancyBboxPatch((gx0, gy0), gx1 - gx0, gy1 - gy0,
                                boxstyle="round,pad=0,rounding_size=1.4",
                                fc=WHITE, ec=ORANGE, lw=1.6, ls=(0, (4, 2.5)), zorder=1))
    ax.add_patch(FancyBboxPatch((gx0 + 1.4, gy1 - 3.3), 13.6, 2.3,
                                boxstyle="round,pad=0,rounding_size=0.8", fc=ORANGE, ec=ORANGE, zorder=2))
    text(ax, gx0 + 8.2, gy1 - 2.15, "EXPERIMENTAL", 8, WHITE, "bold", zorder=3)
    text(ax, gx0 + 16.4, gy1 - 2.15, "Enrich with GLM-5.3-Flash", 10.5, NAVY, "bold", ha="left")
    text(ax, rx, gy1 - 5.0, "same prompt e1  ·  350 papers  ·  Z.ai cloud API", 8.5, GREY)
    text(ax, rx, gy1 - 7.6, "~3,100 in  ·  ~350 out", 12.5, NAVY, "bold")
    text(ax, rx, gy1 - 9.7, "tokens per paper   (DeepSeek: ~3,150 in · ~1,480 out)", 8.5, GREY)
    text(ax, rx, gy1 - 11.9, "~4× fewer output tokens  ·  230–300/min at 50 parallel", 9, ORANGE_DK, "bold")

    common = dict(facecolor=WHITE)
    fig.savefig(OUT / "pipeline_figure.png", dpi=300,
                metadata={"Software": None}, **common)
    fig.savefig(OUT / "pipeline_figure.svg",
                metadata={"Date": None, "Creator": None}, **common)
    plt.close(fig)
    print("wrote", OUT / "pipeline_figure.png", "and", OUT / "pipeline_figure.svg")


if __name__ == "__main__":
    main()
