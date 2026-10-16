import pytest

from app.engineering_rules.registry import UnsupportedStandardError, get_engineering_standard

PROJECT = {"name": "Standards test", "client": "Some Client", "building_type": "Residential",
           "location": "Kigali", "notes": ""}


@pytest.mark.parametrize("name", ["BS 7671 (18th Edition IET Wiring Regulations)", "NEC 2023 (NFPA 70)", "", "made up"])
def test_unsupported_standards_never_fall_back_to_iec(name):
    with pytest.raises(UnsupportedStandardError) as e:
        get_engineering_standard(name)
    assert "RS IEC 60364" in str(e.value)


@pytest.mark.parametrize("name", ["RS IEC 60364", "IEC 60364", "RS IEC 60364 (Rwanda Standards / IEC)", " RS IEC 60364 "])
def test_supported_names_resolve(name):
    assert get_engineering_standard(name).get_standard_code()


def test_a_project_cannot_be_created_for_a_standard_without_rules(client):
    res = client.post("/api/projects", json={**PROJECT, "standard": "NEC 2023 (NFPA 70)"})
    assert res.status_code == 422
    assert "not supported yet" in res.text
    assert client.post("/api/projects", json={**PROJECT, "standard": "RS IEC 60364"}).status_code == 201


def test_changing_a_project_to_an_unsupported_standard_is_refused(client):
    pid = client.post("/api/projects", json={**PROJECT, "standard": "RS IEC 60364"}).json()["id"]
    res = client.patch(f"/api/projects/{pid}", json={"standard": "BS 7671"})
    assert res.status_code == 422
    assert client.get(f"/api/projects/{pid}").json()["standard"] == "RS IEC 60364"
