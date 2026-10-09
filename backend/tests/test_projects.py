def test_create_and_get_project(client):
    payload = {
        "name": "Kicukiro Modern Villa",
        "client": "Jean-Paul Habimana",
        "building_type": "Residential",
        "location": "Kigali, Kicukiro",
        "standard": "RS IEC 60364",
        "notes": "3-bedroom residential property with backup generator provision.",
    }
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["id"] is not None
    assert created["name"] == "Kicukiro Modern Villa"
    assert created["status"] == "created"

    # Get by ID
    get_res = client.get(f"/api/projects/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["client"] == "Jean-Paul Habimana"


def test_list_and_search_projects(client):
    client.post(
        "/api/projects",
        json={
            "name": "Nyarutarama Residence",
            "client": "Marie Claire",
            "building_type": "Residential",
            "location": "Kigali, Gasabo",
            "standard": "RS IEC 60364",
        },
    )
    client.post(
        "/api/projects",
        json={
            "name": "Inzovu Commercial Plaza",
            "client": "Inzovu Properties Ltd",
            "building_type": "Commercial",
            "location": "Kigali, Nyarugenge",
            "standard": "RS IEC 60364",
        },
    )

    # List all
    res = client.get("/api/projects")
    assert res.status_code == 200
    assert len(res.json()) >= 2

    # Filter by search
    res_search = client.get("/api/projects?q=Inzovu")
    assert res_search.status_code == 200
    results = res_search.json()
    assert len(results) == 1
    assert results[0]["name"] == "Inzovu Commercial Plaza"


def test_update_and_delete_project(client):
    create_res = client.post(
        "/api/projects",
        json={
            "name": "Old Project",
            "client": "Old Client",
            "building_type": "Residential",
            "location": "Kigali",
            "standard": "RS IEC 60364",
        },
    )
    proj_id = create_res.json()["id"]

    # Patch
    patch_res = client.patch(f"/api/projects/{proj_id}", json={"name": "Renovated Project", "notes": "Updated scope"})
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Renovated Project"
    assert patch_res.json()["notes"] == "Updated scope"

    # Delete
    del_res = client.delete(f"/api/projects/{proj_id}")
    assert del_res.status_code == 204

    # Verify not found
    get_res = client.get(f"/api/projects/{proj_id}")
    assert get_res.status_code == 404
