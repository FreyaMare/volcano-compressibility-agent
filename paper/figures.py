"""Manuscript figures (PNG 300 dpi + PDF). Run after experiments.py."""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(OUT, "results.json")))

INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#ffffff"
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "legend.frameon": False, "figure.dpi": 150, "savefig.dpi": 300, "axes.titlesize": 8.5,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK})


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), bbox_inches="tight", facecolor="white")
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ===================================================================== Fig. 1 architecture
def box(ax, x, y, w, h, title, body, fc, ec):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012",
                                fc=fc, ec=ec, lw=0.9))
    ax.text(x + 0.012, y + h - 0.022, title, fontsize=7.6, fontweight="bold", color=INK, va="top")
    ax.text(x + 0.012, y + h - 0.062, body, fontsize=6.5, color=INK2, va="top", linespacing=1.32)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9, shrinkA=0, shrinkB=0, mutation_scale=8))


fig = plt.figure(figsize=(7.1, 3.75))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
LLM_FC, LLM_EC = "#eef4fc", "#86b6ef"
DET_FC, DET_EC = "#f4f3f0", "#b9b8b2"
HUM_FC, HUM_EC = "#fdf0ea", "#f2a07c"
# colour key
kx = 0.012
for fc, ec, lab in ((LLM_FC, LLM_EC, "language model (Claude; stochastic, every value sourced)"),
                    (DET_FC, DET_EC, "deterministic code (version-pinned, tested)"),
                    (HUM_FC, HUM_EC, "user")):
    ax.add_patch(FancyBboxPatch((kx, 0.945), 0.022, 0.032, boxstyle="round,pad=0.002,rounding_size=0.006", fc=fc, ec=ec, lw=0.9))
    ax.text(kx + 0.03, 0.961, lab, fontsize=6.8, color=INK2, va="center")
    kx += 0.03 + 0.0105 * len(lab) * 0.62 + 0.03
H1, Y1 = 0.30, 0.585
H2, Y2 = 0.36, 0.155
box(ax, 0.012, Y1, 0.17, H1, "Volcano name", "free text typed by\nthe user, e.g.\n'Campi Flegrei'", HUM_FC, HUM_EC)
box(ax, 0.215, Y1, 0.235, H1, "1  Literature research",
    "3 stages, each a Claude session\nwith web search + page fetch:\nS1 system, magmas, levels\nS2 unrest, published source\nS3 petrology, one run per magma",
    LLM_FC, LLM_EC)
box(ax, 0.483, Y1, 0.235, H1, "2  Structured submission",
    "a 'submit' tool with a JSON\nschema; every number has a\nvalue, range, source and status:\nM measured · U detection limit\nA adopted · D not found", LLM_FC, LLM_EC)
box(ax, 0.752, Y1, 0.236, H1, "3  Review (optional)",
    "the user inspects and edits\nvalues, status and sources;\nthe dataset is saved as JSON,\nso re-runs cost no research", HUM_FC, HUM_EC)
ym = Y1 + H1 / 2
arrow(ax, 0.182, ym, 0.215, ym); arrow(ax, 0.45, ym, 0.483, ym); arrow(ax, 0.718, ym, 0.752, ym)
box(ax, 0.752, Y2, 0.236, H2, "4  finalize()",
    "unit and range checks\n(K→°C, Pa→GPa, signs, axes)\ndepth–pressure consistency\nmissing values → defaults (D)\nevery change logged as a\ncaveat in the report", DET_FC, DET_EC)
box(ax, 0.483, Y2, 0.235, H2, "5  Seven-step chain",
    "P = ρgz → EVo (Psat, φ, f_i)\n→ βm (frozen, equilibrium)\n→ βc (sphere, spheroid, crack)\n→ rV → ΔVc = Ve / rV\n→ uz (Mogi, Yang, Fialko)\nthesis reproduced to 3×10⁻⁷", DET_FC, DET_EC)
box(ax, 0.215, Y2, 0.235, H2, "6  Analyses",
    "inverse: Ve and ΔP for 10 mm\nthin-crack and 10 MPa screens\nclosed-form verification\nconsistency with published source\nsensitivity: volatiles, datum,\nH₂O, ρ, fO₂, aspect, μ, ν", DET_FC, DET_EC)
box(ax, 0.012, Y2, 0.17, H2, "7  Report",
    "rounded facts → Claude\nwrites prose only\n(no web, forced output)\nnumber audit\nPDF with tables, figures,\nprovenance appendix", LLM_FC, LLM_EC)
yb = Y2 + H2 / 2
arrow(ax, 0.87, Y1, 0.87, Y2 + H2); arrow(ax, 0.752, yb, 0.718, yb)
arrow(ax, 0.483, yb, 0.45, yb); arrow(ax, 0.215, yb, 0.182, yb)
ax.text(0.012, 0.115, "The language model sets no number used in a calculation: it proposes sourced inputs (1–2) and writes prose (7).\n"
        "Every value in the report comes from the deterministic engine (4–6); the audit lists any number in the text it cannot match.",
        fontsize=6.6, color=INK2, va="top", linespacing=1.35)
save(fig, "fig1_architecture")

# ===================================================================== Fig. 2 regression
reg = R["regression"]
labels = [l.replace("Published source geometry (prolate spheroid)", "2021 source (spheroid)")
           .replace("Penny crack a = ", "Crack a=").replace("Mogi sphere, ", "Mogi ") for l in reg["labels"]]
rv = np.abs(np.array(reg["rel_rv"])); uz = np.abs(np.array(reg["rel_uz"]))
fig, ax = plt.subplots(figsize=(7.1, 2.7))
x = np.arange(len(labels))
floor = 1e-10
ax.axhline(1e-5, color=ORANGE, lw=1.0)
ax.text(len(labels) - 0.6, 1.25e-5, "test tolerance 10⁻⁵", color=INK2, fontsize=7, ha="right", va="bottom")
ax.scatter(x - 0.13, np.maximum(rv, floor), s=26, color=BLUE, edgecolor="white", linewidth=1.2, zorder=3, label="volume-partitioning factor rV")
ax.scatter(x + 0.13, np.maximum(uz, floor), s=26, color=AQUA, marker="s", edgecolor="white", linewidth=1.2, zorder=3, label="central uplift (largest injection)")
ax.set_yscale("log"); ax.set_ylim(3e-11, 3e-4)
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=6.8)
ax.set_ylabel("|engine / thesis − 1|")
ax.legend(loc="upper left", fontsize=7, ncol=2, handletextpad=0.3)
ax.grid(axis="x", visible=False)
ax.set_title("Generalised engine vs published thesis values, La Fossa, 13 configurations")
save(fig, "fig2_regression")

# ===================================================================== Fig. 4 value of literature data
vd = R["value_of_data"]
keys = list(vd)
v0 = vd[keys[0]]
lab0 = [l.replace("Published source geometry (prolate spheroid)", "2021 source (spheroid, 0.6 km)")
         .replace("Penny crack a = ", "Crack a=").replace("Mogi sphere, ", "Mogi ") for l in v0["labels"]]
order = np.argsort([(-1 if f == "source" else d) for f, d in zip(v0["family"], v0["depth"])], kind="stable")
fig, ax = plt.subplots(figsize=(4.6, 3.6))
y = np.arange(len(order))[::-1]
series = [(keys[1], BLUE, "o", "no melt-inclusion volatiles (defaults)"),
          (keys[3], ORANGE, "D", "rock names only (generic compositions)")]
ax.axvline(1.0, color=MUTED, lw=0.9)
for k, (key, col, mk, lab) in enumerate(series):
    ratio = np.array(vd[key]["rv"]) / np.array(v0["rv"])
    ax.scatter(ratio[order], y + (0.14 if k == 0 else -0.14), s=26, color=col, marker=mk, edgecolor="white",
               linewidth=1.2, zorder=3, label=lab)
ax.set_yticks(y); ax.set_yticklabels([lab0[i] for i in order], fontsize=6.8)
ax.set_xscale("log"); ax.set_xlim(0.9, 2.4)
ax.set_xticks([1, 1.25, 1.5, 2]); ax.set_xticklabels(["1", "1.25", "1.5", "2"])
ax.set_xlabel("rV with defaults / rV with literature data")
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right", fontsize=6.6, handletextpad=0.3)
src_ratio = vd[keys[1]]["rv"][3] / v0["rv"][3]
ax.annotate(f"×{src_ratio:.2f}", xy=(src_ratio, y[list(order).index(3)] + 0.14), xytext=(-30, -2),
            textcoords="offset points", fontsize=7, color=INK2)
ax.set_title("Replacing literature inputs by generic defaults")
save(fig, "fig4_value_of_data")
print("ok")
