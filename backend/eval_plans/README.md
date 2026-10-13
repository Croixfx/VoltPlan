# Evaluating VoltPlan on real plans

Use 3-5 floor plans for which an electrician has **already produced the electrical design**.
For each plan, put the drawing and the electrician's counts side by side:

```
eval_plans/
  house_a.png                 <- the architectural plan (png / jpg / pdf)
  house_a.reference.json      <- the electrician's design, in the format below
  house_b.pdf
  house_b.reference.json
```

Then, from `backend/`:

```bash
# 1. put your key in backend/.env:  AI_PROVIDER=gemini  GEMINI_API_KEY=...   (or openai)
python -m tools.evaluate_plans --plans-dir eval_plans
# -> eval_report.md (read this) and eval_report.json
```

With a real provider and no key the tool stops; it never substitutes mock data.
`python -m tools.evaluate_plans --self-test` checks the tool itself with the mock provider.

> Do not commit client drawings. `eval_plans/*.png|jpg|pdf` and `*.reference.json` are git-ignored.

## Reference file

All coordinates are **ratios of the image** (0-1, origin top-left), as the app uses.

```json
{
  "building_type": "Residential",
  "scale": {
    "point_a": [0.10, 0.92],
    "point_b": [0.62, 0.92],
    "real_distance_mm": 9400
  },
  "rooms": [
    {
      "name": "Living Room",
      "bounds": [0.06, 0.06, 0.52, 0.48],
      "equipment": { "lighting": 2, "twin_socket": 4, "switch_1way": 1, "smoke_detector": 1, "tv_point": 1 }
    },
    {
      "name": "Kitchen",
      "bounds": [0.54, 0.06, 0.94, 0.48],
      "equipment": { "lighting": 2, "twin_socket": 4, "cooker_point": 1, "extractor_fan": 1 }
    }
  ],
  "doors": 6,
  "distribution_board": { "x_ratio": 0.50, "y_ratio": 0.55 },
  "circuits": 7,
  "max_demand_a": 48
}
```

| Field | Needed for |
|---|---|
| `rooms[].name` | matching the AI's rooms to the electrician's, and checking names |
| `rooms[].bounds` | optional; if given, rooms are matched by overlap (IoU >= 0.4) instead of by name |
| `rooms[].equipment` | optional; counts per catalog type (`lighting`, `twin_socket`, `single_socket`, `switch_1way`, `switch_2way`, `cooker_point`, `water_heater`, `ac_point`, `extractor_fan`, `outdoor_light`, `smoke_detector`, `emergency_light`, `data_point`, `tv_point`) |
| `scale` | optional; two points on the drawing and the real distance. Without it, voltage drop is reported as "not calculated" |
| `distribution_board` | optional; where the electrician put the board. Without it, voltage drop is reported as "not calculated" |
| `doors`, `circuits`, `max_demand_a` | optional comparison figures |

## How to read the report

* **Pipeline: blocked_by_geometry_checks** means the AI's rooms/doors failed the pre-generation checks
  (overlaps, doors off walls, implausible sizes). That is the tool doing its job; open the project in the
  app, fix the rooms/doors in the editor, regenerate, and note how many corrections were needed.
* **Rooms recall / precision** and **wrong names** show how well the AI reads the drawing.
* **Equipment counts** compare generated vs the electrician's, per room and type. Differences are not
  automatically errors in VoltPlan: record which side was right and why (code, client preference, ...).
* **Maximum demand** compares VoltPlan's figure with the electrician's. Ask the electrician which diversity
  rules they applied.

Record the outcomes in `docs/CALCULATION_REVIEW.md` (section "Findings from real plans").
