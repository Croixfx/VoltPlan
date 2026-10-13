"""
Evaluate VoltPlan against floor plans that an electrician has already designed.

For every plan `eval_plans/<name>.(png|jpg|jpeg|pdf)` that has a sibling
`<name>.reference.json`, this runs the real pipeline (with the AI provider from your
environment / --provider) and compares the result with the electrician's design:

  * rooms detected and named correctly
  * doors detected
  * whether the geometry checks passed (and which failed)
  * equipment counts per room and type vs the electrician's counts
  * voltage drop and maximum demand outcome

It never falls back to mock data: with --provider gemini/openai and no API key it stops.
The report is written to eval_report.md and eval_report.json.

Usage (from backend/):
    python -m tools.evaluate_plans --plans-dir eval_plans --provider gemini
    python -m tools.evaluate_plans --self-test        # harness check using the mock provider

Reference file format: see eval_plans/README.md
"""
import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional

PLAN_EXTENSIONS = (".png", ".jpg", ".jpeg", ".pdf")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]+", " ", (name or "").lower()).strip()


def _iou(a: List[float], b: List[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    inter = w * h if w > 0 and h > 0 else 0.0
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _make_client(upload_dir: str):
    """TestClient on an isolated in-memory database."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models.analysis  # noqa: F401
    import app.models.material  # noqa: F401
    import app.models.project  # noqa: F401
    from app.core.config import settings
    from app.db.database import Base, get_db
    from app.main import app

    settings.UPLOAD_DIR = upload_dir
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def evaluate_plan(client, plan_path: str, reference: Dict[str, Any]) -> Dict[str, Any]:
    """Run one plan through the API and compare it with the reference. Pure function of its inputs."""
    name = os.path.splitext(os.path.basename(plan_path))[0]
    report: Dict[str, Any] = {"plan": name}

    pid = client.post("/api/projects", json={
        "name": name[:100] or "plan", "client": "Evaluation", "location": "Kigali",
        "building_type": reference.get("building_type", "Residential"),
    }).json()["id"]
    with open(plan_path, "rb") as fh:
        up = client.post(f"/api/projects/{pid}/plan", files={"file": (os.path.basename(plan_path), fh.read())})
    if up.status_code != 200:
        return {**report, "fatal": f"upload failed: {up.status_code} {up.text[:200]}"}

    scale = reference.get("scale")
    if scale:
        cal = client.put(f"/api/projects/{pid}/scale", json={
            "point_a": {"x_ratio": scale["point_a"][0], "y_ratio": scale["point_a"][1]},
            "point_b": {"x_ratio": scale["point_b"][0], "y_ratio": scale["point_b"][1]},
            "real_distance_mm": scale["real_distance_mm"],
        })
        report["scale_calibrated"] = cal.status_code == 200
    else:
        report["scale_calibrated"] = False

    res = client.post(f"/api/projects/{pid}/analyze")
    if res.status_code == 422 and isinstance(res.json().get("detail"), dict):
        issues = res.json()["detail"]["issues"]
        report["pipeline"] = "blocked_by_geometry_checks"
        report["geometry_errors"] = [i["message"] for i in issues if i["severity"] == "error"]
    elif res.status_code != 200:
        return {**report, "pipeline": "failed", "fatal": f"{res.status_code}: {str(res.json().get('detail'))[:300]}"}
    else:
        report["pipeline"] = "completed"
        report["geometry_errors"] = []

    # ---- rooms & doors (available even when the checks blocked generation) ------------------
    geo = client.get(f"/api/projects/{pid}/geometry")
    if geo.status_code == 200:
        g = geo.json()
        ai_rooms = g["rooms"]
        report["geometry_warnings"] = [i["message"] for i in g["issues"] if i["severity"] == "warning"]
        ref_rooms = reference.get("rooms", [])

        matches: Dict[int, Dict] = {}   # reference index -> ai room
        used = set()
        for ri, rr in enumerate(ref_rooms):
            best, best_score = None, 0.0
            for ar in ai_rooms:
                if ar["id"] in used:
                    continue
                score = 0.0
                if rr.get("bounds") and ar.get("bounds"):
                    score = _iou(rr["bounds"], ar["bounds"])
                    if score < 0.4:
                        score = 0.0
                elif _norm(rr["name"]) == _norm(ar["name"]):
                    score = 1.0
                if score > best_score:
                    best, best_score = ar, score
            if best:
                matches[ri] = best
                used.add(best["id"])

        report["rooms"] = {
            "reference": len(ref_rooms),
            "detected": len(ai_rooms),
            "matched": len(matches),
            "recall": round(len(matches) / len(ref_rooms), 2) if ref_rooms else None,
            "precision": round(len(matches) / len(ai_rooms), 2) if ai_rooms else None,
            "name_correct": sum(1 for ri, ar in matches.items() if _norm(ref_rooms[ri]["name"]) == _norm(ar["name"])),
            "wrong_names": [
                {"reference": ref_rooms[ri]["name"], "detected": ar["name"]}
                for ri, ar in matches.items() if _norm(ref_rooms[ri]["name"]) != _norm(ar["name"])
            ],
            "missed": [ref_rooms[i]["name"] for i in range(len(ref_rooms)) if i not in matches],
            "invented": [r["name"] for r in ai_rooms if r["id"] not in used],
        }
        doors = [f for f in g["features"] if f["type"] in ("door", "entrance")]
        report["doors"] = {"reference": reference.get("doors"), "detected": len(doors)}
    else:
        report["fatal"] = f"geometry unavailable: {geo.status_code}"
        return report
    if report["pipeline"] != "completed":
        return report

    # ---- optional distribution board so voltage drop can be assessed -----------------------
    db_ref = reference.get("distribution_board")
    if db_ref:
        add = client.post(f"/api/projects/{pid}/points", json={
            "type": "distribution_board", "x_ratio": db_ref["x_ratio"], "y_ratio": db_ref["y_ratio"]})
        report["distribution_board_placed"] = add.status_code == 201
        if add.status_code != 201:
            report["distribution_board_error"] = str(add.json().get("detail"))

    # ---- equipment ------------------------------------------------------------------------
    analysis = client.get(f"/api/projects/{pid}/analysis").json()
    points = analysis["electrical_points"]
    per_room: List[Dict] = []
    totals_ref: Dict[str, int] = {}
    totals_gen: Dict[str, int] = {}
    within_one = exact = compared = 0
    for ri, rr in enumerate(reference.get("rooms", [])):
        expected = rr.get("equipment")
        if not expected:
            continue
        ai = matches.get(ri)
        generated: Dict[str, int] = {}
        if ai:
            for p in points:
                if p["room_id"] == ai["id"]:
                    generated[p["type"]] = generated.get(p["type"], 0) + p["quantity"]
        row = {"room": rr["name"], "matched": bool(ai), "differences": {}}
        for t in sorted(set(expected) | set(generated)):
            e, g_ = expected.get(t, 0), generated.get(t, 0)
            totals_ref[t] = totals_ref.get(t, 0) + e
            totals_gen[t] = totals_gen.get(t, 0) + g_
            compared += 1
            within_one += abs(e - g_) <= 1
            exact += e == g_
            if e != g_:
                row["differences"][t] = {"electrician": e, "generated": g_}
        per_room.append(row)
    report["equipment"] = {
        "exact_match": round(exact / compared, 2) if compared else None,
        "within_one_of_electrician": round(within_one / compared, 2) if compared else None,
        "by_type": {t: {"electrician": totals_ref.get(t, 0), "generated": totals_gen.get(t, 0)}
                    for t in sorted(set(totals_ref) | set(totals_gen))},
        "per_room": per_room,
    }

    # ---- calculations ---------------------------------------------------------------------
    calc = client.get(f"/api/projects/{pid}/calculations")
    if calc.status_code == 200:
        c = calc.json()
        vd = c["voltage_drop"]
        md = c["max_demand"]
        report["calculations"] = {
            "voltage_drop_status": vd["status"],
            "voltage_drop_reason": vd.get("reason"),
            "voltage_drop_failing": [r["circuit_id"] for r in vd["circuits"] if r.get("status") == "fail"],
            "max_demand_a": md["total"]["total_demand_a"],
            "electrician_max_demand_a": reference.get("max_demand_a"),
            "max_demand_difference_percent": (
                round((md["total"]["total_demand_a"] - reference["max_demand_a"]) / reference["max_demand_a"] * 100, 1)
                if reference.get("max_demand_a") else None
            ),
            "circuits_generated": len(analysis["circuits"]),
            "circuits_electrician": reference.get("circuits"),
        }
    return report


def render_markdown(reports: List[Dict[str, Any]], provider: str) -> str:
    lines = ["# VoltPlan evaluation report", "", f"AI provider: **{provider}**"
             + ("  \n> MOCK PROVIDER: results do not reflect real plan reading." if provider == "mock" else ""), ""]
    for r in reports:
        lines += [f"## {r['plan']}", ""]
        if r.get("fatal"):
            lines += [f"**FAILED:** {r['fatal']}", ""]
            continue
        lines.append(f"- Pipeline: **{r.get('pipeline')}**; scale calibrated: {r.get('scale_calibrated')}")
        if r.get("geometry_errors"):
            lines.append("- Geometry checks blocked generation:")
            lines += [f"  - {m}" for m in r["geometry_errors"]]
        rooms = r.get("rooms")
        if rooms:
            lines.append(f"- Rooms: {rooms['matched']}/{rooms['reference']} matched (recall {rooms['recall']}, "
                         f"precision {rooms['precision']}); names correct {rooms['name_correct']}/{rooms['matched']}")
            if rooms["wrong_names"]:
                lines.append("  - wrong names: " + "; ".join(f"{w['reference']} -> {w['detected']}" for w in rooms["wrong_names"]))
            if rooms["missed"]:
                lines.append("  - missed rooms: " + ", ".join(rooms["missed"]))
            if rooms["invented"]:
                lines.append("  - rooms not in the electrician's design: " + ", ".join(rooms["invented"]))
        if r.get("doors"):
            lines.append(f"- Doors: detected {r['doors']['detected']} vs electrician {r['doors']['reference']}")
        eq = r.get("equipment")
        if eq:
            lines.append(f"- Equipment counts (room x type): exactly equal to the electrician {eq['exact_match']}, within +/-1 {eq['within_one_of_electrician']}")
            lines += ["", "| Equipment | Electrician | VoltPlan |", "|---|---:|---:|"]
            lines += [f"| {t} | {v['electrician']} | {v['generated']} |" for t, v in eq["by_type"].items()]
            lines.append("")
            for row in eq["per_room"]:
                if row["differences"]:
                    diff = ", ".join(f"{t}: {d['electrician']} vs {d['generated']}" for t, d in row["differences"].items())
                    lines.append(f"  - {row['room']}{'' if row['matched'] else ' (room not matched)'}: {diff}")
        calc = r.get("calculations")
        if calc:
            lines.append(f"- Voltage drop: {calc['voltage_drop_status']}"
                         + (f" ({calc['voltage_drop_reason']})" if calc.get("voltage_drop_reason") else "")
                         + (f"; failing: {', '.join(calc['voltage_drop_failing'])}" if calc["voltage_drop_failing"] else ""))
            lines.append(f"- Maximum demand: {calc['max_demand_a']} A"
                         + (f" vs electrician {calc['electrician_max_demand_a']} A ({calc['max_demand_difference_percent']:+}%)"
                            if calc.get("electrician_max_demand_a") else ""))
        lines.append("")
    return "\n".join(lines)


def run(plans_dir: str, provider: Optional[str], out_prefix: str) -> List[Dict[str, Any]]:
    from app.core.config import settings

    if provider:
        settings.AI_PROVIDER = provider
    provider = settings.AI_PROVIDER.lower()
    key_needed = {"gemini": settings.GEMINI_API_KEY, "openai": settings.OPENAI_API_KEY}
    if provider in key_needed and not key_needed[provider]:
        sys.exit(f"AI_PROVIDER is '{provider}' but its API key is not set (backend/.env). Refusing to fall back to mock data.")

    plans = sorted(
        os.path.join(plans_dir, f) for f in os.listdir(plans_dir)
        if f.lower().endswith(PLAN_EXTENSIONS)
        and os.path.exists(os.path.join(plans_dir, os.path.splitext(f)[0] + ".reference.json"))
    )
    if not plans:
        sys.exit(f"No plans with a .reference.json found in '{plans_dir}'. See eval_plans/README.md.")

    work = tempfile.mkdtemp(prefix="voltplan_eval_")
    previous_upload_dir = settings.UPLOAD_DIR
    try:
        client = _make_client(work)
        reports = []
        for plan in plans:
            with open(os.path.splitext(plan)[0] + ".reference.json", encoding="utf-8") as fh:
                reference = json.load(fh)
            print(f"Evaluating {os.path.basename(plan)} ...", flush=True)
            reports.append(evaluate_plan(client, plan, reference))
    finally:
        from app.main import app
        app.dependency_overrides.clear()
        settings.UPLOAD_DIR = previous_upload_dir
        shutil.rmtree(work, ignore_errors=True)

    with open(out_prefix + ".json", "w", encoding="utf-8") as fh:
        json.dump({"provider": provider, "plans": reports}, fh, indent=2)
    with open(out_prefix + ".md", "w", encoding="utf-8") as fh:
        fh.write(render_markdown(reports, provider))
    print(f"Wrote {out_prefix}.md and {out_prefix}.json")
    return reports


def _self_test(out_prefix: str) -> None:
    """Exercise the harness end to end with the mock provider and a synthetic plan."""
    from PIL import Image

    d = tempfile.mkdtemp(prefix="voltplan_selftest_")
    try:
        Image.new("RGB", (800, 600), (255, 255, 255)).save(os.path.join(d, "synthetic.png"))
        reference = {
            "building_type": "Residential",
            "rooms": [
                {"name": "Living Room", "equipment": {"lighting": 2, "twin_socket": 4}},
                {"name": "Kitchen & Dining", "equipment": {"cooker_point": 1}},
                {"name": "Utility", "equipment": {"lighting": 1}},
            ],
            "doors": 6,
            "max_demand_a": 60,
        }
        with open(os.path.join(d, "synthetic.reference.json"), "w", encoding="utf-8") as fh:
            json.dump(reference, fh)
        run(d, "mock", out_prefix)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plans-dir", default="eval_plans")
    parser.add_argument("--provider", choices=["gemini", "openai", "mock"], default=None,
                        help="override AI_PROVIDER from backend/.env")
    parser.add_argument("--out", default="eval_report", help="report path prefix")
    parser.add_argument("--self-test", action="store_true", help="check the harness with the mock provider")
    args = parser.parse_args()
    if args.self_test:
        _self_test(args.out)
    else:
        run(args.plans_dir, args.provider, args.out)


if __name__ == "__main__":
    main()
