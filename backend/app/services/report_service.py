"""Builds the client-facing PDF report for an analysed project.

Everything in it comes from the stored design: nothing is invented here. Warnings that matter to a reader
(unverified scale, demo data, edits not yet regenerated, calculations awaiting review) are printed on the
first page so they cannot be missed.
"""
import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.catalog.equipment import get_equipment
from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.electrical import Circuit, ElectricalPoint
from app.services.electrical_calculations import calculate
from app.services.plan_storage import display_path_for, ensure_plan_on_disk

INK = colors.HexColor("#1b2430")
MUTED = colors.HexColor("#5b6675")
ACCENT = colors.HexColor("#0b5fff")
RULE = colors.HexColor("#d5dae1")
HEAD_BG = colors.HexColor("#eef2f8")
WARN_BG = colors.HexColor("#fff4d6")
WARN_INK = colors.HexColor("#7a5200")
BAD = colors.HexColor("#b3261e")
GOOD = colors.HexColor("#1b7a3a")

# One colour per kind of equipment, so the plan can be read at a glance.
CATEGORY_COLORS = {
    "lighting": colors.HexColor("#f2a900"),
    "socket": colors.HexColor("#0b5fff"),
    "switch": colors.HexColor("#6b4de6"),
    "appliance": colors.HexColor("#d4380d"),
    "safety": colors.HexColor("#1b7a3a"),
    "comms": colors.HexColor("#08979c"),
    "board": colors.HexColor("#1b2430"),
}

DISCLAIMER = (
    "This is a preliminary electrical design proposed by software from an architectural drawing. It is advisory "
    "only. It must be checked on site and reviewed, corrected and signed off by a licensed electrical engineer "
    "before it is used for procurement, permits or installation. Quantities and prices are estimates."
)


def _kind(point_type: str, symbol: str) -> str:
    t = point_type.lower()
    if "distribution" in t:
        return "board"
    if symbol in ("light", "light_wall", "fan") or ("light" in t and "emergency" not in t):
        return "lighting"
    if "switch" in t:
        return "switch"
    if "smoke" in t or "emergency" in t:
        return "safety"
    if "data" in t or "tv" in t:
        return "comms"
    if "socket" in t:
        return "socket"
    return "appliance"


def _rwf(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}"


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=26,
                                leading=30, textColor=INK, alignment=0, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontSize=12, leading=16, textColor=MUTED),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=15,
                             leading=19, textColor=INK, spaceBefore=4, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11,
                             leading=14, textColor=INK, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9, leading=12.5, textColor=INK),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=7.5, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=8, leading=10, textColor=INK),
        "cellr": ParagraphStyle("cellr", parent=base["Normal"], fontSize=8, leading=10, textColor=INK,
                                alignment=TA_RIGHT),
        "head": ParagraphStyle("head", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
                               leading=10, textColor=INK),
        "warn": ParagraphStyle("warn", parent=base["Normal"], fontSize=8.5, leading=11.5, textColor=WARN_INK),
    }


def _para(text: Any, style: ParagraphStyle) -> Paragraph:
    s = "" if text is None else str(text)
    return Paragraph(s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def _table(rows: List[List[Any]], widths: List[float], st: Dict[str, ParagraphStyle],
           right_cols: tuple = (), total_row: bool = False, repeat: int = 1) -> Table:
    data: List[List[Any]] = []
    for i, row in enumerate(rows):
        out = []
        for j, cell in enumerate(row):
            if isinstance(cell, Flowable):
                out.append(cell)
            elif i == 0:
                out.append(_para(cell, st["head"]))
            else:
                out.append(_para(cell, st["cellr"] if j in right_cols else st["cell"]))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=repeat)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if total_row:
        style += [("LINEABOVE", (0, -1), (-1, -1), 0.8, INK), ("BACKGROUND", (0, -1), (-1, -1), HEAD_BG)]
    t.setStyle(TableStyle(style))
    return t


class PlanDrawing(Flowable):
    """The floor plan with every proposed point drawn on it."""

    def __init__(self, image_path: Optional[str], points: List[ElectricalPoint], max_w: float, max_h: float):
        super().__init__()
        self.points = points
        self.image_path = image_path
        self.img = ImageReader(image_path) if image_path and os.path.exists(image_path) else None
        if self.img:
            iw, ih = self.img.getSize()
            scale = min(max_w / iw, max_h / ih)
            self.w, self.h = iw * scale, ih * scale
        else:
            self.w, self.h = max_w, 40 * mm

    def wrap(self, availWidth, availHeight):
        return self.w, self.h

    def draw(self):
        c = self.canv
        if not self.img:
            c.setFillColor(HEAD_BG)
            c.rect(0, 0, self.w, self.h, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 9)
            c.drawCentredString(self.w / 2, self.h / 2, "The floor plan image is not available.")
            return
        c.drawImage(self.img, 0, 0, self.w, self.h)
        c.setStrokeColor(RULE)
        c.rect(0, 0, self.w, self.h, stroke=1, fill=0)
        for p in self.points:
            if p.x_ratio is None or p.y_ratio is None:
                continue
            spec = get_equipment(p.type)
            kind = _kind(p.type, spec.symbol if spec else "")
            x, y = p.x_ratio * self.w, (1 - p.y_ratio) * self.h
            c.setFillColor(CATEGORY_COLORS[kind])
            c.setStrokeColor(colors.white)
            c.setLineWidth(0.6)
            r = 2.6
            if kind == "board":
                c.rect(x - 3.4, y - 3.4, 6.8, 6.8, stroke=1, fill=1)
            elif kind == "socket":
                c.rect(x - r, y - r, 2 * r, 2 * r, stroke=1, fill=1)
            elif kind == "switch":
                path = c.beginPath()
                path.moveTo(x, y + r + 0.8)
                path.lineTo(x + r + 0.8, y)
                path.lineTo(x, y - r - 0.8)
                path.lineTo(x - r - 0.8, y)
                path.close()
                c.drawPath(path, stroke=1, fill=1)
            elif kind == "appliance":
                path = c.beginPath()
                path.moveTo(x, y + r + 0.8)
                path.lineTo(x + r + 0.6, y - r)
                path.lineTo(x - r - 0.6, y - r)
                path.close()
                c.drawPath(path, stroke=1, fill=1)
            else:
                c.circle(x, y, r, stroke=1, fill=1)


def _legend_table(points: List[ElectricalPoint], st: Dict[str, ParagraphStyle], width: float) -> Table:
    seen: Dict[str, str] = {}
    for p in points:
        spec = get_equipment(p.type)
        seen[p.type] = spec.name if spec else p.type.replace("_", " ").title()
    items = sorted(seen.items(), key=lambda kv: kv[1])
    cols = 3
    rows, row = [], []
    chips: List[tuple] = []
    for idx, (type_id, name) in enumerate(items):
        spec = get_equipment(type_id)
        kind = _kind(type_id, spec.symbol if spec else "")
        row += ["", _para(name, st["cell"])]
        chips.append((len(rows), len(row) - 2, kind))
        if len(row) == cols * 2:
            rows.append(row)
            row = []
    if row:
        row += [""] * (cols * 2 - len(row))
        rows.append(row)
    if not rows:
        rows = [["", ""] * cols]
    chip_w = 5 * mm
    text_w = (width - cols * chip_w) / cols
    t = Table(rows, colWidths=[chip_w, text_w] * cols)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    for r, c, kind in chips:
        style.append(("BACKGROUND", (c, r), (c, r), CATEGORY_COLORS[kind]))
        style.append(("LINEBEFORE", (c, r), (c, r), 3, colors.white))
        style.append(("LINEAFTER", (c, r), (c, r), 3, colors.white))
        style.append(("LINEABOVE", (c, r), (c, r), 3, colors.white))
        style.append(("LINEBELOW", (c, r), (c, r), 3, colors.white))
    t.setStyle(TableStyle(style))
    return t


def _warnings(project: Project, analysis: Analysis, points: List[ElectricalPoint], calcs: Optional[dict]) -> List[str]:
    out: List[str] = []
    transform = (analysis.canonical_geometry_data or {}).get("transform", {})
    if not (project.is_scale_calibrated and transform.get("is_scale_verified")):
        out.append("The drawing scale has not been calibrated. Cable lengths, voltage drop and the bill of "
                   "quantities rest on an assumed scale and must not be relied on.")
    if analysis.geometry_dirty:
        out.append("Rooms or doors were edited after the equipment was last generated. Regenerate the equipment "
                   "so this report matches the corrected drawing.")
    for w in analysis.warnings or []:
        if "DEMO" in str(w).upper():
            out.append(str(w))
    review = [p for p in points if p.status == "REQUIRES_ENGINEER_REVIEW" or p.placement_status == "needs_confirmation"]
    if review:
        out.append(f"{len(review)} point(s) are marked as needing confirmation by an engineer.")
    if calcs:
        fail_vd = [r for r in calcs["voltage_drop"].get("circuits", []) if r.get("status") == "fail"]
        fail_cap = [r for r in calcs["cable_capacity"].get("circuits", []) if r.get("status") == "fail"]
        if fail_vd:
            out.append("Voltage drop exceeds the limit on: " + ", ".join(r["circuit_id"] for r in fail_vd) + ".")
        if fail_cap:
            out.append("Cable capacity is not met on: " + ", ".join(r["circuit_id"] for r in fail_cap) + ".")
    return out


def build_report_pdf(project: Project, analysis: Analysis) -> bytes:
    st = _styles()
    points = [ElectricalPoint(**p) for p in (analysis.electrical_points_data or [])]
    circuits = [Circuit(**c) for c in (analysis.circuits_data or [])]
    boq = analysis.boq_items_data or []
    cost = analysis.cost_estimate_data or {}
    rooms = analysis.rooms_data or []

    transform = (analysis.canonical_geometry_data or {}).get("transform", {})
    scale_verified = bool(transform.get("is_scale_verified")) and project.is_scale_calibrated
    calcs = None
    if circuits:
        calcs = calculate(circuits, points, project.building_type, scale_verified)

    generated = datetime.now(timezone.utc)
    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 16 * mm
    content_w = page_w - 2 * margin

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 9 * mm, f"VoltPlan  |  {project.name}  |  Preliminary design, not for construction")
        canvas.drawRightString(page_w - margin, 9 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.line(margin, 12 * mm, page_w - margin, 12 * mm)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=16 * mm, bottomMargin=18 * mm,
        title=f"Electrical design - {project.name}", author="VoltPlan", subject="Preliminary electrical design",
    )
    story: List[Any] = []

    # ---- Page 1: cover and summary -------------------------------------------------------------------
    story += [
        Spacer(1, 10 * mm),
        _para("PRELIMINARY ELECTRICAL DESIGN", st["subtitle"]),
        _para(project.name, st["title"]),
        _para(f"Prepared for {project.client}", st["subtitle"]),
        Spacer(1, 6 * mm),
    ]
    info = [
        ["Project", project.name],
        ["Client", project.client],
        ["Location", project.location],
        ["Building type", project.building_type],
        ["Standard applied", project.standard],
        ["Drawing", project.floor_plan_name or "-"],
        ["Scale", "Calibrated by the user" if scale_verified else "NOT calibrated (assumed)"],
        ["Report date", generated.strftime("%d %B %Y")],
    ]
    story.append(_table([["Item", "Detail"]] + info, [40 * mm, content_w - 40 * mm], st))

    warns = _warnings(project, analysis, points, calcs)
    if warns:
        box = Table([[_para("Read this first", st["head"])]] + [[_para("- " + w, st["warn"])] for w in warns],
                    colWidths=[content_w])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), WARN_BG), ("BOX", (0, 0), (-1, -1), 0.8, WARN_INK),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story += [Spacer(1, 6 * mm), box]

    total_load_kw = sum(c.connected_load_w for c in circuits) / 1000.0
    summary = [
        ["Rooms", str(len(rooms))],
        ["Electrical points", str(sum(p.quantity for p in points))],
        ["Circuits", str(len(circuits))],
        ["Connected load", f"{total_load_kw:.1f} kW"],
    ]
    if calcs and calcs["max_demand"].get("total_demand_kva") is not None:
        summary.append(["Maximum demand (after diversity)", f"{calcs['max_demand']['total_demand_kva']} kVA"])
    if cost.get("grand_total_rwf") is not None:
        summary.append(["Estimated total cost", f"RWF {_rwf(cost['grand_total_rwf'])}"])
    story += [Spacer(1, 6 * mm), _para("Summary", st["h2"]),
              _table([["Measure", "Value"]] + summary, [80 * mm, content_w - 80 * mm], st)]
    story += [Spacer(1, 8 * mm), _para(DISCLAIMER, st["small"]), PageBreak()]

    # ---- Plan ---------------------------------------------------------------------------------------
    story.append(_para("Floor plan with proposed equipment", st["h1"]))
    ensure_plan_on_disk(project)
    image_path = display_path_for(project) if project.floor_plan_path else None
    story.append(PlanDrawing(image_path, points, content_w, page_h - 110 * mm))
    story += [Spacer(1, 4 * mm), _legend_table(points, st, content_w), PageBreak()]

    # ---- Equipment by room --------------------------------------------------------------------------
    story.append(_para("Equipment schedule", st["h1"]))
    by_room: Dict[str, Dict[str, int]] = {}
    for p in points:
        spec = get_equipment(p.type)
        name = spec.name if spec else p.type.replace("_", " ").title()
        by_room.setdefault(p.room_name or "Unassigned", {})
        by_room[p.room_name or "Unassigned"][name] = by_room[p.room_name or "Unassigned"].get(name, 0) + p.quantity
    rows = [["Room", "Equipment", "Qty"]]
    for room, items in sorted(by_room.items()):
        first = True
        for name, qty in sorted(items.items()):
            rows.append([room if first else "", name, str(qty)])
            first = False
    story.append(_table(rows, [55 * mm, content_w - 75 * mm, 20 * mm], st, right_cols=(2,)))

    # ---- Circuit schedule ---------------------------------------------------------------------------
    story += [Spacer(1, 6 * mm), _para("Circuit schedule", st["h1"])]
    rows = [["Circuit", "Description", "Phase", "Points", "Load (W)", "Cable", "Protection", "RCD"]]
    for c in circuits:
        rows.append([c.id, f"{c.name}: {c.description}" if c.description else c.name, c.phase,
                     str(c.points_count), f"{c.connected_load_w:,.0f}", c.cable or "Review", c.protection or "Review",
                     c.rcd or "-"])
    widths = [17 * mm, 52 * mm, 12 * mm, 13 * mm, 18 * mm, 18 * mm, 28 * mm]
    widths.append(content_w - sum(widths))
    story.append(_table(rows, widths, st, right_cols=(3, 4)))
    flagged = [c for c in circuits if c.status == "REQUIRES_ENGINEER_REVIEW"]
    if flagged:
        story.append(Spacer(1, 3 * mm))
        for c in flagged:
            story.append(_para(f"{c.id}: {c.review_notes or 'Requires engineer review.'}", st["small"]))

    # ---- Calculations -------------------------------------------------------------------------------
    if calcs:
        story += [PageBreak(), _para("Calculations (preliminary)", st["h1"]),
                  _para(calcs["disclaimer"], st["small"]), Spacer(1, 3 * mm)]

        md = calcs["max_demand"]
        if md.get("total_demand_kva") is not None:
            tot = md["total"]
            msw = md.get("suggested_main_switch") or {}
            story.append(_para("Maximum demand", st["h2"]))
            rows = [["Measure", "Value"],
                    ["Connected load", f"{md.get('connected_load_kw')} kW"],
                    ["Demand after diversity", f"{tot['total_demand_a']} A  ({md['total_demand_kva']} kVA)"],
                    ["Phase imbalance", f"{md.get('phase_imbalance_percent')} %"],
                    ["Suggested main switch", f"{msw.get('single_phase_supply_a', '-')} A single-phase / "
                                              f"{msw.get('three_phase_supply_a', '-')} A three-phase"]]
            story.append(_table(rows, [60 * mm, content_w - 60 * mm], st))
            for note in md.get("notes", []):
                story.append(_para(note, st["small"]))

        vd = calcs["voltage_drop"]
        story.append(_para("Voltage drop", st["h2"]))
        if vd.get("status") != "calculated":
            story.append(_para(vd.get("reason") or "Not calculated.", st["body"]))
        else:
            rows = [["Circuit", "Cable", "Length (m)", "Current (A)", "Drop (V)", "Drop (%)", "Limit (%)", "Result"]]
            for r in vd["circuits"]:
                if r["status"] == "not_calculated":
                    rows.append([r["circuit_id"], "", "", "", "", "", "", r.get("reason") or "n/a"])
                    continue
                rec = f" (use {r['recommended_cable_mm2']} mm2)" if r.get("recommended_cable_mm2") else ""
                rows.append([r["circuit_id"], f"{r['cable_mm2']} mm2", str(r["length_m"]), str(r["design_current_a"]),
                             str(r["drop_v"]), str(r["drop_percent"]), str(r["limit_percent"]),
                             r["status"].upper() + rec])
            widths = [18 * mm, 18 * mm, 20 * mm, 20 * mm, 18 * mm, 18 * mm, 18 * mm]
            widths.append(content_w - sum(widths))
            story.append(_table(rows, widths, st, right_cols=(2, 3, 4, 5, 6)))

        cc = calcs["cable_capacity"]
        story.append(_para("Cable current-carrying capacity", st["h2"]))
        opts = cc.get("options", {})
        story.append(_para(
            f"Installation method {opts.get('method')} ({opts.get('method_description')}), ambient "
            f"{opts.get('ambient_c')} C, {opts.get('grouped_circuits')} circuit(s) grouped. "
            "Condition checked: Ib <= In <= Iz.", st["small"]))
        rows = [["Circuit", "Cable", "Ib (A)", "In (A)", "Iz (A)", "Used (%)", "Result"]]
        for r in cc.get("circuits", []):
            if r["status"] == "not_calculated":
                rows.append([r["circuit_id"], "", "", "", "", "", r.get("reason") or "n/a"])
                continue
            rows.append([r["circuit_id"], f"{r['cable_mm2']} mm2", str(r["design_current_a"]),
                         str(r["protective_device_a"]), str(r["capacity_a"]), str(r["utilisation_percent"]),
                         r["status"].upper()])
        widths = [18 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm]
        widths.append(content_w - sum(widths))
        story.append(_table(rows, widths, st, right_cols=(2, 3, 4, 5)))
        story.append(Spacer(1, 3 * mm))
        for ref in calcs.get("references", []):
            story.append(_para(ref, st["small"]))

    # ---- BOQ and cost -------------------------------------------------------------------------------
    story += [PageBreak(), _para("Bill of quantities", st["h1"])]
    categories: Dict[str, List[dict]] = {}
    for item in boq:
        categories.setdefault(item.get("category", "Other"), []).append(item)
    rows = [["Code", "Description", "Qty", "Unit", "Unit price (RWF)", "Total (RWF)"]]
    widths = [22 * mm, 66 * mm, 14 * mm, 14 * mm, 28 * mm]
    widths.append(content_w - sum(widths))
    for category in sorted(categories):
        rows.append([_para(category.upper(), st["head"]), "", "", "", "", ""])
        for it in categories[category]:
            desc = it.get("description", "")
            if it.get("specification"):
                desc += f" ({it['specification']})"
            qty = it.get("quantity", 0)
            rows.append([it.get("item_code", ""), desc, f"{qty:g}", it.get("unit", ""),
                         _rwf(it.get("unit_price_rwf")), _rwf(it.get("total_price_rwf"))])
    styled = _table(rows, widths, st, right_cols=(2, 4, 5))
    for i, row in enumerate(rows):
        if i and isinstance(row[0], Paragraph):
            styled.setStyle(TableStyle([("BACKGROUND", (0, i), (-1, i), HEAD_BG), ("SPAN", (0, i), (-1, i))]))
    story.append(styled)
    story.append(Spacer(1, 6 * mm))

    if cost:
        rows = [["Cost summary", "RWF"],
                ["Materials", _rwf(cost.get("materials_cost_rwf"))],
                [f"Labour ({cost.get('labor_percentage', 28):.0f}% of materials)", _rwf(cost.get("labor_cost_rwf"))],
                [f"Contingency ({cost.get('contingency_percentage', 12):.0f}% of materials)",
                 _rwf(cost.get("contingency_cost_rwf"))],
                ["Estimated total", _rwf(cost.get("grand_total_rwf"))]]
        story.append(KeepTogether([
            _table(rows, [content_w - 45 * mm, 45 * mm], st, right_cols=(1,), total_row=True),
            Spacer(1, 3 * mm),
            *[_para(a, st["small"]) for a in cost.get("assumptions", [])],
            _para(cost.get("disclaimer", ""), st["small"]),
        ]))

    # ---- Sign-off -----------------------------------------------------------------------------------
    sign = Table(
        [[_para("Reviewed by (licensed engineer)", st["cell"]), _para("Registration no.", st["cell"]),
          _para("Signature and date", st["cell"])], ["", "", ""]],
        colWidths=[content_w * 0.4, content_w * 0.25, content_w * 0.35], rowHeights=[None, 16 * mm])
    sign.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, INK), ("INNERGRID", (0, 0), (-1, -1), 0.6, INK),
                              ("VALIGN", (0, 0), (-1, 0), "TOP")]))
    story += [Spacer(1, 10 * mm), KeepTogether([_para("Engineer sign-off", st["h2"]), sign, Spacer(1, 3 * mm),
                                                _para(DISCLAIMER, st["small"])])]

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
