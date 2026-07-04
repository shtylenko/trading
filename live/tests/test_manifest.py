import pytest

from trading.live.manifest import (ReleasePinMismatch, capture_manifest,
                                   release_code_hash, verify_pinned)


def test_hash_deterministic(fake_release):
    assert release_code_hash(fake_release) == release_code_hash(fake_release)
    assert release_code_hash(fake_release).startswith("sha256:")


def test_capture_and_verify_roundtrip(fake_release):
    m = capture_manifest(fake_release, version="fake.v1")
    assert m.release_id == "fake"
    verify_pinned(fake_release, m)  # same code → no raise


def test_param_change_breaks_pin(fake_release):
    m = capture_manifest(fake_release)
    # mutate a behaviour-defining attribute → hash drifts → pin must fail
    object.__setattr__(fake_release, "top_n", 99) if False else setattr(fake_release, "top_n", 99)
    with pytest.raises(ReleasePinMismatch):
        verify_pinned(fake_release, m)


def test_release_id_mismatch(fake_release):
    m = capture_manifest(fake_release)
    setattr(fake_release, "release_id", "other")
    with pytest.raises(ReleasePinMismatch):
        verify_pinned(fake_release, m)


def test_manifest_json_roundtrip(fake_release):
    from trading.live.manifest import ReleaseManifest
    m = capture_manifest(fake_release, version="fake.v1")
    assert ReleaseManifest.from_json(m.to_json()) == m
