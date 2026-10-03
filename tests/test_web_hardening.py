import io

from fastapi.testclient import TestClient

from ilgeojwo.config import load_config
from ilgeojwo.web.app import create_app


class FakeEngine:
    loaded = False

    def __init__(self, text="출입국관리사무소 체류기간 연장허가 신청", raises=None):
        self.text, self.raises = text, raises

    def read(self, path):
        if self.raises:
            raise self.raises
        return self.text


class FakeLlm:
    def __init__(self, reply="{}", raises=None):
        self.reply, self.raises = reply, raises

    def complete(self, prompt):
        if self.raises:
            raise self.raises
        return self.reply


def _png():
    return ("a.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")


def _client(tmp_path, engine=None, llm=None, token=None):
    cfg = load_config(env={"ILGEOJWO_DB": str(tmp_path / "t.db")})
    return TestClient(create_app(cfg, engine or FakeEngine(), llm or FakeLlm(),
                                 token=token), raise_server_exceptions=False)


def test_an_ocr_crash_names_the_component_instead_of_something_went_wrong(tmp_path):
    """Spec §7 requires a clear error naming the missing component and the fix.
    A missing EasyOCR cache is her likeliest first-run failure."""
    engine = FakeEngine(raises=RuntimeError("model file korean_g2.pth not found"))
    r = _client(tmp_path, engine=engine).post(
        "/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "korean_g2.pth" in detail
    assert "./setup.sh" in detail


def test_a_failed_scan_leaves_no_orphaned_copy_of_her_document(tmp_path):
    engine = FakeEngine(raises=RuntimeError("boom"))
    c = _client(tmp_path, engine=engine)
    c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    uploads = tmp_path / "uploads"
    assert not uploads.exists() or list(uploads.iterdir()) == []


def test_a_pdf_is_refused_with_a_message_that_says_so(tmp_path):
    c = _client(tmp_path)
    r = c.post("/scan", data={"lens": "document"},
               files={"image": ("a.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")})
    assert r.status_code == 415
    assert "PDF" in r.json()["detail"]


def test_an_oversized_upload_is_refused_before_it_is_processed(tmp_path):
    big = ("a.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * (26 * 1024 * 1024)), "image/png")
    r = _client(tmp_path).post("/scan", files={"image": big}, data={"lens": "document"})
    assert r.status_code == 413


def test_a_model_timeout_names_the_smaller_model_she_can_switch_to(tmp_path):
    """Spec §1 assumes her laptop is weaker than the author's, so the 180s
    ceiling is the failure she is likeliest to meet."""
    from ilgeojwo.extract.extractor import ModelUnavailable
    llm = FakeLlm(raises=TimeoutError("timed out"))
    r = _client(tmp_path, llm=llm).post(
        "/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.status_code == 503
    assert "HyperCLOVAX" in r.json()["detail"]
    assert ModelUnavailable is not None


def test_without_a_token_every_route_is_open_as_before(tmp_path):
    c = _client(tmp_path)
    assert c.get("/").status_code == 200
    assert c.get("/scans").status_code == 200


def test_with_a_token_her_scans_are_not_readable_by_the_whole_subnet(tmp_path):
    """She serves on 0.0.0.0 so her phone can reach it. Korean share-houses put
    every unit on one subnet, and /scans returns the full OCR text of every
    document she has ever photographed."""
    c = _client(tmp_path, token="s3cret")
    assert c.get("/scans").status_code == 401
    assert c.get("/").status_code == 401
    assert c.post("/scan", files={"image": _png()},
                  data={"lens": "document"}).status_code == 401
    assert c.get("/scans?t=s3cret").status_code == 200
    assert c.get("/?t=s3cret").status_code == 200


def test_a_wrong_token_is_refused(tmp_path):
    assert _client(tmp_path, token="s3cret").get("/scans?t=nope").status_code == 401


def test_the_page_forwards_the_token_on_its_own_requests(tmp_path):
    page = _client(tmp_path, token="s3cret").get("/?t=s3cret").text
    assert "URLSearchParams" in page
