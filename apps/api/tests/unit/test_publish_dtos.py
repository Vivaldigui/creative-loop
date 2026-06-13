"""Unit tests for Phase 5 publish DTOs and serialization."""
from __future__ import annotations

import pytest
from packages.meta_client.publish.dtos import (
    AdPayload,
    AdSetPayload,
    CampaignPayload,
    Targeting,
)
from packages.meta_client.publish.placeholders import (
    PENDING_META_AD_ACCOUNT_ID,
    PENDING_META_PAGE_ID,
    is_placeholder,
    resolve,
)
from pydantic import ValidationError


class TestCampaignPayload:
    def test_status_always_paused(self):
        c = CampaignPayload(name="Test")
        assert c.status == "PAUSED"

    def test_status_cannot_be_overridden(self):
        """status field is frozen — override attempt is silently ignored by Pydantic v2."""
        c = CampaignPayload(name="Test", status="ACTIVE")
        # Pydantic frozen field: status stays PAUSED
        assert c.status == "PAUSED"

    def test_invalid_objective(self):
        with pytest.raises(ValidationError):
            CampaignPayload(name="x", objective="INVALID_GOAL")

    def test_valid_objectives(self):
        for obj in ["OUTCOME_TRAFFIC", "OUTCOME_SALES", "OUTCOME_LEADS"]:
            c = CampaignPayload(name="x", objective=obj)
            assert c.objective == obj


class TestAdSetPayload:
    def test_status_always_paused(self):
        a = AdSetPayload(name="x", campaign_id="c1", daily_budget=5000)
        assert a.status == "PAUSED"

    def test_budget_must_be_positive(self):
        with pytest.raises(ValidationError):
            AdSetPayload(name="x", campaign_id="c1", daily_budget=0)

    def test_targeting_age_range_valid(self):
        with pytest.raises(ValidationError):
            Targeting(age_min=40, age_max=30)


class TestAdPayload:
    def test_status_always_paused(self):
        a = AdPayload(name="x", adset_id="a1", creative={"creative_id": "c1"})
        assert a.status == "PAUSED"


class TestPlaceholders:
    def test_preencher_is_placeholder(self):
        assert is_placeholder("PREENCHER_META_PAGE_ID") is True

    def test_pending_is_placeholder(self):
        assert is_placeholder("PENDING_META_PAGE_ID") is True

    def test_real_value_not_placeholder(self):
        assert is_placeholder("123456789") is False

    def test_none_is_placeholder(self):
        assert is_placeholder(None) is True

    def test_resolve_placeholder_returns_fallback(self):
        result = resolve("PREENCHER_META_PAGE_ID", PENDING_META_PAGE_ID)
        assert result == PENDING_META_PAGE_ID

    def test_resolve_real_returns_value(self):
        result = resolve("12345678", PENDING_META_PAGE_ID)
        assert result == "12345678"


class TestSerializationStatusPaused:
    """Serialized payloads must always have status=PAUSED."""

    def test_campaign_status_paused_in_serialized(self):
        from packages.meta_client.publish.serialization import serialize_campaign
        c = CampaignPayload(name="Test")
        result = serialize_campaign(c, "act_123")
        assert result["status"] == "PAUSED"

    def test_adset_status_paused_in_serialized(self):
        from packages.meta_client.publish.serialization import serialize_adset
        a = AdSetPayload(name="x", campaign_id="c1", daily_budget=5000)
        result = serialize_adset(a, "act_123")
        assert result["status"] == "PAUSED"

    def test_ad_status_paused_in_serialized(self):
        from packages.meta_client.publish.serialization import serialize_ad
        a = AdPayload(name="x", adset_id="a1", creative={"creative_id": "c1"})
        result = serialize_ad(a, "act_123")
        assert result["status"] == "PAUSED"


class TestNoInventedIds:
    """Placeholders must be named constants, never invented IDs."""

    def test_ad_account_placeholder_name(self):
        assert PENDING_META_AD_ACCOUNT_ID == "PENDING_META_AD_ACCOUNT_ID"

    def test_page_placeholder_name(self):
        assert PENDING_META_PAGE_ID == "PENDING_META_PAGE_ID"
