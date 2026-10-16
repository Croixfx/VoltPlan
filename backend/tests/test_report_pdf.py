import io

from PIL import Image


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def _analysed_project(client, calibrate=True):
    pid = client.post("/api/projects", json={
        "name": "Report Villa", "client": "Kigali Developer Ltd", "building_type": "Residential",
        "location": "Nyarutarama, Kigali", "standard": "RS IEC 60364", "notes": "",
    }).json()["id"]
    client.post(f"/api/projects/{pid}/plan", files={"file": ("villa.png", _png(), "image/png")})
    if calibrate:
        cal = client.put(f"/api/projects/{pid}/scale", json={
            "point_a": {"x_ratio": 0.1, "y_ratio": 0.5}, "point_b": {"x_ratio": 0.6, "y_ratio": 0.5},
            "real_distance_mm": 10000})
        assert cal.status_code == 200, cal.text
    assert client.post(f"/api/projects/{pid}/analyze").status_code == 200
    return pid


def test_report_is_a_real_pdf_with_the_whole_design(client):
    pid = _analysed_project(client)
    res = client.get(f"/api/projects/{pid}/report.pdf")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert "VoltPlan_Report_Villa_Report.pdf" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(res.content)
    assert len(pdf) >= 4
    text = "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
    for expected in ["Report Villa", "Kigali Developer Ltd", "Circuit schedule", "Bill of quantities",
                     "Voltage drop", "Estimated total", "Engineer sign-off", "licensed electrical engineer"]:
        assert expected in text, expected
    # the demo provider's data must be flagged, never passed off as a real design
    assert "DEMO" in text.upper()
    # a calibrated project must not carry the "not calibrated" warning
    assert "has not been calibrated" not in text


def test_report_says_when_the_scale_is_not_calibrated(client):
    pid = _analysed_project(client, calibrate=False)
    res = client.get(f"/api/projects/{pid}/report.pdf")
    assert res.status_code == 200
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(res.content)
    text = pdf[0].get_textpage().get_text_range()
    assert "has not been calibrated" in text


def test_report_needs_an_analysis(client):
    pid = client.post("/api/projects", json={
        "name": "Empty project", "client": "Some Client", "building_type": "Residential", "location": "Kigali",
        "standard": "RS IEC 60364", "notes": ""}).json()["id"]
    assert client.get(f"/api/projects/{pid}/report.pdf").status_code == 409
    assert client.get("/api/projects/nope/report.pdf").status_code == 404
