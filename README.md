# VoltPlan

**AI-Assisted Electrical Planning & Estimation for Building Professionals**

VoltPlan is a commercial-grade mobile application built in Flutter with clean, feature-based architecture and a precision engineering aesthetic inspired by Linear, Figma, and Autodesk.

---

## Technical Specifications

- **Framework**: Flutter 3.44+ / Dart 3.12+
- **Design System**: Material 3 with Precision Light & Dark themes
- **Architecture**: Clean feature-based modular architecture
- **Regional Context**: Rwandan construction standards (RS IEC 60364 / BS 7671) and Rwandan Franc (RWF) currency pricing
- **Status**: Production UI/UX & Frontend Architecture (Phase 1)

---

## 13 Implemented Screens & Workflows

1. **Dashboard (`Screen 1`)**:
   - Personalized engineer greeting, notifications trigger, and quick stats (`Active Projects`, `Completed Analyses`, `Estimated Projects`).
   - Primary `+ New Project` CTA and recent projects list with status pills.

2. **Projects Directory (`Screen 2`)**:
   - Real-time search by project name, client, or location.
   - Status filtering chips (`In Progress`, `Completed`, `Review Required`).
   - Project cards and floating add action.

3. **Create Project (`Screen 3`)**:
   - Engineering project specification form (`Project Name`, `Client Name`, `Building Type`, `Location`, `Electrical Standard`, `Notes`).
   - Form validation and direct routing to Project Overview.

4. **Project Overview (`Screen 4`)**:
   - 6-step visual progress timeline (`1. Floor Plan → 2. AI Analysis → 3. Electrical Design → 4. BOQ → 5. Cost Estimate → 6. Report`).
   - Architectural plan preview card and direct module navigation grid.

5. **Upload Floor Plan (`Screen 5`)**:
   - High-density dropzone supporting PDF, PNG, and JPG up to 25 MB.
   - Pre-configured realistic sample drawings for instant testing.

6. **AI Analysis Simulation (`Screen 6`)**:
   - Multi-stage analysis animation (`Uploading → Reading drawing → Detecting rooms → Electrical requirements → Recommendations`).
   - Extraction summary: 8 Rooms Detected, 24 Points, 5 Circuits, 1 Main Distribution Board.

7. **Electrical Recommendations (`Screen 7`)**:
   - AI recommendations grouped by room (`Living Room`, `Kitchen`, `Master Bedroom`, `Corridor`, `Bathroom`, `Veranda`).
   - Status indicators (`Recommended`, `Preliminary`, `Review Required`) and engineering advisory disclaimers.
   - Tap-to-inspect bottom sheet for each component.

8. **Electrical Plan Canvas (`Screen 8`)**:
   - Interactive zoomable (`0.6x` to `4.0x`) and pannable vector architectural drawing canvas using `InteractiveViewer`.
   - Crisp rendering of walls, doors, windows, dimensions, and room labels.
   - Overlay electrical symbols (Sockets, Lights, Switches, DB, Appliances) with tap-to-inspect engineering bottom sheets.
   - Layer visibility filters (`All`, `Lighting`, `Power Sockets`, `Distribution Board`).

9. **Circuits Schedule (`Screen 9`)**:
   - Consumer unit load summary (`Total kW`, `Diversity Factor 0.65`, `Main Incomer 63A RCD`).
   - Circuit breakdown cards (`LGT-01`, `SOCKET-01`, `KITCHEN-01`, `WATER-HEATER`, `SPARE-01`) with cable gauge and MCB ratings.

10. **Bill of Quantities / BOQ (`Screen 10`)**:
    - Itemized material schedule with category filters (`Cables`, `Lighting`, `Switches`, `Sockets`, `Protection`, `DB`, `Conduits`, `Accessories`).
    - Interactive quantity editor dynamically recalculating line and category totals in RWF.

11. **Cost Estimate (`Screen 11`)**:
    - Grand estimate banner in Rwandan Francs (`RWF`).
    - Visual budget breakdown bar (`Materials ~60%`, `Labor ~28%`, `Contingency ~12%`).
    - Supplier verification disclaimer.

12. **Engineering Report (`Screen 12`)**:
    - Comprehensive client-ready summary document preview.
    - Animated mock PDF generator modal with download and share actions.

13. **Profile & Settings (`Screen 13`)**:
    - Engineer profile (`Eng. Patrick Mugabo`, RURA certified).
    - Regional electrical standard selector (`RS IEC 60364`, `BS 7671`, `NEC`).
    - Metric / Imperial unit system toggle.
    - Dark mode switch with instant live theme transition.

---

## Running the Application

To run the application on your desired device:

```bash
# Analyze code quality (0 errors / 0 warnings)
flutter analyze

# Run unit and widget test suites
flutter test

# Run on Chrome
flutter run -d chrome

# Run on Windows Desktop
flutter run -d windows

# Run on connected Android / iOS device
flutter run
```
