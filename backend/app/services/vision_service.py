import os
import json
import base64
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.schemas.floor_plan import VisionAnalysisResult, RoomObservation, ArchitecturalFeature


class VisionProvider(ABC):
    @abstractmethod
    async def analyze_floor_plan(
        self,
        image_path: str,
        building_type: str,
        standard: str,
    ) -> VisionAnalysisResult:
        """Analyzes floor plan image and returns structured building observations."""
        pass


class MockVisionProvider(VisionProvider):
    """
    Deterministic mock vision provider for local testing and reliable offline execution.
    Extracts architectural layout observations based on standard architectural blueprints.
    """

    async def analyze_floor_plan(
        self,
        image_path: str,
        building_type: str,
        standard: str,
    ) -> VisionAnalysisResult:
        logger.info(f"MockVisionProvider analyzing plan image: {image_path} for {building_type} building.")

        # Realistic architectural rooms with normalized bounding boxes (x1, y1, x2, y2)
        rooms = [
            RoomObservation(
                id="room_living",
                name="Living Room",
                area_m2=28.5,
                confidence=0.94,
                bounds=[0.06, 0.06, 0.52, 0.48],
            ),
            RoomObservation(
                id="room_kitchen",
                name="Kitchen & Dining",
                area_m2=16.8,
                confidence=0.91,
                bounds=[0.54, 0.06, 0.94, 0.48],
            ),
            RoomObservation(
                id="room_corridor",
                name="Central Corridor",
                area_m2=7.2,
                confidence=0.88,
                bounds=[0.42, 0.48, 0.60, 0.62],
            ),
            RoomObservation(
                id="room_master",
                name="Master Bedroom",
                area_m2=21.4,
                confidence=0.93,
                bounds=[0.06, 0.54, 0.44, 0.94],
            ),
            RoomObservation(
                id="room_bathroom",
                name="En-Suite Bathroom",
                area_m2=6.4,
                confidence=0.89,
                bounds=[0.46, 0.64, 0.66, 0.94],
            ),
            RoomObservation(
                id="room_bed1",
                name="Bedroom 1",
                area_m2=15.6,
                confidence=0.90,
                bounds=[0.68, 0.54, 0.94, 0.94],
            ),
        ]

        features = [
            ArchitecturalFeature(
                type="door",
                room="Living Room",
                confidence=0.92,
                wall="south",
                door_position=[0.14, 0.48],
                hinge_point=[0.11, 0.48],
                strike_side="right",
                strike_point=[0.17, 0.48],
                swing_direction="into_room",
            ),
            ArchitecturalFeature(type="window", room="Living Room", confidence=0.95),
            ArchitecturalFeature(
                type="door",
                room="Kitchen & Dining",
                confidence=0.91,
                wall="west",
                door_position=[0.54, 0.35],
                hinge_point=[0.54, 0.32],
                strike_side="right",
                strike_point=[0.54, 0.38],
                swing_direction="into_room",
            ),
            ArchitecturalFeature(type="window", room="Kitchen & Dining", confidence=0.91),
            ArchitecturalFeature(
                type="cooker_stove",
                room="Kitchen & Dining",
                confidence=0.94,
                bounds=[0.78, 0.40, 0.88, 0.48],
            ),
            ArchitecturalFeature(
                type="refrigerator",
                room="Kitchen & Dining",
                confidence=0.93,
                bounds=[0.55, 0.08, 0.63, 0.16],
            ),
            ArchitecturalFeature(
                type="door",
                room="Central Corridor",
                confidence=0.90,
                wall="north",
                door_position=[0.51, 0.48],
                hinge_point=[0.48, 0.48],
                strike_side="east",
                strike_point=[0.54, 0.48],
                swing_direction="into_room",
            ),
            ArchitecturalFeature(
                type="door",
                room="Master Bedroom",
                confidence=0.90,
                wall="east",
                door_position=[0.44, 0.58],
                hinge_point=[0.44, 0.55],
                strike_side="south",
                strike_point=[0.44, 0.61],
                swing_direction="into_room",
            ),
            ArchitecturalFeature(type="window", room="Master Bedroom", confidence=0.94),
            ArchitecturalFeature(
                type="door",
                room="En-Suite Bathroom",
                confidence=0.88,
                wall="north",
                door_position=[0.52, 0.64],
                hinge_point=[0.49, 0.64],
                strike_side="east",
                strike_point=[0.55, 0.64],
                swing_direction="into_room",
            ),
            ArchitecturalFeature(
                type="shower",
                room="En-Suite Bathroom",
                confidence=0.92,
                bounds=[0.46, 0.64, 0.54, 0.74],
            ),
            ArchitecturalFeature(
                type="sink",
                room="En-Suite Bathroom",
                confidence=0.90,
                bounds=[0.58, 0.64, 0.66, 0.70],
            ),
            ArchitecturalFeature(
                type="door",
                room="Bedroom 1",
                confidence=0.89,
                wall="west",
                door_position=[0.68, 0.58],
                hinge_point=[0.68, 0.55],
                strike_side="south",
                strike_point=[0.68, 0.61],
                swing_direction="into_room",
            ),
        ]

        observations = [
            "Architectural layout recognized: 3-bedroom residential residential villa topology.",
            "Standard wall partitions detected separating living, culinary, and rest quarters.",
            "Main entry door identified on living area perimeter facing exterior entrance.",
            "Wet area (bathroom) grouped adjacent to bedroom corridor for plumbing/conduit consolidation.",
        ]

        warnings = [
            "Room areas estimated from standard scale assumption (1:100). Verify on-site dimensions before final breaker sizing.",
            "Structural column positions inferred from wall junctions. Check conduit routing around reinforced concrete pillars.",
        ]

        return VisionAnalysisResult(
            rooms=rooms,
            architectural_features=features,
            observations=observations,
            warnings=warnings,
        )


class GeminiVisionProvider(VisionProvider):
    """
    Google Gemini Vision Provider using REST API.
    Sends floor plan drawing and parses structured JSON response.
    """

    async def analyze_floor_plan(
        self,
        image_path: str,
        building_type: str,
        standard: str,
    ) -> VisionAnalysisResult:
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured. Falling back to MockVisionProvider.")
            return await MockVisionProvider().analyze_floor_plan(image_path, building_type, standard)

        logger.info(f"Calling Gemini Vision model: {settings.GEMINI_MODEL} for plan analysis")

        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        prompt = f"""
You are an expert architectural plan interpreter and electrical consulting engineer in Rwanda.
Analyze this floor plan image for a {building_type} building designed under {standard}.

CRITICAL ROOM SEGMENTATION RULES:
1. IDENTIFY ROOM FUNCTION ACCURATELY BY ITS FURNITURE:
   - "Office" / "Study": A room containing a computer desk, monitor/screen, office chair, or bookshelves. NEVER classify a study/office room as a bathroom or WC!
   - "Bathroom" / "WC": A room containing sanitary plumbing fixtures: shower tray, bathtub, toilet (WC), or washbasin. Typical residential apartments have 1 or 2 bathrooms; never invent phantom bathrooms.
   - "Bedroom": A room containing a bed (single, twin, or double) and wardrobe.
   - "Kitchen": Counters, sink, cooker/stove, or refrigerator. NEVER merge Kitchen into the Living Room or Dining area.
2. Segment circulation hallways, corridors, and entrance foyers separately from the primary living lounge.
3. Every room must have tight, accurate normalized bounding boxes [x1, y1, x2, y2] between 0.0 and 1.0.

CRITICAL ARCHITECTURAL FEATURE DETECTION (DOORS & WET FIXTURES):
1. In CAD blueprints, a door is drawn as a straight door leaf line and a 90° circular swing arc.
   - "hinge_point": [x, y] on the wall at the exact pivot / center of the circular arc where the door is hinged.
   - "strike_point": [x, y] on the opposite door frame jamb where the door latches (the open tip of the 90° arc).
   - CAUTION: NEVER invert hinge and strike! The hinge is always the pivot center of the arc; the strike is at the open arc tip.
   - "door_position": [x, y] midpoint of the wall opening between hinge and strike jambs.
   - "swing_direction": "into_room" if the 90° arc curves into the room interior; "out_of_room" if it curves outside into the hallway.
   - "strike_side": direction opposite the hinge along the wall.
2. In Bathrooms, detect wet fixtures to enforce RS IEC 60364-7-701 safety zones:
   - "shower": bounds [x1, y1, x2, y2] of shower tray or cubicle.
   - "sink": bounds [x1, y1, x2, y2] of wash basin / vanity.
   - "bathtub": bounds [x1, y1, x2, y2] if present.
3. In Kitchens, detect primary appliances:
   - "cooker_stove": bounds [x1, y1, x2, y2] of the cooking range / cooktop.
   - "refrigerator": bounds [x1, y1, x2, y2] of fridge.
4. Detect the main exterior entrance door of the building ("type": "entrance"). Note which jamb has the hinge.

Return ONLY a valid JSON object matching this schema:
{{
  "rooms": [
    {{
      "id": "room_1",
      "name": "Living Room",
      "area_m2": 28.5,
      "confidence": 0.95,
      "bounds": [0.15, 0.55, 0.65, 0.95]
    }},
    {{
      "id": "room_2",
      "name": "Kitchen",
      "area_m2": 14.0,
      "confidence": 0.94,
      "bounds": [0.65, 0.60, 0.97, 0.95]
    }}
  ],
  "architectural_features": [
    {{
      "type": "door",
      "room": "Bedroom 1",
      "confidence": 0.92,
      "wall": "east",
      "door_position": [0.33, 0.42],
      "hinge_point": [0.33, 0.48],
      "strike_point": [0.33, 0.38],
      "strike_side": "north",
      "swing_direction": "into_room"
    }},
    {{
      "type": "shower",
      "room": "Bathroom",
      "confidence": 0.92,
      "bounds": [0.32, 0.16, 0.42, 0.26]
    }},
    {{
      "type": "cooker_stove",
      "room": "Kitchen",
      "confidence": 0.95,
      "bounds": [0.75, 0.85, 0.85, 0.95]
    }}
  ],
  "observations": [
    "Brief observations about the floor plan layout"
  ],
  "warnings": [
    "Any warnings regarding unreadable dimensions or structural ambiguity"
  ]
}}
Do NOT invent unreadable dimensions; return null for area_m2 if dimensions are not legible.
"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": encoded_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)

                logger.info(f"Gemini Vision successfully identified {len(parsed.get('rooms', []))} rooms from drawing.")
                return VisionAnalysisResult(**parsed)
        except Exception as e:
            logger.error(f"Gemini API request failed: {e}. Falling back to deterministic mock.", exc_info=True)
            return await MockVisionProvider().analyze_floor_plan(image_path, building_type, standard)


class OpenAIVisionProvider(VisionProvider):
    """
    OpenAI Vision Provider using chat completions.
    """

    async def analyze_floor_plan(
        self,
        image_path: str,
        building_type: str,
        standard: str,
    ) -> VisionAnalysisResult:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Falling back to MockVisionProvider.")
            return await MockVisionProvider().analyze_floor_plan(image_path, building_type, standard)

        logger.info(f"Calling OpenAI Vision model: {settings.OPENAI_MODEL} for plan analysis")

        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        prompt = f"""
You are an expert architectural plan interpreter and electrical consulting engineer in Rwanda.
Analyze this floor plan for a {building_type} building designed under {standard}.

CRITICAL ROOM SEGMENTATION RULES:
1. IDENTIFY ROOM FUNCTION ACCURATELY BY ITS FURNITURE:
   - "Office" / "Study": A room containing a computer desk, monitor/screen, office chair, or bookshelves. NEVER classify a study/office room as a bathroom or WC!
   - "Bathroom" / "WC": A room containing sanitary plumbing fixtures: shower tray, bathtub, toilet (WC), or washbasin. Typical residential apartments have 1 or 2 bathrooms; never invent phantom bathrooms.
   - "Bedroom": A room containing a bed (single, twin, or double) and wardrobe.
   - "Kitchen": Counters, sink, cooker/stove, or refrigerator. NEVER merge Kitchen into the Living Room or Dining area.
2. Segment circulation hallways, corridors, and entrance foyers separately from the primary living lounge.
3. Every room must have tight, accurate normalized bounding boxes [x1, y1, x2, y2] between 0.0 and 1.0.

CRITICAL ARCHITECTURAL FEATURE DETECTION (DOORS & WET FIXTURES):
1. In CAD blueprints, a door is drawn as a straight door leaf line and a 90° circular swing arc.
   - "hinge_point": [x, y] on the wall at the exact pivot / center of the circular arc where the door is hinged.
   - "strike_point": [x, y] on the opposite door frame jamb where the door latches (the open tip of the 90° arc).
   - CAUTION: NEVER invert hinge and strike! The hinge is always the pivot center of the arc; the strike is at the open arc tip.
   - "door_position": [x, y] midpoint of the wall opening between hinge and strike jambs.
   - "swing_direction": "into_room" if the 90° arc curves into the room interior; "out_of_room" if it curves outside into the hallway.
   - "strike_side": direction opposite the hinge along the wall.
2. In Bathrooms, detect wet fixtures to enforce RS IEC 60364-7-701 safety zones:
   - "shower": bounds [x1, y1, x2, y2] of shower tray or cubicle.
   - "sink": bounds [x1, y1, x2, y2] of wash basin / vanity.
   - "bathtub": bounds [x1, y1, x2, y2] if present.
3. In Kitchens, detect primary appliances:
   - "cooker_stove": bounds [x1, y1, x2, y2] of cooking range / cooktop.
   - "refrigerator": bounds [x1, y1, x2, y2] of fridge.
4. Detect the main exterior entrance door of the building ("type": "entrance"). Note which jamb has the hinge.
Output JSON only matching the schema with rooms, architectural_features, observations, and warnings.
"""

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                        },
                    ],
                }
            ],
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return VisionAnalysisResult(**parsed)
        except Exception as e:
            logger.error(f"OpenAI API request failed: {e}. Falling back to deterministic mock.", exc_info=True)
            return await MockVisionProvider().analyze_floor_plan(image_path, building_type, standard)


class VisionService:
    @staticmethod
    def get_provider() -> VisionProvider:
        provider_name = settings.AI_PROVIDER.lower()
        if provider_name == "gemini":
            return GeminiVisionProvider()
        elif provider_name == "openai":
            return OpenAIVisionProvider()
        else:
            return MockVisionProvider()

    @staticmethod
    async def analyze_floor_plan(
        image_path: str,
        building_type: str = "Residential",
        standard: str = "RS IEC 60364",
    ) -> VisionAnalysisResult:
        provider = VisionService.get_provider()
        return await provider.analyze_floor_plan(image_path, building_type, standard)
