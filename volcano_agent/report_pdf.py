"""Assemble the thesis-style PDF report with ReportLab."""
from __future__ import annotations

import datetime as _dt
import html
import io
import os
import re
from typing import List

import matplotlib
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from . import __version__
from . import figures as FIG
from . import templates as T
from .facts import audit_numbers
from .physics import EVO_COMMIT
from .schema import STATUS_LABEL

# ------------------------------------------------------------------------------- fonts
_FD = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("Serif", os.path.join(_FD, "DejaVuSerif.ttf")))
pdfmetrics.registerFont(TTFont("Serif-B", os.path.join(_FD, "DejaVuSerif-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Serif-I", os.path.join(_FD, "DejaVuSerif-Italic.ttf")))
pdfmetrics.registerFont(TTFont("Serif-BI", os.path.join(_FD, "DejaVuSerif-BoldItalic.ttf")))
pdfmetrics.registerFont(TTFont("Sans", os.path.join(_FD, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sans-B", os.path.join(_FD, "DejaVuSans-Bold.ttf")))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402

registerFontFamily("Serif", normal="Serif", bold="Serif-B", italic="Serif-I", boldItalic="Serif-BI")
registerFontFamily("Sans", normal="Sans", bold="Sans-B", italic="Sans", boldItalic="Sans-B")

ACCENT = colors.HexColor("#7a2e1f")
S = {
    "body": ParagraphStyle("body", fontName="Serif", fontSize=9.6, leading=13.6, alignment=TA_JUSTIFY, spaceAfter=6),
    "eq": ParagraphStyle("eq", fontName="Serif", fontSize=9.6, leading=14, alignment=TA_CENTER, spaceBefore=3, spaceAfter=7),
    "h1": ParagraphStyle("h1", fontName="Serif-B", fontSize=16, leading=20, spaceBefore=4, spaceAfter=12, textColor=ACCENT),
    "h2": ParagraphStyle("h2", fontName="Serif-B", fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Serif-BI", fontSize=10, leading=13, spaceBefore=6, spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="Serif", fontSize=8, leading=10.4, alignment=TA_JUSTIFY, spaceBefore=3, spaceAfter=10, textColor=colors.HexColor("#333333")),
    "tcap": ParagraphStyle("tcap", fontName="Serif", fontSize=8, leading=10.4, alignment=TA_JUSTIFY, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#333333")),
    "cell": ParagraphStyle("cell", fontName="Serif", fontSize=7.2, leading=8.8, alignment=TA_LEFT, splitLongWords=0),
    "cellc": ParagraphStyle("cellc", fontName="Serif", fontSize=7.2, leading=8.8, alignment=TA_CENTER),
    "head": ParagraphStyle("head", fontName="Serif-B", fontSize=7.2, leading=8.8, alignment=TA_CENTER, splitLongWords=0),
    "title": ParagraphStyle("title", fontName="Serif-B", fontSize=21, leading=27, alignment=TA_CENTER, textColor=ACCENT),
    "sub": ParagraphStyle("sub", fontName="Serif", fontSize=11, leading=15, alignment=TA_CENTER),
    "small": ParagraphStyle("small", fontName="Serif", fontSize=8, leading=10.5, alignment=TA_JUSTIFY),
    "ref": ParagraphStyle("ref", fontName="Serif", fontSize=8.4, leading=11, leftIndent=14, firstLineIndent=-14, spaceAfter=3),
    "box": ParagraphStyle("box", fontName="Serif", fontSize=8.6, leading=11.6, alignment=TA_JUSTIFY),
    "toc1": ParagraphStyle("toc1", fontName="Serif-B", fontSize=9.5, leading=14),
    "toc2": ParagraphStyle("toc2", fontName="Serif", fontSize=8.8, leading=12, leftIndent=14),
}
W = A4[0] - 4.4 * cm


# ------------------------------------------------------------------------------ helpers
_ALLOWED = ("b", "i", "sub", "sup", "super", "br/")


def clean(text: str) -> str:
    """Escape everything except a small whitelist of inline tags."""
    if text is None:
        return ""
    t = html.escape(str(text), quote=False)
    for tag in _ALLOWED:
        t = t.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t


def sci(v, nd=2):
    if v is None or not np.isfinite(v):
        return "—"
    if v == 0:
        return "0"
    e = int(np.floor(np.log10(abs(v))))
    m = v / 10 ** e
    if abs(round(m, nd)) >= 10:
        m, e = m / 10, e + 1
    if -2 <= e <= 4 and nd >= 2:
        return f"{v:,.{max(0, nd - e)}f}" if e < 3 else f"{v:,.0f}"
    return f"{m:.{nd}f}×10<sup>{e}</sup>".replace("-", "−")


def sci_always(v, nd=2):
    if v is None or not np.isfinite(v):
        return "—"
    if v == 0:
        return "0"
    e = int(np.floor(np.log10(abs(v))))
    m = v / 10 ** e
    if abs(round(m, nd)) >= 10:
        m, e = m / 10, e + 1
    return f"{m:.{nd}f}×10<sup>{e}</sup>".replace("-", "−")


def num(v, nd=2):
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def mm(v):
    a = abs(v)
    if a >= 100:
        return f"{v:.0f}"
    if a >= 1:
        return f"{v:.2f}"
    if a >= 0.01:
        return f"{v:.3f}"
    return f"{v:.1e}"


def qstr(q, nd=3, unit=""):
    if q is None or q.value is None:
        return "—"
    v = q.value
    s = f"{v:.{nd}g}"
    if q.min is not None or q.max is not None:
        s += f" ({q.min:g}–{q.max:g})" if (q.min is not None and q.max is not None) else ""
    return s + (f" {unit}" if unit else "") + f" ({q.status})"


class Doc(SimpleDocTemplate):
    def __init__(self, *a, **k):
        self.volcano = k.pop("volcano")
        super().__init__(*a, **k)

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and getattr(f, "_toc", None):
            lvl, text = f._toc
            key = f"h{id(f)}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (lvl, text, self.page, key))


def _footer(canv, doc):
    canv.saveState()
    canv.setFont("Serif", 7.5)
    canv.setFillColor(colors.HexColor("#555555"))
    canv.drawString(2.2 * cm, 1.3 * cm, f"Magma compressibility and surface deformation — {doc.volcano}")
    canv.drawRightString(A4[0] - 2.2 * cm, 1.3 * cm, str(doc.page))
    canv.restoreState()


class Builder:
    def __init__(self):
        self.story: List = []
        self.nfig = {}
        self.ntab = {}

    def h1(self, t):
        p = Paragraph(clean(t), S["h1"])
        p._toc = (0, t)
        self.story.append(p)

    def h2(self, t):
        p = Paragraph(clean(t), S["h2"])
        p._toc = (1, t)
        self.story.append(p)

    def h3(self, t):
        self.story.append(Paragraph(clean(t), S["h3"]))

    def para(self, t, style="body"):
        self.story.append(Paragraph(t, S[style]))

    def prose(self, text: str, fallback: str = ""):
        text = (text or "").strip() or fallback
        for block in re.split(r"\n\s*\n", text):
            b = block.strip()
            if not b:
                continue
            if b.startswith("## ") or b.startswith("### "):
                lines = b.split("\n", 1)
                self.h3(lines[0].lstrip("#").strip())
                if len(lines) > 1 and lines[1].strip():
                    self.story.append(Paragraph(clean(lines[1].strip()).replace("\n", " "), S["body"]))
            else:
                self.story.append(Paragraph(clean(b).replace("\n", "<br/>" if re.match(r"^\d\.", b) else " "), S["body"]))

    def table(self, header, rows, caption, widths=None, chapter="", font=7.2, zebra=True):
        n = self.ntab.get(chapter, 0) + 1
        self.ntab[chapter] = n
        cap = Paragraph(f"<b>Table {chapter}.{n}.</b> {caption}", S["tcap"])
        cs = ParagraphStyle("c", parent=S["cell"], fontSize=font, leading=font * 1.22)
        hs = ParagraphStyle("h", parent=S["head"], fontSize=font, leading=font * 1.22)
        data = [[Paragraph(str(h), hs) for h in header]]
        for r in rows:
            data.append([Paragraph(str(c), cs) for c in r])
        if widths is None:
            widths = [W / len(header)] * len(header)
        else:
            tot = sum(widths)
            widths = [w * W / tot for w in widths]
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
              ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efe7e3"))]
        if zebra:
            for i in range(1, len(data)):
                if i % 2 == 0:
                    st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8f6f4")))
        t.setStyle(TableStyle(st))
        self.story.append(cap)
        self.story.append(t)
        self.story.append(Spacer(1, 6))
        return f"Table {chapter}.{n}"

    def figure(self, png: bytes, caption: str, chapter: str, width=W):
        if not png:
            return None
        n = self.nfig.get(chapter, 0) + 1
        self.nfig[chapter] = n
        img = Image(io.BytesIO(png))
        r = img.imageHeight / img.imageWidth
        w = min(width, W)
        h = w * r
        if h > 19 * cm:
            h = 19 * cm
            w = h / r
        img.drawWidth, img.drawHeight = w, h
        self.story.append(KeepTogether([img, Paragraph(f"<b>Figure {chapter}.{n}.</b> {caption}", S["cap"])]))
        return f"Figure {chapter}.{n}"

    def box(self, text, bg="#fbf3e6", border="#d9a441"):
        t = Table([[Paragraph(text, S["box"])]], colWidths=[W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                               ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(border)),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        self.story.append(t)
        self.story.append(Spacer(1, 8))


# =============================================================================== report
def build_pdf(ds, an, R, facts, chapters: dict, meta: dict) -> bytes:
    res = R["res"]
    thin = R["thin_crack"]
    flagged = set(thin[thin.status == "violated"].label)
    edge = set(thin[thin.status.str.startswith("satisfied; a/d")].label)
    src = ds.deformation_source
    name = ds.name
    B = Builder()
    tgt, scr = R["target_mm"], R["screen_MPa"]

    def flag(lbl):
        return " †" if lbl in flagged else (" ‡" if lbl in edge else "")

    # ------------------------------------------------------------------ title page
    B.story += [Spacer(1, 3.2 * cm), Paragraph("Quantitative volcano-monitoring report", S["sub"]), Spacer(1, 0.6 * cm),
                Paragraph(clean(f"From magma compressibility to surface deformation at {name}"), S["title"]),
                Spacer(1, 0.8 * cm),
                Paragraph(clean(", ".join(x for x in (ds.region, ds.country) if x)), S["sub"]), Spacer(1, 2.2 * cm),
                Paragraph(f"Generated on {_dt.date.today():%d %B %Y} by the Volcano Compressibility Agent "
                          "(Freya&nbsp;Mohammadian, 2026)", S["sub"]),
                Spacer(1, 0.3 * cm),
                Paragraph("Method after Freya&nbsp;Mohammadian (2026), <i>From magma compressibility to surface deformation at La Fossa "
                          "volcano (Vulcano Island, Italy)</i>, MSc thesis", S["sub"]),
                Spacer(1, 2.4 * cm)]
    ng = len(ds.data_gaps)
    B.box("<b>How this report was produced.</b> The input data were collected automatically from the published literature "
          f"by an AI research agent ({clean(meta.get('model', ''))}); the physics — EVo volatile equilibria and the Mogi, Yang "
          "and Fialko elastic sources — was computed by code that reproduces the La Fossa thesis results to machine precision; "
          "the narrative chapters were drafted by the language model from the computed numbers only. Every input carries its "
          "source and a status code (M measured, U analytical upper limit, A adopted, D generic default). "
          f"<b>{ng} input(s) are generic defaults or carry caveats</b> (Section 4.7). Verify key inputs against the cited "
          "papers before using the results in any decision. This report is not an eruption forecast or a hazard assessment.")
    B.story.append(PageBreak())
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    B.story += [Paragraph("Contents", S["h1"]), toc, PageBreak()]

    # ------------------------------------------------------------------ abstract
    B.h1("Abstract")
    B.prose(chapters.get("abstract"))
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ chapter 1
    B.h1("1  Introduction")
    B.h2("1.1 Volcano geodesy and the problem of compressible magma")
    B.prose(T.INTRO_GENERAL.format(name=clean(name)))
    B.h2(f"1.2 {name}")
    B.prose(chapters.get("intro_volcano"))
    B.h2("1.3 Aim and research questions")
    B.prose(chapters.get("aims"))
    B.h2("1.4 Approach")
    B.prose(T.APPROACH.format(target=f"{tgt:g}"))
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ chapter 2
    B.h1("2  The volcanic system")
    B.h2("2.1 Geological setting and eruptive history")
    B.prose(chapters.get("ch2_setting"))
    B.h2("2.2 The magma series")
    B.prose(chapters.get("ch2_magmas"))
    B.h2("2.3 The plumbing system")
    B.prose(chapters.get("ch2_plumbing"))
    rows = []
    for L in ds.levels:
        rows.append([clean(L.name), qstr(L.depth_km, unit="km"), qstr(L.pressure_MPa, unit="MPa"),
                     f"{L.resident.capitalize()} / {L.injected.capitalize()}", clean(L.evidence),
                     clean(L.depth_km.source)])
    if src is not None:
        rows.insert(0, ["Published deformation source", qstr(src.depth_km, unit="km") + f" {clean(src.depth_reference)}",
                        (f"ΔP = {src.dP_MPa.value:g} MPa" if src.dP_MPa.value else "—"),
                        f"{src.resident.capitalize()} (hypothetical) / {src.injected.capitalize()}",
                        clean(src.interpretation), clean(src.source)])
    B.table(["Level", "Depth", "Published pressure", "Resident / injected magma", "Evidence", "Source"], rows,
            "Storage levels of the plumbing system adopted for the model. Status codes in parentheses "
            "(M measured, U upper limit, A adopted, D generic default).", widths=[2.2, 1.6, 1.5, 1.8, 3.6, 2.0], chapter="2")
    B.figure(FIG.plumbing(ds, R), "Schematic cross-section of the modelled storage levels (depth to scale, horizontal axis "
             "schematic), with the lithostatic pressures of Eq. (3.1) and the resident magma of each level.", "2", width=0.8 * W)
    B.h2("2.4 Volatile budgets and temperatures")
    B.prose(chapters.get("ch2_volatiles"))
    rows = [[m.key.capitalize(), qstr(m.T_C, 4, "°C"), qstr(m.H2O_wt), qstr(m.CO2_wt), qstr(m.S_wt),
             clean("; ".join(dict.fromkeys(x for x in (m.T_C.source, m.H2O_wt.source, m.CO2_wt.source, m.S_wt.source) if x)))]
            for m in ds.magmas]
    B.table(["Magma", "T", "H<sub>2</sub>O (wt%)", "CO<sub>2</sub> (wt%)", "S (wt%)", "Sources"], rows,
            "Temperatures and volatile budgets with their published ranges and status codes. Values marked U are detection "
            "limits assigned as positive numbers; values marked D were not found and are generic defaults.",
            widths=[1.4, 1.6, 1.6, 1.6, 1.5, 3.8], chapter="2")
    B.h2("2.5 Hydrothermal system, unrest and ground deformation")
    B.prose(chapters.get("ch2_unrest"))
    B.h2("2.6 Synthesis: the conceptual scheme")
    B.prose(chapters.get("ch2_synthesis"))
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ chapter 3
    B.h1("3  Theoretical framework")
    B.para("Every number of Chapter 5 is produced by the relations below; their derivation and provenance are given in "
           "Chapter 3 of the MSc thesis of Freya Mohammadian (2026).")
    for title, pre, eq, post in T.THEORY:
        B.h2(title)
        B.para(pre)
        B.para(re.sub(r" {2,}", lambda m: "&nbsp;" * len(m.group(0)), eq), "eq")
        B.para(post.format(rho=ds.rho_crust.value, screen=scr))
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ chapter 4
    B.h1("4  Input data, scenario design and verification")
    B.h2("4.1 Melt compositions")
    ox = ["SIO2", "TIO2", "AL2O3", "FEO", "MNO", "MGO", "CAO", "NA2O", "K2O", "P2O5"]
    lab = ["SiO<sub>2</sub>", "TiO<sub>2</sub>", "Al<sub>2</sub>O<sub>3</sub>", "FeO<sub>tot</sub>", "MnO", "MgO", "CaO",
           "Na<sub>2</sub>O", "K<sub>2</sub>O", "P<sub>2</sub>O<sub>5</sub>"]
    rows = [["Sample / unit"] + [clean(m.label or m.rock_type) for m in ds.magmas]]
    rows += [[l] + [f"{m.oxides[o]:.2f}" for m in ds.magmas] for o, l in zip(ox, lab)]
    rows += [["Status"] + [m.composition_status for m in ds.magmas],
             ["EVo solubility class"] + [m.evo_class for m in ds.magmas],
             ["Source"] + [clean(m.composition_source) for m in ds.magmas]]
    B.table(["Oxide (wt%)"] + [m.key.capitalize() for m in ds.magmas], rows,
            "Major-element compositions supplied to EVo (total iron as FeO; Fe<sub>2</sub>O<sub>3</sub> converted with the "
            "factor 0.8998). The EVo class is the Burgisser et al. (2015) calibration whose SiO<sub>2</sub> range contains the "
            "melt; for intermediate compositions the phonolite class is an approximation.",
            widths=[1.6] + [2.0] * len(ds.magmas), chapter="4")
    B.h2("4.2 Magmatic state parameters")
    rows = [[m.key.capitalize(), f"{m.T_C.value:g} ({m.T_C.status})", f"{m.H2O_wt.value:g} ({m.H2O_wt.status})",
             f"{m.CO2_wt.value:g} ({m.CO2_wt.status})", f"{m.S_wt.value:g} ({m.S_wt.status})",
             sci_always(m.beta_liquid.value, 1),
             clean("; ".join(x for x in (m.H2O_wt.note, m.CO2_wt.note) if x))] for m in ds.magmas]
    B.table(["Magma", "T (°C)", "H<sub>2</sub>O (wt%)", "CO<sub>2</sub> (wt%)", "S (wt%)", "β<sub>liquid</sub> (Pa<sup>−1</sup>)",
             "Basis"], rows, f"Scenario A magmatic state parameters (total budgets supplied to the EVo saturation search; "
            f"fO<sub>2</sub> buffered at FMQ{ds.dFMQ.value:+g}).", widths=[1.3, 1.1, 1.1, 1.1, 1.0, 1.2, 4.0], chapter="4")
    B.h2("4.3 Mechanical parameters and the published source")
    rows = [["Crustal density ρ<sub>c</sub>", qstr(ds.rho_crust, unit="kg m<sup>−3</sup>"), clean(ds.rho_crust.source or ds.rho_crust.note)],
            ["Shear modulus, deep μ", qstr(ds.mu_deep_GPa, unit="GPa"), clean(ds.mu_deep_GPa.source or ds.mu_deep_GPa.note)],
            ["Poisson ratio, deep ν", qstr(ds.nu_deep), clean(ds.nu_deep.source or ds.nu_deep.note)],
            ["Shear modulus, shallow μ", qstr(ds.mu_shallow_GPa, unit="GPa"), clean(ds.mu_shallow_GPa.source or ds.mu_shallow_GPa.note)],
            ["Poisson ratio, shallow ν", qstr(ds.nu_shallow), clean(ds.nu_shallow.source or ds.nu_shallow.note)],
            ["Summit elevation", qstr(ds.summit_elevation_m, 4, "m"), clean(ds.summit_elevation_m.source)],
            ["Caldera half-length (bounds sill radius)", qstr(ds.caldera_max_radius_km, unit="km"), clean(ds.caldera_max_radius_km.source)]]
    if src is not None:
        rows += [["Published source: model / depth", f"{src.model} / {qstr(src.depth_km, unit='km')} {clean(src.depth_reference)}", clean(src.source)],
                 ["Published source: geometry", clean(f"a = {src.a_m.value:g} m" + (f", b = {src.b_m.value:g} m, plunge {src.dip_deg.value:g}°, trend {src.strike_deg.value:g}°" if src.model == "YANG" else "")), clean(src.a_m.source)],
                 ["Published source: V<sub>0</sub>, ΔV, ΔP", f"{sci_always(src.V0_m3.value)} m³; " + (f"{sci_always(src.dV_m3.value)} m³" if src.dV_m3.value else "—") + "; " + (f"{src.dP_MPa.value:g} MPa" if src.dP_MPa.value else "—"), clean(src.dV_m3.source)],
                 ["Published source: μ, ν used", f"{src.mu_GPa.value:g} GPa ({src.mu_GPa.status}), {src.nu.value:g} ({src.nu.status})", clean(src.mu_GPa.source)]]
    B.table(["Parameter", "Value", "Source / note"], rows, "Mechanical and geometric inputs.", widths=[3, 3.4, 4.6], chapter="4")
    B.h2("4.4 Scenario design")
    B.para(f"The scenario matrix crosses the {len(ds.levels)} magmatic storage levels with three source geometries — a Mogi sphere "
           f"and penny-shaped cracks of radius {', '.join(f'{a:g}' for a in sorted(res.penny_radius_km.dropna().unique()))} km "
           "(bounded by the caldera dimension where known) — and with injected volumes of 10<sup>6</sup>, 5×10<sup>6</sup> and "
           "10<sup>7</sup> m<sup>3</sup> per level. Initial reservoir volumes follow the published values where available and "
           "otherwise grow with depth as in the La Fossa scheme (5×10<sup>8</sup>, 5×10<sup>9</sup>, 5×10<sup>10</sup> m<sup>3</sup>). "
           + ("The published deformation source is added as the shallowest configuration, with its published geometry and the "
              "most evolved magma as a hypothetical magmatic occupant; its pressure is computed at the published model depth "
              "and this pressure datum is varied in Section 5.6. " if src is not None else "")
           + "The resident composition controls β<sub>m</sub>; the injected composition is a scenario label.")
    rows = [[clean(c.label), f"{c.depth_km:g}", c.resident.capitalize(), c.injected.capitalize(), sci_always(c.V0, 2),
             ", ".join(sci_always(v, 0) for v in c.Ve), f"{c.mu / 1e9:g}, {c.nu:g}",
             ("violated" if c.label in flagged else ("satisfied (a/d = 1)" if c.label in edge else ("satisfied" if c.model == "PENNY" else "n/a")))]
            for c in R["configs"]]
    B.table(["Configuration", "z (km)", "Resident", "Injected", "V<sub>0</sub> (m³)", "V<sub>e</sub> (m³)", "μ (GPa), ν", "Thin crack"],
            rows, "The scenario matrix (Scenario A).", widths=[3.0, 0.8, 1.3, 1.3, 1.3, 2.4, 1.2, 1.5], chapter="4")
    sb = R["scenario_b"]
    rows = [[clean(r.level), f"{r.depth_km:g}", r.magma.capitalize(), r.scenario, f"{r.H2O_wt:.2f}", f"{r.CO2_wt:.3f}",
             f"×{r.H2O_multiplier:.2f}"] for _, r in sb.iterrows()]
    B.table(["Level", "z (km)", "Resident", "Trial", "H<sub>2</sub>O (wt%)", "CO<sub>2</sub> (wt%)", "H<sub>2</sub>O / Scenario A"],
            rows, "Scenario A (adopted budgets) and the graded volatile-rich Scenario B trials. Scenario B values are trial "
            "values, not measurements: they test the dependence of the results on the assumed inventory, with the depth-graded "
            "multipliers of the La Fossa thesis.", widths=[3, 1, 1.5, 1, 1.4, 1.4, 1.6], chapter="4")
    B.h2("4.5 Numerical implementation")
    B.para(f"The chain is implemented in Python. Volatile equilibria are computed with EVo (Liggins et al., 2020, 2022) pinned "
           f"to the commit used for the La Fossa thesis, in closed-system saturation-finding mode (engine used here: "
           f"{R['engine']}); elastic sources use dmodelspy, the Python port of dMODELS (Battaglia et al., 2013), with the two "
           "NumPy-2 compatibility corrections of the thesis. EVo's warning routine for temperatures outside the calibrated "
           "range of its H<sub>2</sub>O solubility law is replaced so that EVo continues, as intended, with "
           "temperature-independent coefficients; any state affected is listed in Section 4.7. Run on the La Fossa "
           "dataset, the same code reproduces every r<sub>V</sub> and uplift value of the thesis to a relative "
           "precision of 10<sup>−6</sup>.")
    B.h2("4.6 Verification and consistency checks")
    rows = [[clean(v["test"]), v["kind"], (sci(v["this"], 3) if isinstance(v["this"], (float, np.floating)) else str(v["this"])),
             (sci(v["ref"], 3) if isinstance(v["ref"], (float, int, np.floating)) and np.isfinite(v["ref"]) else "—"), clean(v["agreement"])]
            for v in R["verification"] + R["consistency"]]
    B.table(["Test", "Kind", "This work", "Reference", "Agreement"], rows,
            "Verification against closed-form solutions and consistency with the published source mechanics. A consistency "
            "check shows that two implementations of the same elastic relation agree; it does not validate the petrological, "
            "thermodynamic or elastic assumptions of the chain.", widths=[4.4, 1.3, 1.4, 1.4, 2.5], chapter="4")
    B.h2("4.7 Data gaps, defaults and caveats")
    gaps_all = list(ds.data_gaps) + list(R.get("notes", []))
    if gaps_all:
        for g in gaps_all:
            B.para("• " + clean(g), "small")
    else:
        B.para("No input had to be replaced by a generic default.")
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ chapter 5
    B.h1("5  Results")
    B.h2("5.1 Magmatic state of the reservoirs")
    B.prose(chapters.get("res_state"))
    st = R["states"]
    rows = [[clean(r.level), f"{r.depth_km:g}", f"{r.P_MPa:.2f}", r.role, r.magma.capitalize(), f"{r.T_C:.0f}",
             num(r.P_sat_MPa, 1), "yes" if r.saturated else "no", num(100 * r.phi, 2), num(100 * r.gas_wt, 3)]
            for _, r in st.iterrows()]
    B.table(["Level", "z (km)", "P (MPa)", "Role", "Magma", "T (°C)", "P<sub>sat</sub> (MPa)", "Saturated?", "φ (vol%)", "Gas (wt%)"],
            rows, "Magmatic state of each reservoir under Scenario A (EVo). β<sub>m</sub> is set by the resident magma; the "
            "injected magma is listed for reference.", widths=[2.6, 0.8, 1, 1.1, 1.2, 0.9, 1.1, 1.1, 1, 1], chapter="5")
    for d in R["saturated_detail"]:
        sp = d["gas_species"]
        rows = [[re.sub(r"(\d)", r"<sub>\1</sub>", k), f"{100 * v:.2f}", num(d.get("f" + k), 3) if ("f" + k) in d and d.get("f" + k) is not None else "—"]
                for k, v in sorted(sp.items(), key=lambda kv: -kv[1]) if v > 1e-5]
        rows.append(["Bulk", f"M̄ = {1000 * d['gas_molmass']:.1f} g/mol", f"ρ<sub>g</sub> = {num(d['rho_gas'], 1)} kg/m³"])
        rows.append(["β<sub>m</sub>", f"frozen {sci_always(d['beta_m'])}", f"equilibrium {sci_always(d['beta_m_evo'])} Pa<sup>−1</sup>"])
        B.table(["Species", "mol%", "Fugacity (bar)"], rows,
                clean(f"Equilibrium vapour of the gas-bearing {d['magma'].lower()} at {d['P_MPa']:.2f} MPa ({d['label']}); "
                      f"φ = {100 * d['phi']:.2f} vol%, log fO2 = FMQ{d['fO2_dFMQ']:+.2f}."),
                widths=[2, 3, 4], chapter="5")
    B.h2("5.2 Compressibilities and volume partitioning")
    B.prose(chapters.get("res_partitioning"))
    rows = []
    for _, r in res.iterrows():
        rows.append([clean(r.label) + flag(r.label), f"{r.depth_km:g}", f"{r.P_MPa:.2f}", num(100 * r.phi, 2),
                     sci_always(r.beta_m), sci_always(r.beta_c), f"{r.beta_c * r.mu_Pa:.3g}", f"{r.rV:.3f}",
                     (f"{r.rV_eq:.2f}" if r.phi > 0 else "="), f"{100 / r.rV:.1f}%"])
    B.table(["Configuration", "z (km)", "P (MPa)", "φ (vol%)", "β<sub>m</sub> (Pa<sup>−1</sup>)", "β<sub>c</sub> (Pa<sup>−1</sup>)",
             "β<sub>c</sub>μ", "r<sub>V</sub> frozen", "r<sub>V</sub> equil.", "1/r<sub>V</sub>"], rows,
            "Compressibilities and volume-partitioning factors. † violates the thin-crack condition (stiff-walled idealisation, "
            "not a sill); ‡ crack radius equal to or larger than its depth (validity limit). '=' : the two branches coincide (φ = 0).",
            widths=[3.2, 0.8, 0.9, 0.9, 1.3, 1.3, 0.8, 1, 1, 0.9], chapter="5")
    B.figure(FIG.rv_bars(R, thin), "Volume-partitioning factor for every configuration (logarithmic scale; upper axis: fraction "
             "of an injection expressed as cavity-volume change). Hatched bars violate the thin-crack condition.", "5")
    B.h2("5.3 Reservoir volume changes")
    rows = [[clean(r.label) + flag(r.label), f"{r.rV:.3f}"] + [f"{sci_always(r[f'Ve{k}_m3'], 0)} → {sci_always(r[f'dVc{k}_m3'])}" for k in (1, 2, 3)]
            + [f"{100 / r.rV:.1f}%"] for _, r in res.iterrows()]
    B.table(["Configuration", "r<sub>V</sub>", "V<sub>e1</sub> → ΔV<sub>c1</sub>", "V<sub>e2</sub> → ΔV<sub>c2</sub>",
             "V<sub>e3</sub> → ΔV<sub>c3</sub>", "Expressed"], rows,
            "Injected volumes and the resulting reservoir volume changes ΔV<sub>c</sub> = V<sub>e</sub>/r<sub>V</sub> (m³), frozen branch.",
            widths=[3.4, 1, 2.1, 2.1, 2.1, 1], chapter="5")
    B.h2("5.4 Predicted surface displacements")
    B.prose(chapters.get("res_uplift"))
    rows = [[clean(r.label) + flag(r.label), f"{r.depth_km:g}", sci_always(r.Ve1_m3, 0), mm(r.uz1_0km_mm), mm(r.uz1_1km_mm),
             mm(r.uz1_2km_mm), sci_always(r.Ve3_m3, 0), mm(r.uz3_0km_mm), mm(r.uz3_1km_mm), mm(r.uz3_2km_mm),
             f"{r.uz3_2km_mm / r.uz3_0km_mm:.2f}"] for _, r in res.iterrows()]
    B.table(["Configuration", "z (km)", "V<sub>e</sub> small", "0 km", "1 km", "2 km", "V<sub>e</sub> large", "0 km", "1 km", "2 km",
             "u<sub>2km</sub>/u<sub>0</sub>"], rows,
            "Predicted vertical surface displacement (mm) at the centre and at 1 and 2 km radial distance, for the smallest and "
            "largest injected volume (frozen branch; the intermediate volume gives five times the first block). The last column "
            "is independent of V<sub>e</sub>, r<sub>V</sub> and μ and indicates depth within a given source model.",
            widths=[3.1, 0.7, 1.1, 0.9, 0.9, 0.9, 1.1, 0.9, 0.9, 0.9, 1.0], chapter="5")
    B.figure(FIG.profiles(an, R, thin), "Predicted vertical displacement against radial distance for the largest injection of each "
             "configuration: (a) Mogi spheres; (b) penny cracks; (c) the published source geometry as a hypothetical magmatic "
             "end-member under the pressure datums of Section 5.6; (d) profiles normalised to their central value.", "5")
    m = FIG.source_map(an, R)
    if m:
        B.figure(m, "Map of the vertical displacement produced by the published deformation source driven with its published "
                 "cavity-volume change (consistency check, not an independent prediction). Cross: epicentre of the centroid.",
                 "5", width=0.62 * W)
    B.h2("5.5 Detectability: the inverse analysis")
    B.prose(chapters.get("res_inverse"))
    inv = R["inverse"]
    rows = [[clean(d.label) + flag(d.label) + (" [equilibrium]" if d.branch == "equilibrium" else ""), f"{d.depth_km:g}",
             f"{d.rV:.2f}", sci_always(d.Ve), sci_always(d.dVc), f"{d.dP_MPa:.2f}", "yes" if d.within_screen else "<b>no</b>"]
            for _, d in inv.iterrows()]
    B.table(["Configuration", "z (km)", "r<sub>V</sub>", "V<sub>e</sub> needed (m³)", "ΔV<sub>c</sub> (m³)", "ΔP (MPa)",
             f"Within {scr:g} MPa screen?"], rows,
            f"Injected volume, cavity-volume change and overpressure required for {tgt:g} mm of central uplift, ordered by "
            "geodetic cost. ΔV<sub>c</sub> and ΔP are fixed by the elastic problem alone; V<sub>e</sub> depends on the volatile "
            "state and the compressibility branch.", widths=[3.6, 0.8, 0.9, 1.6, 1.6, 1, 1.4], chapter="5")
    B.figure(FIG.inverse(R), f"Injected volume required for {tgt:g} mm of central uplift, with the overpressure each "
             "configuration requires. Outlined bars exceed the screening threshold; light bars are the equilibrium branch.", "5")
    B.h2("5.6 Sensitivity analyses")
    B.prose(chapters.get("res_sensitivity"))
    rows = [[clean(r.level), r.scenario, f"{r.H2O_wt:.2f}", f"×{r.H2O_multiplier:.2f}", num(r.P_sat_MPa, 0),
             num(100 * r.phi, 2), f"{r.rV:.2f}", mm(r.uz_max_mm)] for _, r in sb.iterrows()]
    B.table(["Level (Mogi)", "Scenario", "H<sub>2</sub>O (wt%)", "Multiplier", "P<sub>sat</sub> (MPa)", "φ (vol%)", "r<sub>V</sub>",
             "u<sub>z</sub>(0), V<sub>e</sub> = 10<sup>7</sup> m³ (mm)"], rows,
            "Volatile-inventory sensitivity: Scenario A against the Scenario B trials, Mogi geometry.",
            widths=[3, 1, 1.1, 1.1, 1.1, 1, 1, 1.8], chapter="5")
    if "datum" in R:
        rows = [[clean(r.datum), f"{r.zP_km:.3f}", f"{r.P_MPa:.2f}", num(100 * r.phi, 2), f"{r.rV:.2f}", f"{r.rV_eq:.2f}",
                 mm(r.uz_max_mm), mm(r.uz_max_mm_eq)] for _, r in R["datum"].iterrows()]
        B.table(["Pressure datum", "Overburden (km)", "P (MPa)", "φ (vol%)", "r<sub>V</sub> frozen", "r<sub>V</sub> equil.",
                 "u<sub>z</sub>(0) frozen (mm)", "u<sub>z</sub>(0) equil. (mm)"], rows,
                f"The published source geometry as a hypothetical magmatic end-member under three pressure datums, for "
                f"V<sub>e</sub> = {sci_always(R['datum'].Ve_max.iloc[0], 0)} m³.", widths=[3, 1.2, 1, 1, 1, 1, 1.4, 1.4], chapter="5")
        rows = [[f"{r.H2O_wt:.2f}", clean(r.datum), f"{r.P_MPa:.1f}", num(r.P_sat_MPa, 1), num(100 * r.phi, 2), f"{r.rV:.2f}",
                 f"{r.rV_eq:.2f}"] for _, r in R["h2o_datum"].iterrows()]
        B.table(["H<sub>2</sub>O (wt%)", "Datum", "P (MPa)", "P<sub>sat</sub> (MPa)", "φ (vol%)", "r<sub>V</sub> frozen", "r<sub>V</sub> equil."],
                rows, "Joint sensitivity of the shallow source to the dissolved water content (±20%) and the pressure datum.",
                widths=[1.2, 3, 1, 1.2, 1, 1.2, 1.2], chapter="5")
    extra = []
    if "density" in R:
        extra += [[f"ρ<sub>c</sub> = {r.rho:.0f} kg m<sup>−3</sup>", "published source", f"P = {r.P_MPa:.2f} MPa, φ = {100 * r.phi:.2f}%",
                   f"{r.rV:.2f}"] for _, r in R["density"].iterrows()]
    if "redox" in R:
        extra += [[f"ΔFMQ = {r.dFMQ:+.1f}", "published source", f"φ = {100 * r.phi:.2f}%, fSO<sub>2</sub> = {num(r.fSO2, 2)} bar, "
                   f"fH<sub>2</sub>S = {num(r.fH2S, 2)} bar", "—"] for _, r in R["redox"].iterrows()]
    if "aspect" in R:
        extra += [[f"A = {r.aspect:g}", "published source", f"β<sub>c</sub>μ = {r.beta_c_mu:.3f}", f"{r.rV:.2f}"]
                  for _, r in R["aspect"].iterrows()]
    extra += [[f"μ = {r.mu_GPa:g} GPa, ν = {r.nu:.2f}", clean(r.level) + " (Mogi)", f"u<sub>z</sub>(0) = {mm(r.uz_max_mm)} mm",
               f"{r.rV:.2f}"] for _, r in R["elastic"].iterrows() if r.nu == 0.25 or r.mu_GPa == 10]
    B.table(["Lever value", "Configuration", "Effect", "r<sub>V</sub>"], extra,
            "Other levers: crustal density, redox state, source aspect ratio and elastic parameters.",
            widths=[3, 3, 4.5, 1], chapter="5")
    rows = [[f"{r.a_km:g}", f"{r.depth_km:g}", sci_always(r.V0, 0), f"{r.wbar:,.0f}", f"{r.ratio:.3g}", f"{r.a_over_d:.2f}",
             f"{r.rV:.2f}", r.status] for _, r in thin.iterrows()]
    B.table(["a (km)", "z (km)", "V<sub>0</sub> (m³)", "w̄ (m)", "w̄/2a", "a/d", "r<sub>V</sub>", "Status"], rows,
            "Geometric consistency of the penny-shaped configurations (thin-crack condition w̄/2a ≤ 0.1).",
            widths=[0.8, 0.8, 1.3, 1.2, 1, 0.8, 1, 3.2], chapter="5")
    B.figure(FIG.sensitivity(R), "Sensitivity of the volume-partitioning factor: (a) to the assumed volatile budget of each "
             "Mogi reservoir; (b) to the pressure datum and dissolved water content of the shallow source, on both "
             "compressibility branches.", "5")
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ 6 & 7
    B.h1("6  Discussion")
    B.prose(chapters.get("discussion"))
    B.story.append(PageBreak())
    B.h1("7  Conclusions and future work")
    B.prose(chapters.get("conclusions"))
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ references
    B.h1("References")
    allrefs = [(r.key, r.citation or r.key, r.url or (f"https://doi.org/{r.doi}" if r.doi else "")) for r in ds.references]
    for mref in T.METHOD_REFS:
        allrefs.append((mref, mref, ""))
    seen = set()
    for key, cit, url in sorted(allrefs, key=lambda x: x[1].lower()):
        if cit in seen:
            continue
        seen.add(cit)
        B.para(clean(cit) + (f" <font color='#555555'>{clean(url)}</font>" if url else ""), "ref")
    B.story.append(PageBreak())

    # ------------------------------------------------------------------ appendices
    B.h1("Appendix A  Complete numerical results")
    rows = [[clean(r.label), f"{r.P_MPa:.3f}", f"{r.phi:.5f}", sci_always(r.beta_m, 3), sci_always(r.beta_m_eq, 3),
             sci_always(r.beta_c, 3), f"{r.rV:.4f}", f"{r.rV_eq:.4f}", sci_always(r.dVc3_m3, 3), f"{r.uz3_0km_mm:.4g}",
             f"{r.uz3_1km_mm:.4g}", f"{r.uz3_2km_mm:.4g}"] for _, r in res.iterrows()]
    B.table(["Configuration", "P (MPa)", "φ", "β<sub>m</sub>", "β<sub>m</sub><sup>eff</sup>", "β<sub>c</sub>", "r<sub>V</sub>",
             "r<sub>V</sub><sup>eq</sup>", "ΔV<sub>c3</sub>", "u(0)", "u(1 km)", "u(2 km)"], rows,
            "Complete forward results (largest injected volume; displacements in mm; compressibilities in Pa<sup>−1</sup>).",
            widths=[2.8, 0.9, 0.9, 1.2, 1.2, 1.2, 0.9, 0.9, 1.2, 0.8, 0.8, 0.8], chapter="A", font=6.4)
    B.h1("Appendix B  Provenance of every input")
    rows = []
    for m in ds.magmas:
        rows.append([f"{m.key.capitalize()} composition", clean(m.label), m.composition_status, clean(m.composition_source), ""])
        for nm, qq, u in (("T", m.T_C, "°C"), ("H₂O", m.H2O_wt, "wt%"), ("CO₂", m.CO2_wt, "wt%"), ("S", m.S_wt, "wt%"),
                          ("β_liquid", m.beta_liquid, "Pa⁻¹")):
            rows.append([f"{m.key.capitalize()} {nm}", f"{qq.value:.4g} {u}", qq.status, clean(qq.source), clean(qq.note)])
    for L in ds.levels:
        rows.append([f"{clean(L.name)} depth", f"{L.depth_km.value:g} km", L.depth_km.status, clean(L.depth_km.source), clean(L.depth_km.note)])
        rows.append([f"{clean(L.name)} V₀", sci_always(L.V0_m3.value), L.V0_m3.status, clean(L.V0_m3.source), clean(L.V0_m3.note)])
    for nm, qq in (("ρ_crust", ds.rho_crust), ("μ deep (GPa)", ds.mu_deep_GPa), ("ν deep", ds.nu_deep),
                   ("μ shallow (GPa)", ds.mu_shallow_GPa), ("ν shallow", ds.nu_shallow), ("ΔFMQ", ds.dFMQ)):
        rows.append([nm, f"{qq.value:g}", qq.status, clean(qq.source), clean(qq.note)])
    B.table(["Input", "Value", "Status", "Source", "Note"], rows,
            "Provenance and status of every input. " + "; ".join(f"{k} = {v}" for k, v in STATUS_LABEL.items()) + ".",
            widths=[2.4, 1.8, 0.8, 3.2, 3.6], chapter="B", font=6.6)
    B.h1("Appendix C  Research log and number audit")
    B.para(clean(f"Research model: {meta.get('model', '')}. Usage: {meta.get('usage', '')}. "
                 f"Software: Volcano Compressibility Agent {__version__}; EVo commit {EVO_COMMIT[:7]}. "
                 f"Report generated {_dt.datetime.now():%Y-%m-%d %H:%M}."), "small")
    unmatched = meta.get("audit", [])
    B.para(("<b>Number audit.</b> Every number in the model-written chapters was compared with the computed facts and the "
            "inputs (allowing for the rounding implied by the digits written and for % and km/m conversions). " +
            (f"{len(unmatched)} number(s) could not be matched and should be checked: " + clean(", ".join(unmatched[:80]))
             if unmatched else "All numbers were matched.")), "small")
    B.para("<b>Web sources returned during the research</b> (not all were used; the cited references are listed above):", "small")
    for u in ds.research_log[2:120]:
        B.para(clean(u), "small")

    buf = io.BytesIO()
    doc = Doc(buf, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2.0 * cm, bottomMargin=2.0 * cm,
              title=f"Magma compressibility and surface deformation at {name}", author="Volcano Compressibility Agent - Freya Mohammadian",
              volcano=name)
    doc.multiBuild(B.story, onLaterPages=_footer)
    return buf.getvalue()


def audit_chapters(chapters: dict, facts: dict) -> list:
    text = "\n".join(v for v in chapters.values() if v)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\((?:[^()]*?)\b(1[89]\d\d|20\d\d)[a-z]?\)", " ", text)       # citation years
    text = re.sub(r"RQ\d", " ", text)
    return audit_numbers(text, facts)
