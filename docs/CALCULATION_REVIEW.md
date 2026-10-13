# Electrical calculations: review pack for the electrician

VoltPlan calculates **voltage drop per final circuit** and **maximum demand** for the main supply
(`backend/app/services/electrical_calculations.py`, endpoint `GET /api/projects/{id}/calculations`), plus the
**cable current-carrying capacity** check (section 3).

These are preliminary aids. **Nothing here has been verified by a qualified electrician yet.**
This document lists every formula, constant and assumption so you can confirm or correct them.
Anything marked ⚠ is a judgement call that I (the developer) made and would like you to decide.

---

## 1. Voltage drop

### Formula (per circuit)

```
dV  = 2 x Ib x L x rho / S            [volts, single-phase, copper]
dV% = dV / 230 x 100
```

| Symbol | Meaning | Value / source |
|---|---|---|
| Ib | design current | see "Design current" below |
| L | cable length, board to farthest point | see "Length" below |
| S | conductor cross-section (mm²) | read from the circuit's cable, e.g. `3 x 2.5 mm²` → 2.5 |
| rho | copper resistivity at 70 °C | **0.0225 Ω·mm²/m** (1.25 × 0.018) |
| 230 V | supply voltage | single-phase, line to neutral |

Reactance is neglected (valid for S ≤ 50 mm²). The formula gives 18 mV/A/m for 2.5 mm² and 30 mV/A/m for 1.5 mm²;
BS 7671 Table 4D2B lists 18 and 29, so the result is equal or slightly conservative.

### Limits ⚠

| Circuit | Limit | Source used |
|---|---|---|
| lighting and safety lighting (smoke / emergency) | **3 %** | IEC 60364-5-52 Table G.57.1, BS 7671 App. 4 |
| everything else | **5 %** | same |

* Status is `pass` ≤ 80 % of the limit, `marginal` between 80 % and 100 %, `fail` above the limit.
* The limit applies to the drop **from the origin of the installation**. VoltPlan only calculates the final circuit from the
  distribution board, so any drop in the incoming cable / sub-main must be **added by you**. ⚠ Rwanda's utility
  (EUCL/REG) may set its own limits: please confirm.

### Design current Ib ⚠

* **Socket circuits:** Ib = rating of the protective device (e.g. 20 A). The real load behind a socket is unknown, so
  the full rating is used. This is conservative.
* **All other circuits:** Ib = sum of the connected loads / 230 V (air-conditioning at power factor 0.85).
  Lighting uses 60 W per luminaire (the catalog default), smoke detectors 5 W, etc.

### Length ⚠

```
L = (|dx| + |dy|) x 1.10  +  (2.7 - height of board)  +  (2.7 - height of outlet)
```

* `dx`, `dy`: horizontal distance (m) from the board to the **farthest point of the circuit**, measured on the calibrated plan.
* 1.10: allowance for bends and slack (cable follows walls, not straight lines).
* Vertical: ceiling height assumed **2.7 m**; board at 1.5 m, outlets at their catalog mounting heights
  (sockets 0.3 m, switches 1.1 m, ceiling items 2.7 m, ...).
* The **whole circuit load is placed at the farthest point**. For lighting radials and socket rings this overstates the drop.
* The board position is the point the user places on the plan. Without it, or without a calibrated scale, voltage drop is
  reported as **"not calculated"**. It is never estimated.

### Not checked

Protective-device discrimination, short-circuit withstand, earth-fault loop impedance, RCD selectivity, three-phase
balance of each circuit. (Cable current-carrying capacity is covered in section 3.) ⚠ Please tell me which of these
the client expects.

### Worked examples (these are automated tests: `backend/tests/test_electrical_calculations.py`)

**A. Lighting radial.** 10 × 60 W luminaires on 1.5 mm², farthest one 10 m east and 5 m north of the board.

```
Ib = 600 / 230                    = 2.609 A
L  = (10 + 5) x 1.10 + 1.2 + 0    = 17.7 m        (ceiling luminaire: no drop at the outlet)
dV = 2 x 2.609 x 17.7 x 0.0225 / 1.5 = 1.385 V = 0.60 %      limit 3 %  -> pass
```

**B. Long socket radial.** 20 A circuit, 2.5 mm², socket 40 m east of the board.

```
Ib = 20 A (device rating)
L  = 40 x 1.10 + 1.2 + 2.4        = 47.6 m
dV = 2 x 20 x 47.6 x 0.0225 / 2.5 = 17.14 V = 7.45 %          limit 5 %  -> FAIL
```

The tool then suggests the smallest standard section that meets the limit (4 mm² → 4.66 %).

---

## 2. Maximum demand

### Method ⚠

For **residential** projects, diversity from the IET On-Site Guide (BS 7671) Appendix 1, Table 1B (household):

| Group | Rule applied |
|---|---|
| Lighting (incl. safety lighting) | **66 %** of the total connected current |
| Socket circuits | **100 %** of the largest circuit + **40 %** of every other |
| Cooker | **10 A + 30 %** of the rest of the rated current **+ 5 A** (socket in the control unit) |
| Water heating, air conditioning, other fixed appliances | **100 %** (no diversity) |

For **any other building type no diversity is applied** (100 % of the design currents) because I have no sourced factors.
⚠ Please advise if you use a specific table for shops / offices / etc.

Demand is calculated for the whole installation and per phase (each circuit has an L1/L2/L3 assignment from the
circuit engine). Suggested main switch = **smallest standard rating ≥ demand** from
16, 20, 25, 32, 40, 50, 63, 80, 100, 125 A. Future load growth is **not** included.

IEC 60364 itself gives no fixed diversity factors. If the utility or your practice uses different factors, tell me and
they will be changed in one place (`electrical_calculations.py`, constants at the top).

### Worked example (automated test)

2 lighting circuits (2 × 600 W), 2 socket circuits (2 × 20 A), 6 kW cooker, 2.5 kW water heater:

```
Lighting  1200 / 230 x 0.66            =  3.44 A
Sockets   20 + 0.4 x 20                = 28.00 A
Cooker    10 + 0.3 x (26.09 - 10) + 5  = 19.83 A
Heater    2500 / 230                   = 10.87 A
Total                                  = 62.14 A  = 14.3 kVA at 230 V   -> 63 A rating
```

---

## 3. Cable current-carrying capacity

Endpoint: `GET /api/projects/{id}/calculations?method=B2&ambient_c=30&grouped_circuits=1`
(`cable_capacity` block). Unlike voltage drop it needs **no scale and no distribution board**: it only needs each
circuit's cable size and protective device.

### Check (IEC 60364-4-43, 5-52)

```
Ib <= In <= Iz          Iz = It x Ca x Cg
```

| Symbol | Meaning | Source |
|---|---|---|
| Ib | design current | as in section 1 (socket circuits: = In, an assumption) |
| In | rating of the protective device | read from the circuit, e.g. `20A Type B MCB` → 20 A |
| It | tabulated capacity of the cable | IEC 60364-5-52 Table B.52.2 (copper, PVC, two loaded conductors, 70 °C conductor, 30 °C ambient) |
| Ca | ambient-temperature factor | Table B.52.14 (PVC) |
| Cg | grouping factor | Table B.52.17 (circuits bunched in air / on a surface / embedded or enclosed) |

For IEC 60898 miniature circuit-breakers (conventional tripping current 1.45 × In) the second condition
I2 ≤ 1.45 × Iz is then also met. Status: `fail` if Ib > In or In > Iz; `marginal` if In is above 90 % of Iz; otherwise `pass`.
For a failing circuit the tool suggests the smallest standard cable that passes, or a smaller device that fits.
For every circuit it also reports `max_grouped_circuits`: how many circuits may share its route.

### Table values used ⚠ please verify against the standard

**Table B.52.2, amperes (copper, PVC, 2 loaded conductors, 30 °C)**

| mm² | A2 | B2 (default) | C |
|---|---:|---:|---:|
| 1.5 | 14 | 16.5 | 19.5 |
| 2.5 | 18.5 | 23 | 27 |
| 4 | 25 | 30 | 36 |
| 6 | 32 | 38 | 46 |
| 10 | 43 | 52 | 63 |
| 16 | 57 | 69 | 85 |
| 25 | 75 | 90 | 112 |

* Methods: **A2** multi-core cable in conduit in a thermally insulating wall; **B2** multi-core cable in conduit on a wall or
  embedded in masonry (assumed for concealed wiring in masonry); **C** cable clipped direct to a surface.
* I transcribed these from public web pages because I do not have the standard. **B2 and C rows agreed across two
  independent sources. The A2 row came from one source** and differs from the values in older editions of the
  table (13 / 17.5 / 23 / 29 / 39 / 52 / 68), so please confirm which edition Rwanda applies.
* Only copper PVC cables up to 25 mm² are tabulated; anything else is reported as "not calculated".

**Ambient factor Ca (Table B.52.14, PVC):** 30 °C → 1.00, 35 °C → 0.94, 40 °C → 0.87. These are the only values
offered; 35 and 40 °C were cross-checked against a public source.

**Grouping factor Cg (Table B.52.17):** 1 → 1.00, 2 → 0.80, 3 → 0.70, 4 → 0.65, 5 → 0.60, 6 → 0.57.
⚠ **These were NOT cross-checked against any source in this work**; they are the commonly published values.
More than 6 circuits is rejected rather than approximated.

### Assumptions ⚠

* Default installation: **method B2, 30 °C, circuits not bunched.** The plan does not show how cables are routed, so the
  number of circuits sharing a conduit is unknown. The user can change method, ambient and bunching on the Calculations
  screen; the result shows how many bunched circuits each cable tolerates.
* Thermal insulation around cables is only covered through method A2. Not covered: buried cables, cables above 25 mm²,
  three-phase circuits, harmonic currents, short-circuit withstand, earth-fault loop impedance.

### What the default design shows (please review) ⚠

With the circuit rules currently built into the generator, **the design only passes when circuits are not bunched**:

| Circuit | Cable / device | Iz (B2, alone) | Used | With 2 circuits bunched (Iz × 0.80) |
|---|---|---:|---:|---|
| Socket radials | 2.5 mm² / 20 A | 23 A | 87 % | 18.4 A → **fail** (use 4 mm² or a 16 A device) |
| Water heater | 2.5 mm² / 20 A | 23 A | 87 % | 18.4 A → **fail** |
| Cooker | 6 mm² / 32 A | 38 A | 84 % | 30.4 A → **fail** (use 10 mm²) |
| Lighting | 1.5 mm² / 10 A | 16.5 A | 61 % | 13.2 A → pass |
| Air conditioner | 2.5 mm² / 16 A | 23 A | 70 % | 18.4 A → pass |
| Detection / escape lighting | 1.5 mm² / 6 A | 16.5 A | 36 % | pass |

This is a design-rule question for the electrician: should the generator default to 16 A devices or 4 mm² cable on
radials, or is "2.5 mm² on 20 A, never bunched" acceptable in local practice?

### Worked examples (automated tests: `backend/tests/test_cable_capacity.py`)

**A.** 2.5 mm² on a 20 A device, method B2, alone: Iz = 23 × 1.00 × 1.00 = 23 A ≥ 20 A → pass (87 %).

**B.** Same cable with one more circuit bunched: Iz = 23 × 0.80 = 18.4 A < 20 A → **fail**; 4 mm² (30 × 0.80 = 24 A) or a 16 A device fixes it.

**C.** 1.5 mm² on 10 A at 40 °C with 6 circuits bunched: Iz = 16.5 × 0.87 × 0.57 = 8.18 A < 10 A → **fail**; 2.5 mm² gives 23 × 0.87 × 0.57 = 11.4 A → pass.

---

## 4. Review checklist

Please tick, correct or comment on each line.

- [ ] Resistivity 0.0225 Ω·mm²/m at 70 °C is acceptable (or give the value you use)
- [ ] Limits 3 % / 5 % are right for Rwanda (and whether to measure from the meter or from the board)
- [ ] Ib for socket circuits = device rating is acceptable
- [ ] Ceiling height 2.7 m, bend allowance 1.10, board height 1.5 m
- [ ] "Whole load at the farthest point" is an acceptable upper bound
- [ ] Household diversity table (66 % / 100 %+40 % / cooker rule) is the one you apply
- [ ] No diversity for non-residential is acceptable as a conservative default
- [ ] Standard rating list for the main switch
- [ ] Table B.52.2 values and the A2 / B2 / C row choice (section 3); which edition applies
- [ ] Grouping factors 1-6 circuits, and ambient factors 30 / 35 / 40 °C
- [ ] Default "method B2, 30 °C, not bunched" is acceptable, and whether 2.5 mm² on 20 A radials / 6 mm² on 32 A is
      acceptable when circuits are bunched
- [ ] Anything that is missing and must be calculated (earth-fault loop, short-circuit withstand, ...)

Reviewed by: ____________________  Registration no.: ____________  Date: ____________

---

## 5. Findings from real plans

*(fill in after running `python -m tools.evaluate_plans`, see `backend/eval_plans/README.md`)*

| Plan | Rooms matched | Names right | Corrections needed in the editor | Equipment within ±1 | Max demand vs electrician | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |
