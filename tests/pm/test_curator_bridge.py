"""The Curator hand-off client: arithmetic, and how Curator's answers become errors a person can read."""

import io
import json
import urllib.error

import pytest

from gazzali import curator_bridge as cb


def test_the_estimate_is_per_image_plus_render_plus_a_margin() -> None:
    # 100 images x (1 MB DICOM + 0.2 MB PNG) x 1.25
    assert cb.estimated_bytes(100, renders=True, bytes_per_instance=1_000_000,
                              bytes_per_render=200_000) == 150_000_000
    assert cb.estimated_bytes(100, renders=False, bytes_per_instance=1_000_000,
                              bytes_per_render=200_000) == 125_000_000
    assert cb.estimated_bytes(3, renders=False, bytes_per_instance=1,
                              bytes_per_render=0) == 4   # rounded UP, never down


def test_the_2026_10_17_cohort_gets_a_reservation_that_holds_it() -> None:
    """28 DX images at the measured 12,161,784 bytes: the suggestion must exceed what the cohort
    really took (338,723,632 bytes of DICOM), unlike the 0.3 GiB a per-object rate produced."""
    estimate = cb.estimated_bytes(28, renders=False, bytes_per_instance=12_161_784, bytes_per_render=0)
    assert estimate is not None
    assert estimate > 338_723_632
    assert estimate > int(0.3 * (1 << 30))


def test_nothing_measured_means_no_estimate_rather_than_an_invented_one() -> None:
    assert cb.estimated_bytes(100, renders=True, bytes_per_instance=0, bytes_per_render=5) is None
    assert cb.estimated_bytes(0, renders=True, bytes_per_instance=1_000_000, bytes_per_render=5) is None


def test_rates_are_read_per_image_and_an_older_curator_answer_still_reads() -> None:
    assert cb.rates_from({"bytes_per_instance": 12, "bytes_per_render": 3, "bytes_per_object": 12}) == (12, 3)
    assert cb.rates_from({"bytes_per_instance": 0, "bytes_per_object": 0}) == (0, 0)
    # before per-image sizing: one object per image, two with renders — the render at object rate
    assert cb.rates_from({"bytes_per_object": 7}) == (7, 7)
    assert cb.rates_from({}) == (0, 0)


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setenv("CURATOR_HANDOFF_URL", "https://platform.example")
    monkeypatch.setenv("CURATOR_HANDOFF_TOKEN", "t")
    calls = []

    def answer_with(fn):
        monkeypatch.setattr(cb.urllib.request, "urlopen", fn)

    return calls, answer_with


def _http_error(code, detail):
    return urllib.error.HTTPError("https://platform.example/x", code, "x", {},
                                  io.BytesIO(json.dumps({"detail": detail}).encode()))


def test_a_firm_refusal_keeps_curators_words(wired) -> None:
    _calls, answer_with = wired

    def refuse(*_a, **_k):
        raise _http_error(409, "this selection was already requested (2026-10-17)")

    answer_with(refuse)
    with pytest.raises(cb.CuratorRefused) as err:
        cb.submit_selection("sel_" + "a" * 32, "a@x.com", "d" * 32)
    assert err.value.status == 409
    assert "already requested" in err.value.detail


@pytest.mark.parametrize("failure", ["5xx", "network"])
def test_a_server_failure_or_no_answer_is_unavailable(wired, failure) -> None:
    _calls, answer_with = wired

    def fail(*_a, **_k):
        if failure == "5xx":
            raise _http_error(503, "down")
        raise urllib.error.URLError("no route to host")

    answer_with(fail)
    with pytest.raises(cb.CuratorUnavailable):
        cb.list_selections("a@x.com")


def test_unconfigured_is_unavailable_and_never_calls_out(monkeypatch) -> None:
    monkeypatch.delenv("CURATOR_HANDOFF_URL", raising=False)
    monkeypatch.delenv("CURATOR_HANDOFF_TOKEN", raising=False)

    def boom(*_a, **_k):
        raise AssertionError("no call may be made without configuration")

    monkeypatch.setattr(cb.urllib.request, "urlopen", boom)
    assert cb.configured() is False
    with pytest.raises(cb.CuratorUnavailable):
        cb.list_selections("a@x.com")


def test_a_retract_never_raises_whatever_curator_does(wired) -> None:
    _calls, answer_with = wired

    def fail(*_a, **_k):
        raise urllib.error.URLError("down")

    answer_with(fail)
    assert cb.retract_selection("sel_" + "a" * 32, "a@x.com", "d" * 32) is False


def test_the_request_carries_the_token_and_only_the_owner_email(wired) -> None:
    calls, answer_with = wired

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def capture(req, timeout, context):
        calls.append(req)
        return Resp(json.dumps({"selections": []}).encode())

    answer_with(capture)
    cb.list_selections("Student2@medai.local")
    req = calls[0]
    assert req.get_header("Authorization") == "Bearer t"
    assert req.full_url == "https://platform.example/api/v1/handoff/selections?owner_email=Student2%40medai.local"
