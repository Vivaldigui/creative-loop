"""
Serialization helpers: convert MetaPublishPayload DTOs into the exact
dict format the Meta Graph API expects for each endpoint.

These functions are used by the DryRunPublisher to build the payload
that *would* be sent, and for display in the frontend payload viewer.
"""
from __future__ import annotations

from typing import Any

from .dtos import (
    AdCreativePayload,
    AdPayload,
    AdSetPayload,
    CampaignPayload,
    ImageUploadPayload,
    MetaPublishPayload,
)


def serialize_campaign(p: CampaignPayload, account_id: str) -> dict[str, Any]:
    """Returns the body for POST /{account_id}/campaigns."""
    return {
        "_endpoint": f"/{account_id}/campaigns",
        "_method": "POST",
        "name": p.name,
        "objective": p.objective,
        "status": p.status,   # always PAUSED
        "special_ad_categories": p.special_ad_categories,
        "buying_type": p.buying_type,
    }


def serialize_adset(p: AdSetPayload, account_id: str) -> dict[str, Any]:
    """Returns the body for POST /{account_id}/adsets."""
    payload: dict[str, Any] = {
        "_endpoint": f"/{account_id}/adsets",
        "_method": "POST",
        "name": p.name,
        "campaign_id": p.campaign_id,
        "daily_budget": p.daily_budget,
        "billing_event": p.billing_event,
        "optimization_goal": p.optimization_goal,
        "bid_strategy": p.bid_strategy,
        "status": p.status,  # always PAUSED
        "targeting": {
            "geo_locations": {
                "countries": p.targeting.geo_locations.countries,
                "cities": p.targeting.geo_locations.cities,
                "regions": p.targeting.geo_locations.regions,
            },
            "age_min": p.targeting.age_min,
            "age_max": p.targeting.age_max,
        },
    }
    if p.targeting.genders:
        payload["targeting"]["genders"] = p.targeting.genders
    if p.targeting.flexible_spec:
        payload["targeting"]["flexible_spec"] = p.targeting.flexible_spec
    if p.promoted_object:
        payload["promoted_object"] = {
            k: v for k, v in {
                "pixel_id": p.promoted_object.pixel_id,
                "custom_event_type": p.promoted_object.custom_event_type,
            }.items() if v is not None
        }
    if p.start_time:
        payload["start_time"] = p.start_time
    return payload


def serialize_image_upload(p: ImageUploadPayload, account_id: str) -> dict[str, Any]:
    """Returns the body for POST /{account_id}/adimages (multipart, represented as dict)."""
    return {
        "_endpoint": f"/{account_id}/adimages",
        "_method": "POST (multipart)",
        "_note": "DRY_RUN: file not uploaded. image_hash is a placeholder.",
        "filename": p.filename,
        "bytes_len": p.bytes_len,
        "source_storage_key": p.source_storage_key,
        "sha256_hash": p.image_hash,
        "expected_response_image_hash": p.placeholder_image_hash,
    }


def serialize_ad_creative(p: AdCreativePayload, account_id: str) -> dict[str, Any]:
    """Returns the body for POST /{account_id}/adcreatives."""
    spec = p.object_story_spec
    link_data: dict[str, Any] = {
        "image_hash": spec.link_data.image_hash,
        "link": spec.link_data.link,
    }
    if spec.link_data.message:
        link_data["message"] = spec.link_data.message
    if spec.link_data.name:
        link_data["name"] = spec.link_data.name
    if spec.link_data.description:
        link_data["description"] = spec.link_data.description
    if spec.link_data.call_to_action:
        cta: dict[str, Any] = {"type": spec.link_data.call_to_action.type}
        if spec.link_data.call_to_action.value:
            cta["value"] = {"link": spec.link_data.call_to_action.value.link}
        link_data["call_to_action"] = cta

    story_spec: dict[str, Any] = {
        "page_id": spec.page_id,
        "link_data": link_data,
    }
    if spec.instagram_actor_id:
        story_spec["instagram_actor_id"] = spec.instagram_actor_id

    result: dict[str, Any] = {
        "_endpoint": f"/{account_id}/adcreatives",
        "_method": "POST",
        "name": p.name,
        "object_story_spec": story_spec,
    }
    if p.degrees_of_freedom_spec:
        result["degrees_of_freedom_spec"] = p.degrees_of_freedom_spec
    return result


def serialize_ad(p: AdPayload, account_id: str) -> dict[str, Any]:
    """Returns the body for POST /{account_id}/ads."""
    result: dict[str, Any] = {
        "_endpoint": f"/{account_id}/ads",
        "_method": "POST",
        "name": p.name,
        "adset_id": p.adset_id,
        "creative": p.creative,
        "status": p.status,  # always PAUSED
    }
    if p.tracking_specs:
        result["tracking_specs"] = p.tracking_specs
    return result


def serialize_full_payload(root: MetaPublishPayload) -> dict[str, Any]:
    """
    Returns the complete structured payload dict with all five serialised steps.
    This is what is stored in PublicationAttempt.payload and shown in the UI.
    """
    account_id = root.ad_account_id
    return {
        "graph_api_version": root.graph_api_version,
        "ad_account_id": account_id,
        "page_id": root.page_id,
        "instagram_actor_id": root.instagram_actor_id,
        "pixel_id": root.pixel_id,
        "optimization_event": root.optimization_event,
        "placements": root.placements,
        "url": root.url,
        "tracking_params": root.tracking_params,
        "steps": {
            "1_campaign": serialize_campaign(root.campaign, account_id),
            "2_adset": serialize_adset(root.adset, account_id),
            "3_image_upload": serialize_image_upload(root.image_upload, account_id),
            "4_ad_creative": serialize_ad_creative(root.ad_creative, account_id),
            "5_ad": serialize_ad(root.ad, account_id),
        },
    }
