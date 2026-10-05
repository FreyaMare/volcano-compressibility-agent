"""Report figures (PNG bytes), in the style of the thesis figures."""
from __future__ import annotations

import io

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import physics as ph  # noqa: E402

plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.linewidth": 0.8,
                     "xtick.direction": "in", "ytick.direction": "in", "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})
PAL = ["#2e8b57", "#c0392b", "#e08b1e", "#2c6fbb", "#7d3c98", "#7f8c8d"]
SRC_COL = "#7d3c98"


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=170)
    plt.close(fig)
    return buf.getvalue()


def _depth_colours(res):
    depths = sorted(res[res.family == "level"].depth_km.unique())
    return {d: PAL[i % len(PAL)] for i, d in enumerate(depths)}


def plumbing(ds, R) -> bytes:
    """Schematic cross-section of the modelled storage levels (depth to scale)."""
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    zmax = max(L.depth_km.value for L in ds.levels) * 1.18
    elev = (ds.summit_elevation_m.v(0) or 0) / 1000.0
    x = np.linspace(-6, 6, 200)
    topo = np.maximum(0, elev * (1 - (np.abs(x) / 3.0) ** 1.5))
    ax.fill_between(x, -topo, zmax, color="#f3efe6", zorder=0)
    ax.plot(x, -topo, color="k", lw=1)
    ax.axhline(0, color="#2c6fbb", lw=0.6, ls="--")
    ax.text(5.8, -0.05, "sea level", ha="right", va="bottom", fontsize=7, color="#2c6fbb")
    states = R["states"]
    for i, L in enumerate(ds.levels):
        z = L.depth_km.value
        w = 1.2 + 0.35 * i
        ax.add_patch(matplotlib.patches.Ellipse((0, z), 2 * w, 0.06 * zmax + 0.25, color="#c0392b", alpha=0.75, zorder=3))
        row = states[(states.level == L.name) & (states.role == "resident")]
        P = row.P_MPa.values[0] if len(row) else np.nan
        ax.text(w + 0.3, z, f"{L.name}\n{z:g} km · {P:.0f} MPa · {L.resident.lower()}", va="center", fontsize=7)
    src = ds.deformation_source
    if src is not None:
        z = src.depth_km.value
        ax.add_patch(matplotlib.patches.Ellipse((0, z), 0.5, max(0.04 * zmax, 0.15), color=SRC_COL, zorder=4))
        ax.text(-0.5, z, f"published source\n{z:g} km", ha="right", va="center", fontsize=7, color=SRC_COL)
    for i in range(len(ds.levels) - 1):
        z1, z2 = ds.levels[i].depth_km.value, ds.levels[i + 1].depth_km.value
        ax.annotate("", xy=(0, z1 + 0.15), xytext=(0, z2 - 0.15),
                    arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2))
    ax.set_ylim(zmax, -max(elev, 0.3) * 1.6)
    ax.set_xlim(-6, 6)
    ax.set_xlabel("horizontal distance (schematic)")
    ax.set_ylabel("depth (km)")
    ax.set_xticks([])
    ax.set_title(f"Modelled storage levels beneath {ds.name}", fontsize=9)
    return _png(fig)


def rv_bars(R, thin) -> bytes:
    res = R["res"]
    flagged = set(thin[thin.status == "violated"].label)
    labels, vals, cols, hatch = [], [], [], []
    for _, r in res.iterrows():
        labels.append(r.label)
        vals.append(r.rV)
        cols.append(SRC_COL if r.family == "source" else PAL[["MOGI", "PENNY"].index(r.model) if r.model in ("MOGI", "PENNY") else 2])
        hatch.append("///" if r.label in flagged else "")
        if r.family == "source" and r.phi > 0:
            labels.append(r.label + " (equilibrium)")
            vals.append(r.rV_eq)
            cols.append("#b48ad1")
            hatch.append("")
    fig, ax = plt.subplots(figsize=(6.4, 0.28 * len(vals) + 1.0))
    y = np.arange(len(vals))[::-1]
    for yi, v, c, h in zip(y, vals, cols, hatch):
        ax.barh(yi, v, color=c, hatch=h, edgecolor="white" if not h else "k", linewidth=0.4)
        ax.text(v * 1.08, yi, f"{v:.2f}", va="center", fontsize=7)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xscale("log")
    ax.set_xlim(0.8, max(vals) * 4)
    ax.axvline(1, color="k", lw=0.6)
    ax.set_xlabel("volume-partitioning factor $r_V = 1 + β_m/β_c$")
    sec = ax.secondary_xaxis("top", functions=(lambda v: 100 / np.maximum(v, 1e-9), lambda f: 100 / np.maximum(f, 1e-9)))
    sec.set_xlabel("fraction of the injection expressed as cavity-volume change (%)", fontsize=7.5)
    return _png(fig)


def profiles(an, R, thin) -> bytes:
    res = R["res"]
    cfgs = {c.label: c for c in an.configs()}
    flagged = set(thin[thin.status == "violated"].label)
    col = _depth_colours(res)
    r = np.linspace(0, 6000, 121)
    has_src = (res.family == "source").any()
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 5.6))
    ax = axs[0, 0]
    for _, row in res[(res.model == "MOGI") & (res.family == "level")].iterrows():
        u = an.uplift(cfgs[row.label], row.Ve3_m3 / row.rV, r) * 1e3
        ax.plot(r / 1e3, u, color=col[row.depth_km], label=f"{row.depth_km:g} km")
    ax.set_title("(a) Mogi spheres, $V_e$ = 10$^7$ m³", fontsize=8.5)
    ax.legend(fontsize=7, frameon=False)
    ax = axs[0, 1]
    for _, row in res[(res.model == "PENNY") & (res.family == "level")].iterrows():
        u = an.uplift(cfgs[row.label], row.Ve3_m3 / row.rV, r) * 1e3
        fl = row.label in flagged
        ax.plot(r / 1e3, u, color=col[row.depth_km], alpha=0.3 if fl else 1, lw=0.8 if fl else 1.3,
                ls=["-", "--", ":", "-."][list(sorted(res.penny_radius_km.dropna().unique())).index(row.penny_radius_km) % 4])
    radii = list(sorted(res.penny_radius_km.dropna().unique()))
    for i, a in enumerate(radii):
        ax.plot([], [], color="0.3", ls=["-", "--", ":", "-."][i % 4], label=f"a = {a:g} km")
    ax.legend(fontsize=6.5, frameon=False, title="colour = depth", title_fontsize=6.5)
    ax.set_title("(b) penny cracks (faint: thin-crack condition violated)", fontsize=8.5)
    ax = axs[1, 0]
    if has_src:
        src = res[res.family == "source"].iloc[0]
        c = cfgs[src.label]
        for _, d in R.get("datum", []).iterrows() if "datum" in R else []:
            dVc = d.Ve_max / d.rV
            u = an.uplift(c, dVc, r) * 1e3
            ax.plot(r / 1e3, u, label=f"{d.datum} (frozen)")
        if "datum" in R:
            d0 = R["datum"].iloc[0]
            ax.plot(r / 1e3, an.uplift(c, d0.Ve_max / d0.rV_eq, r) * 1e3, "k--", lw=0.9, label="sea-level datum, equilibrium")
        ax.set_title(f"(c) published source geometry, $V_e$ = {src.Ve3_m3:.0e} m³", fontsize=8.5)
        ax.legend(fontsize=6.5, frameon=False)
        ax.set_xlim(0, 3)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "No published analytical\ndeformation source", ha="center", va="center", transform=ax.transAxes)
    ax = axs[1, 1]
    for _, row in res.iterrows():
        if row.label in flagged:
            continue
        u = an.uplift(cfgs[row.label], 1.0, r)
        c = SRC_COL if row.family == "source" else col[row.depth_km]
        ax.plot(r / 1e3, u / u[0], color=c, lw=1, ls="-" if row.model != "PENNY" else "--")
    ax.set_title("(d) profiles normalised to their central value", fontsize=8.5)
    for a in axs.ravel():
        if a.axison:
            a.set_xlabel("radial distance (km)")
            a.set_ylabel("vertical uplift (mm)" if a is not axs[1, 1] else "$u_z(r)/u_z(0)$")
    fig.tight_layout()
    return _png(fig)


def inverse(R) -> bytes:
    inv = R["inverse"]
    fig, ax = plt.subplots(figsize=(6.4, 0.28 * len(inv) + 1.0))
    y = np.arange(len(inv))[::-1]
    for yi, (_, d) in zip(y, inv.iterrows()):
        c = SRC_COL if d.family == "source" else PAL[0 if d.model == "MOGI" else 3]
        ax.barh(yi, d.Ve, color=c, edgecolor="k" if not d.within_screen else "white",
                linewidth=1.2 if not d.within_screen else 0.3, alpha=0.6 if d.branch == "equilibrium" else 1)
        ax.text(d.Ve * 1.15, yi, f"ΔP = {d.dP_MPa:.2f} MPa", va="center", fontsize=6.5)
    lab = [f"{d.label}" + (" [equilibrium]" if d.branch == "equilibrium" else "") for _, d in inv.iterrows()]
    ax.set_yticks(y)
    ax.set_yticklabels(lab, fontsize=7)
    ax.set_xscale("log")
    ax.set_xlim(inv.Ve.min() / 3, inv.Ve.max() * 30)
    ax.axvline(1e6, color="k", ls=":", lw=0.7)
    ax.set_xlabel(f"injected volume required for {R['target_mm']:g} mm of central uplift (m³)")
    return _png(fig)


def sensitivity(R) -> bytes:
    has_datum = "h2o_datum" in R
    fig, axs = plt.subplots(1, 2 if has_datum else 1, figsize=(7.2 if has_datum else 4, 3.2))
    axs = np.atleast_1d(axs)
    ax = axs[0]
    b = R["scenario_b"]
    for i, (lev, g) in enumerate(b.groupby("depth_km", sort=True)):
        ax.plot(g.H2O_multiplier, g.rV, "o-", color=PAL[i % len(PAL)], label=f"{lev:g} km ({g.magma.iloc[0].lower()})")
        for _, r in g.iterrows():
            if r.phi > 0:
                ax.annotate(f"{100 * r.phi:.1f}%", (r.H2O_multiplier, r.rV), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("assumed H$_2$O / Scenario A value")
    ax.set_ylabel("$r_V$ (Mogi reservoir)")
    ax.set_title("(a) volatile budget (labels: exsolved gas vol%)", fontsize=8.5)
    ax.legend(fontsize=7, frameon=False)
    if has_datum:
        ax = axs[1]
        g = R["h2o_datum"]
        for i, (h, gg) in enumerate(g.groupby("H2O_wt")):
            ax.plot(gg.P_MPa, gg.rV, "o-", color=PAL[i], label=f"{h:.2f} wt% frozen")
            ax.plot(gg.P_MPa, gg.rV_eq, "s--", color=PAL[i], alpha=0.6, label=f"{h:.2f} wt% equilibrium")
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.set_xlabel("pressure of the shallow source (MPa) — set by the datum")
        ax.set_ylabel("$r_V$")
        ax.set_title("(b) pressure datum × dissolved H$_2$O, shallow source", fontsize=8.5)
        ax.legend(fontsize=6, frameon=False)
    fig.tight_layout()
    return _png(fig)


def source_map(an, R) -> bytes | None:
    res = R["res"]
    if not (res.family == "source").any():
        return None
    row = res[res.family == "source"].iloc[0]
    c = [x for x in an.configs() if x.family == "source"][0]
    ds = an.ds
    dV = ds.deformation_source.dV_m3.v(None) or row.Ve1_m3 / row.rV
    L = max(1500.0, 2.5 * c.depth_km * 1e3)
    g = np.linspace(-L, L, 81)
    X, Y = np.meshgrid(g, g)
    if c.model == "YANG":
        W = ph.uplift_yang_map(dV, c.V0, c.aspect, c.depth_km * 1e3, c.mu, c.nu, c.dip, c.strike, X, Y) * 1e3
    else:
        Rr = np.hypot(X, Y)
        W = an.uplift(c, dV, Rr.ravel()).reshape(X.shape) * 1e3
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    cs = ax.contourf(X / 1e3, Y / 1e3, W, levels=14, cmap="viridis")
    ax.contour(X / 1e3, Y / 1e3, W, levels=8, colors="w", linewidths=0.4)
    fig.colorbar(cs, ax=ax, label="vertical uplift (mm)")
    i = int(np.argmax(W))
    ax.plot(X.ravel()[i] / 1e3, Y.ravel()[i] / 1e3, "r^", ms=6)
    ax.plot(0, 0, "w+", ms=8)
    ax.set_aspect("equal")
    ax.set_xlabel("east (km)")
    ax.set_ylabel("north (km)")
    ax.set_title(f"ΔV$_c$ = {dV:,.0f} m³; maximum {W.max():.1f} mm (▲)", fontsize=8)
    return _png(fig)
