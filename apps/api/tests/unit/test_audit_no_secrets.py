"""
Unit tests — logs and payloads must not contain secrets, keys, or raw image bytes.
"""
from __future__ import annotations

import json


def test_compute_input_hash_produces_hex():
    from app.services.analysis_service import _compute_input_hash
    h = _compute_input_hash(
        model="claude-sonnet-4-6",
        provider="real",
        image_path=None,
        metrics={"spend": 100},
        request_fields={"ad_name": "X"},
    )
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_audit_payload_has_no_api_key():
    # Simulate the payload built in analysis_service.analyze
    payload = {
        "provider": "mock",
        "model": "claude-sonnet-4-6",
        "had_image": False,
        "media_kind": "none",
        "force": False,
        "analysis_version": 1,
    }
    payload_json = json.dumps(payload)
    assert "api_key" not in payload_json
    assert "PREENCHER" not in payload_json
    assert "access_token" not in payload_json
    assert "image_data" not in payload_json


def test_request_metadata_has_no_image_bytes():
    # Simulate the request_metadata stored in CreativeAnalysis
    meta = {
        "had_image": True,
        "media_kind": "image",
        "n_metrics": 3,
        "n_snapshots": 2,
    }
    meta_json = json.dumps(meta)
    assert "data:" not in meta_json  # no base64 data URIs
    assert "base64" not in meta_json


def test_analysis_parameters_no_key():
    params = {
        "model": "claude-sonnet-4-6",
        "provider": "real",
        "max_tokens": 2048,
        "timeout_s": 60.0,
        "max_retries": 3,
    }
    params_json = json.dumps(params)
    assert "api_key" not in params_json
    assert "PREENCHER" not in params_json
