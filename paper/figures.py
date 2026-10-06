"""Manuscript figures, three-dimensional versions (PNG 300 dpi + PDF). Run after experiments.py:

    python paper/figures.py

Figure 1  surface uplift above the 2021 La Fossa source for the same injected volume, without and with
          volume partitioning (computed here with the engine's Yang source)
Figure 2  architecture, drawn as extruded blocks
Figure 3  regression against the thesis: digits of agreement as 3-D bars, pale below the test tolerance
Figure 4  value of the literature data: change in rV when inputs are replaced by defaults, 3-D bars

Palette (validated for colour-vision deficiency, all pairs): lava #d24418, indigo #4b3fbf, teal #0a8f9c.
"""
import json
import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LightSource, LinearSegmentedColormap, to_rgb  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)
sys.path.insert(0, ROOT)
R = json.load(open(os.path.join(OUT, "results.json")))

# ----------------------------------------------------------------------------- style
INK, INK2, MUTED, GRID = "#16161a", "#4a4a52", "#8c8c94", "#e4e4e8"
LAVA, INDIGO, TEAL = "#d24418", "#4b3fbf", "#0a8f9c"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "axes.edgecolor": MUTED, "figure.dpi": 150, "savefig.dpi": 300,
    "axes.titlesize": 8.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "legend.frameon": False})
LAVA_RAMP = LinearSegmentedColormap.from_list("lava", ["#fde8dc", "#f6a982", "#e5703f", LAVA, "#8e2a0b", "#521704"])


def mix(c, other, t):
    """Blend colour c towards other by fraction t."""
    a, b = np.array(to_rgb(c)), np.array(to_rgb(other))
    return tuple(a + (b - a) * t)


def save(fig, name, tight=True):
    """tight=False keeps the figure frame: 3-D axes larger than the figure would otherwise pad the crop."""
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), bbox_inches="tight" if tight else None,
                    pad_inches=0.05, facecolor="white")
    plt.close(fig)


def style3d(ax):
    ax.set_proj_type("ortho")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((0.975, 0.975, 0.98, 1.0))
        axis.pane.set_edgecolor(GRID)
        axis._axinfo["grid"].update(color=GRID, linewidth=0.5)
        axis.line.set_color(MUTED)
    ax.tick_params(axis="both", which="major", labelsize=6.6, pad=0)


# short configuration codes, in the order of the thesis tables
CODES = ["M 2", "M 5", "M 12", "S 0.6", "C0.5 2", "C0.5 5", "C0.5 12", "C1 2", "C1 5", "C1 12", "C2 2", "C2 5", "C2 12"]
CODE_NOTE = "S = 2021 source (spheroid); M = Mogi sphere; C0.5, C1, C2 = penny crack of radius 0.5, 1, 2 km; number = depth (km)."


# ============================================================================ Figure 2 (architecture)
def block(ax, x, y, w, h, title, body, base, depth=(0.012, 0.022), band=True):
    """A box extruded towards the upper right: shaded top and side faces, text on the front face."""
    dx, dy = depth
    front = mix(base, "white", 0.86)
    top = mix(base, "white", 0.55)
    side = mix(base, "black", 0.05)
    edge = mix(base, "black", 0.25)
    ax.add_patch(Polygon([(x, y + h), (x + dx, y + h + dy), (x + w + dx, y + h + dy), (x + w, y + h)],
                         closed=True, fc=top, ec=edge, lw=0.7, zorder=2))
    ax.add_patch(Polygon([(x + w, y), (x + w + dx, y + dy), (x + w + dx, y + h + dy), (x + w, y + h)],
                         closed=True, fc=side, ec=edge, lw=0.7, zorder=2))
    ax.add_patch(Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True, fc=front, ec=edge,
                         lw=0.8, zorder=3))
    if band:
        ax.add_patch(Polygon([(x, y + h - 0.052), (x + w, y + h - 0.052), (x + w, y + h), (x, y + h)], closed=True,
                             fc=mix(base, "white", 0.70), ec=mix(base, "black", 0.25), lw=0.8, zorder=3))
    ax.text(x + 0.011, y + h - 0.026, title, fontsize=7.5, fontweight="bold", color=mix(base, "black", 0.45),
            va="center", zorder=4)
    ax.text(x + 0.011, y + h - 0.068, body, fontsize=6.4, color=INK2, va="top", linespacing=1.32, zorder=4)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=5,
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=9))


def fig_architecture():
    fig = plt.figure(figsize=(7.1, 3.9))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    kx = 0.012
    for base, lab in ((INDIGO, "language model (Claude; stochastic, every value sourced)"),
                      (TEAL, "deterministic code (version-pinned, tested)"), (LAVA, "user")):
        block(ax, kx, 0.948, 0.022, 0.03, "", "", base, depth=(0.005, 0.009), band=False)
        ax.text(kx + 0.034, 0.963, lab, fontsize=6.8, color=INK2, va="center")
        kx += 0.034 + 0.0108 * len(lab) * 0.6 + 0.03
    H1, Y1, H2, Y2 = 0.30, 0.575, 0.36, 0.15
    block(ax, 0.012, Y1, 0.165, H1, "Volcano name", "free text typed by\nthe user, e.g.\n'Campi Flegrei'", LAVA)
    block(ax, 0.212, Y1, 0.232, H1, "1  Literature research",
          "3 stages, each a Claude session\nwith web search + page fetch:\nS1 system, magmas, levels\n"
          "S2 unrest, published source\nS3 petrology, one run per magma", INDIGO)
    block(ax, 0.479, Y1, 0.232, H1, "2  Structured submission",
          "a 'submit' tool with a JSON\nschema; every number has a\nvalue, range, source and status:\n"
          "M measured · U detection limit\nA adopted · D not found", INDIGO)
    block(ax, 0.746, Y1, 0.226, H1, "3  Review (optional)",
          "the user inspects and edits\nvalues, status and sources;\nthe dataset is saved as JSON,\n"
          "so re-runs cost no research", LAVA)
    ym = Y1 + H1 / 2
    arrow(ax, 0.189, ym, 0.212, ym)
    arrow(ax, 0.456, ym, 0.479, ym)
    arrow(ax, 0.723, ym, 0.746, ym)
    block(ax, 0.746, Y2, 0.226, H2, "4  finalize()",
          "unit and range checks\n(K→°C, Pa→GPa, signs, axes)\ndepth–pressure consistency\n"
          "missing values → defaults (D)\nevery change logged as a\ncaveat in the report", TEAL)
    block(ax, 0.479, Y2, 0.232, H2, "5  Seven-step chain",
          "P = ρgz → EVo (Psat, φ, f_i)\n→ βm (frozen, equilibrium)\n→ βc (sphere, spheroid, crack)\n"
          "→ rV → ΔVc = Ve / rV\n→ uz (Mogi, Yang, Fialko)\nthesis reproduced to 3×10⁻⁷", TEAL)
    block(ax, 0.212, Y2, 0.232, H2, "6  Analyses",
          "inverse: Ve and ΔP for 10 mm\nthin-crack and 10 MPa screens\nclosed-form verification\n"
          "consistency with published source\nsensitivity: volatiles, datum,\nH₂O, ρ, fO₂, aspect, μ, ν", TEAL)
    block(ax, 0.012, Y2, 0.165, H2, "7  Report",
          "rounded facts → Claude\nwrites prose only\n(no web, forced output)\nnumber audit\n"
          "PDF: tables, figures,\nprovenance appendix", INDIGO)
    yb = Y2 + H2 / 2
    arrow(ax, 0.859, Y1, 0.859, Y2 + H2 + 0.022)
    arrow(ax, 0.746, yb, 0.723, yb)
    arrow(ax, 0.479, yb, 0.456, yb)
    arrow(ax, 0.212, yb, 0.189, yb)
    ax.text(0.012, 0.105, "The language model sets no number used in a calculation: it proposes sourced inputs (1–2) "
            "and writes prose (7).\nEvery value in the report comes from the deterministic engine (4–6); the audit "
            "lists any number in the text it cannot match.", fontsize=6.6, color=INK2, va="top", linespacing=1.35)
    save(fig, "fig2_architecture")


# ============================================================================ Figure 3 (regression)
LS = LightSource(azdeg=315, altdeg=45)


def bar(ax, x, y, z0, z1, c, dx, dy):
    if z1 - z0 <= 0:
        z1 = z0 + 1e-3
    ax.bar3d(x - dx / 2, y - dy / 2, z0, dx, dy, z1 - z0, color=c, shade=True, lightsource=LS,
             edgecolor=mix(c, "black", 0.35), linewidth=0.3)


def fig_regression():
    reg = R["regression"]
    rv, uz = np.abs(np.array(reg["rel_rv"])), np.abs(np.array(reg["rel_uz"]))
    cap, tol = 10.0, 5.0
    d_rv = np.where(rv > 0, -np.log10(np.where(rv > 0, rv, 1)), cap)
    d_uz = np.where(uz > 0, -np.log10(np.where(uz > 0, uz, 1)), cap)
    n = len(CODES)
    fig = plt.figure(figsize=(7.1, 3.3))
    ax = fig.add_axes([-0.12, -0.36, 1.26, 1.5], projection="3d")
    style3d(ax)
    # one row, a pair of bars per configuration; the part of each bar below the test tolerance is a pale tint
    for i in range(n):
        for off, d, c in ((-0.19, d_rv[i], INDIGO), (0.19, d_uz[i], TEAL)):
            bar(ax, i + off, 0, 0, tol, mix(c, "white", 0.62), 0.34, 0.6)
            bar(ax, i + off, 0, tol, d, c, 0.34, 0.6)
    # tolerance level drawn on the back and side walls
    ax.plot([-0.7, n - 0.3], [0.7, 0.7], [tol, tol], color=LAVA, lw=1.2, ls=(0, (4, 2)))
    ax.plot([-0.7, -0.7], [-0.7, 0.7], [tol, tol], color=LAVA, lw=1.2, ls=(0, (4, 2)))
    ax.text(-0.9, -0.7, tol, "tolerance\n10⁻⁵", color=LAVA, fontsize=6.8, ha="right", va="center", zorder=50)
    i_exact = int(np.argmax(d_rv >= cap))
    ax.text(i_exact - 0.2, 0, cap + 0.35, "exact", color=INK2, fontsize=6.5, ha="center", zorder=50)
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels(CODES, fontsize=6.3)
    ax.set_yticks([])
    ax.set_zticks([0, 2, 4, 6, 8, 10])
    ax.set_zlim(0, 10.6)
    ax.set_xlim(-0.7, n - 0.3)
    ax.set_ylim(-0.7, 0.7)
    ax.set_zlabel("digits of agreement", fontsize=7, labelpad=1)
    ax.set_box_aspect((4.2, 0.55, 1.35))
    ax.view_init(elev=18, azim=-72)
    fig.text(0.04, 0.96, "Generalised engine vs published thesis values, La Fossa, 13 configurations",
             fontsize=8.5, fontweight="bold", color=INK)
    fig.text(0.04, 0.915, "Bar height = −log₁₀ |engine / thesis − 1|. Indigo: volume-partitioning factor rV; "
             "teal: central uplift for the largest injection.", fontsize=6.8, color=INK2)
    fig.text(0.04, 0.88, "Pale part of each bar: below the test tolerance of 10⁻⁵ (five digits). Every bar "
             "exceeds it by at least 1.5 digits.", fontsize=6.8, color=INK2)
    fig.text(0.04, 0.845, CODE_NOTE, fontsize=6.6, color=MUTED)
    save(fig, "fig3_regression", tight=False)


# ============================================================================ Figure 1 (partitioning)
def fig_partitioning():
    from volcano_agent import physics as ph
    src = dict(V0=8.83e6, aspect=59.0 / 595.0, z0=598.0, mu=1e9, nu=0.35, dip=69.0, strike=137.0)
    rv = R["regression"]["rv"][3]                 # computed rV of the 2021 source geometry (frozen branch)
    Ve = 1e5
    g = np.linspace(-2000.0, 2000.0, 141)
    X, Y = np.meshgrid(g, g)
    W1 = ph.uplift_yang_map(Ve, src["V0"], src["aspect"], src["z0"], src["mu"], src["nu"], src["dip"],
                            src["strike"], X, Y) * 1e3
    W2 = W1 / rv
    zmax = float(np.nanmax(W1)) * 1.1
    floor = -0.32 * zmax
    a = ph.yang_semi_major(src["V0"], src["aspect"])
    half = a * np.cos(np.deg2rad(src["dip"]))          # map projection of the long axis (plunge 69°)
    tr = np.deg2rad(src["strike"])
    ex, ey = half * np.sin(tr) / 1e3, half * np.cos(tr) / 1e3
    fig = plt.figure(figsize=(7.1, 3.7))
    shade = LightSource(azdeg=300, altdeg=40)
    for k, (W, title, sub) in enumerate((
            (W1, "(a) No partitioning, rV = 1", "the whole injected volume dilates the cavity"),
            (W2, f"(b) Computed partitioning, rV = {rv:.1f}",
             "gas-bearing rhyolite, frozen branch (hypothetical magmatic end-member)"))):
        ax = fig.add_axes([0.0 + 0.5 * k, 0.03, 0.5, 0.85], projection="3d")
        style3d(ax)
        # map view on the floor: filled uplift contours and the source
        ax.contourf(X / 1e3, Y / 1e3, W, levels=np.linspace(0, zmax, 12), zdir="z", offset=floor,
                    cmap=LAVA_RAMP, alpha=0.85)
        ax.plot([-ex, ex], [-ey, ey], [floor, floor], color=INDIGO, lw=2.4, solid_capstyle="round", zorder=20)
        rgb = shade.shade(np.clip(W / zmax, 0, 1), cmap=LAVA_RAMP, vert_exag=0.6, blend_mode="soft", vmin=0, vmax=1)
        ax.plot_surface(X / 1e3, Y / 1e3, W, facecolors=rgb, rstride=2, cstride=2, linewidth=0,
                        antialiased=True, shade=False)
        i, j = np.unravel_index(np.nanargmax(W), W.shape)
        ax.plot([X[i, j] / 1e3] * 2, [Y[i, j] / 1e3] * 2, [W[i, j], W[i, j] + 0.12 * zmax], color=INK, lw=0.7,
                zorder=60)
        ax.text(X[i, j] / 1e3, Y[i, j] / 1e3, W[i, j] + 0.15 * zmax, f"max {W[i, j]:.1f} mm", color=INK,
                fontsize=7.2, ha="center", fontweight="bold", zorder=60)
        ax.set_zlim(floor, zmax)
        ax.set_zticks([0, 10, 20, 30, 40, 50])
        ax.set_xlabel("east (km)", fontsize=6.8, labelpad=-4)
        ax.set_ylabel("north (km)", fontsize=6.8, labelpad=-4)
        ax.set_zlabel("uplift (mm)", fontsize=6.8, labelpad=-2)
        ax.set_xticks([-2, -1, 0, 1, 2])
        ax.set_yticks([-2, -1, 0, 1, 2])
        ax.set_box_aspect((1, 1, 0.75))
        ax.view_init(elev=24, azim=-58)
        fig.text(0.03 + 0.5 * k, 0.945, title, fontsize=8.2, fontweight="bold", color=INK)
        fig.text(0.03 + 0.5 * k, 0.91, sub, fontsize=6.6, color=INK2)
    fig.text(0.03, 0.012, "Same injected volume Ve = 10⁵ m³ and the same vertical scale in both panels. Floor: the "
             "uplift in map view; indigo line: map projection of the source's long axis\n(0.598 km below sea level, "
             "plunge 69°, trend 137°; Di Traglia et al., 2023). μ = 1 GPa, ν = 0.35. Uplift computed with the "
             "engine's Yang source.", fontsize=6.2, color=MUTED, linespacing=1.3)
    save(fig, "fig1_partitioning_3d")
    return float(W1.max()), float(W2.max()), rv


# ============================================================================ Figure 4
def fig_value_of_data():
    vd = R["value_of_data"]
    keys = list(vd)
    v0 = np.array(vd[keys[0]]["rv"])
    order = [3, 0, 4, 7, 10, 1, 5, 8, 11, 2, 6, 9, 12]           # source, then 2, 5, 12 km
    pct = {k: ((np.array(vd[k]["rv"]) / v0 - 1) * 100)[order] for k in keys[1:]}
    assert np.allclose(pct[keys[1]], pct[keys[2]], atol=1e-6)      # V2 = V1 at every configuration
    rows = [(pct[keys[1]], INDIGO, "V1 = V2"), (pct[keys[3]], LAVA, "V3")]
    n = len(order)
    fig = plt.figure(figsize=(7.1, 3.4))
    ax = fig.add_axes([-0.12, -0.36, 1.26, 1.5], projection="3d")
    style3d(ax)
    ys = [0.0, 1.3]
    for (z, col, _), y in zip(rows, ys):
        for i in range(n):
            bar(ax, i, y, 0, z[i], col, 0.55, 0.55)
    for (z, col, _), y in zip(rows, ys):
        for i in range(n):
            if z[i] >= 1 and (y > 0 or i == 0):
                xo, ha = (i - 0.35, "right") if y == 0 else (i, "center")
                ax.text(xo, y, z[i] + 3.5, f"+{z[i]:.0f}", fontsize=6.6, color=mix(col, "black", 0.35),
                        ha=ha, fontweight="bold", zorder=60)
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels([CODES[i] for i in order], fontsize=6.3)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[2] for r in rows], fontsize=7)
    ax.set_zlabel("change in rV (%)", fontsize=7, labelpad=1)
    ax.set_zlim(0, 95)
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(-0.5, 1.8)
    ax.set_box_aspect((4.6, 0.9, 1.35))
    ax.view_init(elev=20, azim=-66)
    fig.text(0.04, 0.96, "Replacing literature inputs by generic defaults, La Fossa", fontsize=8.5,
             fontweight="bold", color=INK)
    fig.text(0.04, 0.915, "Change in rV (%) relative to the thesis data. Indigo: no melt-inclusion volatiles (V1), "
             "identical when temperatures are also removed (V2).", fontsize=6.8, color=INK2)
    fig.text(0.04, 0.88, "Lava: only the rock names kept (V3). Flat plates: no change (deep, undersaturated "
             "levels). V1 at 2 km: +6%, +6%, +2%, +0.3%.", fontsize=6.8, color=INK2)
    fig.text(0.04, 0.845, CODE_NOTE, fontsize=6.6, color=MUTED)
    save(fig, "fig4_value_of_data", tight=False)


if __name__ == "__main__":
    print("Figure 1 max uplift (mm) without / with partitioning, rV:", fig_partitioning())
    fig_architecture()
    fig_regression()
    fig_value_of_data()
    print("ok")
