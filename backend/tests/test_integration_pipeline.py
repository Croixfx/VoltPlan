import io
import pytest
from PIL import Image


def _create_test_image_bytes():
    file_bytes = io.BytesIO()
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    img.save(file_bytes, format="PNG")
    file_bytes.seek(0)
    return file_bytes


def test_full_end_to_end_pipeline(client):
    # 1. Create a project
    create_payload = {
        "name": "Integration Villa",
        "client": "Kigali Developer Ltd",
        "building_type": "Residential",
        "location": "Nyarutarama, Kigali",
        "standard": "RS IEC 60364",
        "notes": "Full end to end test project",
    }
    res = client.post("/api/projects", json=create_payload)
    assert res.status_code == 201
    proj_data = res.json()
    project_id = proj_data["id"]
    assert proj_data["status"] == "created"

    # 2. Upload architectural floor plan file
    img_bytes = _create_test_image_bytes()
    upload_res = client.post(
        f"/api/projects/{project_id}/plan",
        files={"file": ("villa_plan.png", img_bytes, "image/png")},
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["status"] == "uploaded"
    assert upload_data["floor_plan_name"] == "villa_plan.png"

    # Verify download of rendered display plan file
    file_res = client.get(f"/api/projects/{project_id}/plan/file")
    assert file_res.status_code == 200
    assert file_res.headers["content-type"].startswith("image/")

    # 3. Trigger analysis pipeline
    analyze_res = client.post(f"/api/projects/{project_id}/analyze")
    assert analyze_res.status_code == 200
    status_data = analyze_res.json()
    assert status_data["project_id"] == project_id
    assert status_data["status"] == "completed"

    # 4. Check analysis status endpoint
    status_check = client.get(f"/api/projects/{project_id}/analysis/status")
    assert status_check.status_code == 200
    assert status_check.json()["status"] == "completed"

    # 5. Retrieve full structured analysis results
    analysis_res = client.get(f"/api/projects/{project_id}/analysis")
    assert analysis_res.status_code == 200
    analysis = analysis_res.json()

    assert analysis["project_id"] == project_id
    assert analysis["status"] == "completed"
    assert analysis["standard_applied"] == "RS IEC 60364"

    # Verify rooms extracted by AI vision
    assert len(analysis["rooms"]) > 0
    room_names = [r["name"] for r in analysis["rooms"]]
    assert "Living Room" in room_names
    assert any("Kitchen" in r for r in room_names)

    # Verify architectural features
    assert len(analysis["architectural_features"]) > 0

    # Verify deterministic electrical points
    assert len(analysis["electrical_points"]) > 0
    for pt in analysis["electrical_points"]:
        assert pt["id"] is not None
        assert pt["room_name"] is not None
        assert pt["circuit_id"] is not None
        assert pt["recommended_cable"] is not None
        assert pt["recommended_protection"] is not None

    # Verify circuits
    assert len(analysis["circuits"]) > 0
    circuit_types = set(c["circuit_type"] for c in analysis["circuits"])
    assert "lighting" in circuit_types
    assert "power" in circuit_types

    # Verify BOQ items
    assert len(analysis["boq_items"]) > 0

    # Verify Cost Estimate
    assert analysis["cost_estimate"] is not None
    assert analysis["cost_estimate"]["currency"] == "RWF"
    assert analysis["cost_estimate"]["grand_total_rwf"] > 0
    assert analysis["cost_estimate"]["labor_cost_rwf"] > 0
    assert analysis["cost_estimate"]["contingency_cost_rwf"] > 0

    # Verify mandatory engineering disclaimer
    assert "RS IEC 60364" in analysis["engineering_disclaimer"]
    assert "certified" in analysis["engineering_disclaimer"].lower() or "professional" in analysis["engineering_disclaimer"].lower()

    # 6. Test dedicated BOQ endpoint
    boq_res = client.get(f"/api/projects/{project_id}/boq")
    assert boq_res.status_code == 200
    boq_data = boq_res.json()
    assert boq_data["project_id"] == project_id
    assert len(boq_data["items"]) == len(analysis["boq_items"])
    assert boq_data["materials_subtotal_rwf"] > 0

    # 7. Test dedicated Cost Estimate endpoint
    cost_res = client.get(f"/api/projects/{project_id}/cost-estimate")
    assert cost_res.status_code == 200
    cost_data = cost_res.json()
    assert cost_data["grand_total_rwf"] == analysis["cost_estimate"]["grand_total_rwf"]
