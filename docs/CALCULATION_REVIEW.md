# Electrical calculations: review pack for the electrician

VoltPlan calculates **voltage drop per final circuit** and **maximum demand** for the main supply
(`backend/app/services/electrical_calculations.py`, endpoint `GET /api/projects/{id}/calculations`).

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

Cable **current-carrying capacity** (installation method, grouping, thermal insulation, ambient temperature),
protective-device discrimination, short-circuit / earth-fault loop impedance, RCD selectivity, three-phase balance of
each circuit. ⚠ Please tell me which of these the client expects.

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

## 3. Review checklist

Please tick, correct or comment on each line.

- [ ] Resistivity 0.0225 Ω·mm²/m at 70 °C is acceptable (or give the value you use)
- [ ] Limits 3 % / 5 % are right for Rwanda (and whether to measure from the meter or from the board)
- [ ] Ib for socket circuits = device rating is acceptable
- [ ] Ceiling height 2.7 m, bend allowance 1.10, board height 1.5 m
- [ ] "Whole load at the farthest point" is an acceptable upper bound
- [ ] Household diversity table (66 % / 100 %+40 % / cooker rule) is the one you apply
- [ ] No diversity for non-residential is acceptable as a conservative default
- [ ] Standard rating list for the main switch
- [ ] Anything that is missing and must be calculated (cable ratings Iz, earth-fault loop, ...)

Reviewed by: ____________________  Registration no.: ____________  Date: ____________

---

## 4. Findings from real plans

*(fill in after running `python -m tools.evaluate_plans`, see `backend/eval_plans/README.md`)*

| Plan | Rooms matched | Names right | Corrections needed in the editor | Equipment within ±1 | Max demand vs electrician | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |
