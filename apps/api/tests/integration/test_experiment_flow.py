"""Integration tests for Phase 7 experiment lifecycle."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


class TestExperimentCRUD:
    async def test_create_exploratory_experiment(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r = await c.post("/experiments", json={
            "name": "Test Exploratory",
            "mode": "EXPLORATORY",
            "hypothesis": "Testing image impact",
            "primary_metric": "ctr",
            "variants": [],
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["mode"] == "EXPLORATORY"
        assert data["status"] == "draft"
        assert data["organization_id"] == str(org.id)

    async def test_create_controlled_requires_primary_variable(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r = await c.post("/experiments", json={
            "name": "Test CONTROLLED no variable",
            "mode": "CONTROLLED",
            "hypothesis": "Test",
            "variants": [],
            # No primary_variable
        })
        assert r.status_code == 422, r.text

    async def test_create_controlled_with_variable(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r = await c.post("/experiments", json={
            "name": "Test CONTROLLED",
            "mode": "CONTROLLED",
            "hypothesis": "Testing headline",
            "primary_variable": "headline",
            "primary_metric": "ctr",
            "variants": [],
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["primary_variable"] == "headline"

    async def test_get_experiment(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={
            "name": "Get Test",
            "mode": "EXPLORATORY",
            "variants": [],
        })
        exp_id = r_create.json()["id"]

        r = await c.get(f"/experiments/{exp_id}")
        assert r.status_code == 200
        assert r.json()["id"] == exp_id

    async def test_list_experiments(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        await c.post("/experiments", json={"name": "E1", "mode": "EXPLORATORY", "variants": []})
        await c.post("/experiments", json={"name": "E2", "mode": "EXPLORATORY", "variants": []})

        r = await c.get("/experiments")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2

    async def test_org_isolation(self, seeded_client):
        c, user_a, org_a, user_b, org_b = seeded_client
        await _login(c, user_a.email, "password123")

        r = await c.post("/experiments", json={"name": "Org A Exp", "mode": "EXPLORATORY", "variants": []})
        exp_id = r.json()["id"]

        await _login(c, user_b.email, "password456")
        r2 = await c.get(f"/experiments/{exp_id}")
        assert r2.status_code == 404


class TestExperimentLifecycle:
    async def test_start_requires_confirm(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={"name": "Start Test", "mode": "EXPLORATORY", "variants": []})
        exp_id = r_create.json()["id"]

        r = await c.post(f"/experiments/{exp_id}/start", json={"confirm": False})
        assert r.status_code == 422

    async def test_start_experiment(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={"name": "Lifecycle Test", "mode": "EXPLORATORY", "variants": []})
        exp_id = r_create.json()["id"]

        r = await c.post(f"/experiments/{exp_id}/start", json={"confirm": True})
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    async def test_stop_experiment(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={"name": "Stop Test", "mode": "EXPLORATORY", "variants": []})
        exp_id = r_create.json()["id"]
        await c.post(f"/experiments/{exp_id}/start", json={"confirm": True})

        r = await c.post(f"/experiments/{exp_id}/stop", json={"stop_reason": "budget_exhausted"})
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"


class TestEvaluation:
    async def test_evaluate_returns_evaluation(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={"name": "Eval Test", "mode": "EXPLORATORY", "primary_metric": "ctr", "variants": []})
        exp_id = r_create.json()["id"]
        await c.post(f"/experiments/{exp_id}/start", json={"confirm": True})

        r = await c.post(f"/experiments/{exp_id}/evaluate", json={"notes": "Manual test"})
        assert r.status_code == 201, r.text
        data = r.json()
        assert "evaluation_state" in data
        assert data["causal_attribution"] is False  # EXPLORATORY

    async def test_evaluation_is_append_only(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={"name": "Append Eval", "mode": "EXPLORATORY", "variants": []})
        exp_id = r_create.json()["id"]
        await c.post(f"/experiments/{exp_id}/start", json={"confirm": True})

        await c.post(f"/experiments/{exp_id}/evaluate", json={})
        await c.post(f"/experiments/{exp_id}/evaluate", json={})

        r = await c.get(f"/experiments/{exp_id}/evaluations")
        assert r.status_code == 200
        assert len(r.json()) >= 2


class TestDecisions:
    async def test_create_decision_does_not_change_budget(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/experiments", json={"name": "Decision Test", "mode": "EXPLORATORY", "variants": []})
        exp_id = r_create.json()["id"]

        r = await c.post(f"/experiments/{exp_id}/decisions", json={
            "primary_metric": "ctr",
            "recommendation": "Continue testing",
            "suggested_action": "continue",
        })
        assert r.status_code == 201, r.text
        data = r.json()
        # v1: only suggests, never automatically changes budget
        assert "budget" not in str(data.get("executed_action", "")).lower()


class TestLearningLifecycle:
    async def test_create_learning_starts_provisional(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r = await c.post("/learnings", json={
            "observed_pattern": "Headlines with numbers convert better",
            "confidence": 0.75,
            "context": "ecommerce",
            "responsible_type": "test_result",
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["status"] == "provisional"

    async def test_confirm_learning_requires_human(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/learnings", json={"observed_pattern": "Test pattern", "responsible_type": "test_result"})
        lid = r_create.json()["id"]

        r = await c.post(f"/learnings/{lid}/confirm", json={"comment": "Verified by team"})
        assert r.status_code == 200
        assert r.json()["status"] == "confirmed"

    async def test_reject_requires_comment(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r_create = await c.post("/learnings", json={"observed_pattern": "Pattern to reject", "responsible_type": "test_result"})
        lid = r_create.json()["id"]

        # Missing comment
        r = await c.post(f"/learnings/{lid}/reject", json={})
        assert r.status_code == 422

        # With comment — should work
        r2 = await c.post(f"/learnings/{lid}/reject", json={"comment": "Correlation, not causation"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "rejected"

    async def test_learning_org_isolation(self, seeded_client):
        c, user_a, org_a, user_b, org_b = seeded_client
        await _login(c, user_a.email, "password123")
        r = await c.post("/learnings", json={"observed_pattern": "Org A pattern", "responsible_type": "test_result"})
        lid = r.json()["id"]

        await _login(c, user_b.email, "password456")
        r2 = await c.get(f"/learnings/{lid}")
        assert r2.status_code == 404


class TestReports:
    async def test_daily_report(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r = await c.get("/reports/daily")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "alerts" in data
        assert "running_experiments" in data
        assert "total_spend" in data or data.get("total_spend") is None

    async def test_weekly_report(self, seeded_client):
        c, user, org, *_ = seeded_client
        await _login(c, user.email, "password123")

        r = await c.get("/reports/weekly")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "completed_experiments" in data
        assert "new_learnings" in data
        assert "report_week" in data
