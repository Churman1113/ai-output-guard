"""Tests for the billing module — models, webhooks, and API routes."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentguard.api import create_app
from agentguard.billing.models import (
    Subscription, SubscriptionTier, SubscriptionStatus,
    get_pricing, PRICING_CONFIG,
)
from agentguard.billing.webhooks import (
    verify_signature, parse_event, map_tier_from_variant, map_status,
    SubscriptionStore, subscription_store,
    handle_subscription_created, handle_subscription_updated,
    handle_subscription_cancelled,
    WebhookError, WebhookSignatureError,
)


# ── Test Models ──────────────────────────────────────────────

class TestSubscriptionTier:
    def test_enum_values(self):
        assert SubscriptionTier.COMMUNITY.value == "community"
        assert SubscriptionTier.TEAM.value == "team"
        assert SubscriptionTier.ENTERPRISE.value == "enterprise"


class TestSubscription:
    def test_default_tier_is_community(self):
        sub = Subscription(id="test", user_id="user_1")
        assert sub.tier == SubscriptionTier.COMMUNITY
        assert sub.status == SubscriptionStatus.CANCELLED

    def test_is_active(self):
        active = Subscription(id="1", user_id="u1", status=SubscriptionStatus.ACTIVE)
        assert active.is_active() is True

        trial = Subscription(id="2", user_id="u2", status=SubscriptionStatus.ON_TRIAL)
        assert trial.is_active() is True

        cancelled = Subscription(id="3", user_id="u3", status=SubscriptionStatus.CANCELLED)
        assert cancelled.is_active() is False

    def test_is_paid(self):
        community = Subscription(id="1", user_id="u1", tier=SubscriptionTier.COMMUNITY, status=SubscriptionStatus.ACTIVE)
        assert community.is_paid() is False

        team = Subscription(id="2", user_id="u2", tier=SubscriptionTier.TEAM, status=SubscriptionStatus.ACTIVE)
        assert team.is_paid() is True

        enterprise = Subscription(id="3", user_id="u3", tier=SubscriptionTier.ENTERPRISE, status=SubscriptionStatus.ACTIVE)
        assert enterprise.is_paid() is True

    def test_can_access_feature(self):
        sub = Subscription(id="1", user_id="u1", tier=SubscriptionTier.COMMUNITY, status=SubscriptionStatus.ACTIVE)
        assert sub.can_access_feature("sdk") is True
        assert sub.can_access_feature("dashboard") is False
        assert sub.can_access_feature("sso") is False

        team = Subscription(id="2", user_id="u2", tier=SubscriptionTier.TEAM, status=SubscriptionStatus.ACTIVE)
        assert team.can_access_feature("dashboard") is True
        assert team.can_access_feature("sso") is False

        ent = Subscription(id="3", user_id="u3", tier=SubscriptionTier.ENTERPRISE, status=SubscriptionStatus.ACTIVE)
        assert ent.can_access_feature("sso") is True
        assert ent.can_access_feature("sla") is True


class TestGetPricing:
    def test_community_pricing(self):
        pricing = get_pricing(SubscriptionTier.COMMUNITY)
        assert pricing["price_monthly"] == 0
        assert pricing["price_yearly"] == 0

    def test_team_pricing(self):
        pricing = get_pricing(SubscriptionTier.TEAM)
        assert pricing["price_monthly"] == 29
        assert pricing["price_yearly"] == 290

    def test_enterprise_pricing(self):
        pricing = get_pricing(SubscriptionTier.ENTERPRISE)
        assert pricing["price_monthly"] is None
        assert any("SSO" in f for f in pricing["features"])

    def test_invalid_tier_falls_back_to_community(self):
        pricing = get_pricing(None)
        assert pricing["price_monthly"] == 0


# ── Test Webhook Helpers ────────────────────────────────────

class TestWebhookHelpers:
    def test_map_tier_from_variant(self):
        assert map_tier_from_variant("variant_team_monthly") == SubscriptionTier.TEAM
        assert map_tier_from_variant("variant_team_yearly") == SubscriptionTier.TEAM
        assert map_tier_from_variant("variant_enterprise") == SubscriptionTier.ENTERPRISE
        assert map_tier_from_variant("unknown") == SubscriptionTier.COMMUNITY

    def test_map_status(self):
        assert map_status("active") == SubscriptionStatus.ACTIVE
        assert map_status("on_trial") == SubscriptionStatus.ON_TRIAL
        assert map_status("cancelled") == SubscriptionStatus.CANCELLED
        assert map_status("expired") == SubscriptionStatus.EXPIRED
        assert map_status("unknown") == SubscriptionStatus.CANCELLED

    def test_parse_event(self):
        payload = {
            "meta": {"event_name": "subscription_created"},
            "data": {"id": "123", "attributes": {}},
        }
        event_name, event_data = parse_event(payload)
        assert event_name == "subscription_created"
        assert event_data["id"] == "123"

    def test_parse_event_missing_name(self):
        payload = {"data": {}}
        event_name, event_data = parse_event(payload)
        assert event_name is None

    def test_verify_signature_missing_secret(self):
        with pytest.raises(WebhookError, match="not configured"):
            verify_signature(b"test", "sig", secret=None)


# ── Test Subscription Store ─────────────────────────────────

class TestSubscriptionStore:
    def setup_method(self):
        self.store = SubscriptionStore()

    def test_save_and_get_by_user(self):
        sub = Subscription(id="sub_1", user_id="user_1")
        self.store.save(sub)
        assert self.store.get_by_user("user_1") is sub
        assert self.store.get_by_user("nonexistent") is None

    def test_get_by_lemon_id(self):
        sub = Subscription(id="sub_1", user_id="user_1", lemon_subscription_id="ls_1")
        self.store.save(sub)
        assert self.store.get_by_lemon_id("ls_1") is sub
        assert self.store.get_by_lemon_id("nonexistent") is None

    def test_update_existing(self):
        sub = Subscription(id="sub_1", user_id="user_1", tier=SubscriptionTier.COMMUNITY)
        self.store.save(sub)
        sub.tier = SubscriptionTier.TEAM
        self.store.save(sub)
        assert self.store.get_by_user("user_1").tier == SubscriptionTier.TEAM


# ── Test Webhook Handlers ───────────────────────────────────

class TestWebhookHandlers:
    @pytest.fixture(autouse=True)
    def clear_store(self):
        subscription_store._subscriptions.clear()
        subscription_store._lemon_id_map.clear()

    @pytest.mark.asyncio
    async def test_handle_subscription_created(self):
        event_data = {
            "id": "ls_sub_1",
            "attributes": {
                "status": "active",
                "user_id": "user_1",
                "billing_anchor": 15,
            },
            "relationships": {
                "customer": {"data": {"id": "cust_1"}},
                "order": {"data": {"id": "order_1"}},
                "variant": {"data": {"id": "variant_team_monthly"}},
            },
        }
        await handle_subscription_created(event_data)
        sub = subscription_store.get_by_user("user_1")
        assert sub is not None
        assert sub.tier == SubscriptionTier.TEAM
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.lemon_subscription_id == "ls_sub_1"
        assert sub.lemon_customer_id == "cust_1"

    @pytest.mark.asyncio
    async def test_handle_subscription_created_no_user_id_raises(self):
        event_data = {"id": "ls_1", "attributes": {}, "relationships": {}}
        with pytest.raises(WebhookError, match="No user_id"):
            await handle_subscription_created(event_data)

    @pytest.mark.asyncio
    async def test_handle_subscription_updated(self):
        # First create
        sub = Subscription(id="sub_1", user_id="user_1", lemon_subscription_id="ls_1")
        subscription_store.save(sub)

        # Then update
        event_data = {
            "id": "ls_1",
            "attributes": {"status": "paused"},
            "relationships": {
                "variant": {"data": {"id": "variant_team_monthly"}},
            },
        }
        await handle_subscription_updated(event_data)
        updated = subscription_store.get_by_user("user_1")
        assert updated.status == SubscriptionStatus.PAUSED

    @pytest.mark.asyncio
    async def test_handle_subscription_cancelled(self):
        sub = Subscription(id="sub_1", user_id="user_1", lemon_subscription_id="ls_1")
        subscription_store.save(sub)

        event_data = {"id": "ls_1", "attributes": {}}
        await handle_subscription_cancelled(event_data)
        cancelled = subscription_store.get_by_user("user_1")
        assert cancelled.status == SubscriptionStatus.CANCELLED


# ── Test Billing API Routes ─────────────────────────────────

class TestBillingAPIRoutes:
    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app)

    def test_get_pricing(self, client):
        response = client.get("/api/v1/billing/pricing")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # 3 tiers
        tiers = {d["tier"] for d in data}
        assert "community" in tiers
        assert "team" in tiers
        assert "enterprise" in tiers

        # Check community pricing
        community = [d for d in data if d["tier"] == "community"][0]
        assert community["price_monthly"] == 0
        assert community["price_yearly"] == 0

    def test_get_subscription_default(self, client):
        response = client.get("/api/v1/billing/subscription")
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "community"
        assert data["is_active"] is True

    def test_github_sponsors(self, client):
        response = client.get("/api/v1/billing/github-sponsors")
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "tiers" in data

    def test_create_checkout_no_config(self, client):
        """Without LEMONSQUEEZY env vars, checkout should fail gracefully."""
        response = client.post("/api/v1/billing/checkout", json={
            "tier": "team",
            "billing_cycle": "monthly",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        })
        assert response.status_code == 500  # Billing not configured
        assert "Billing not configured" in response.text

    @patch("agentguard.billing.client.LemonSqueezyClient.create_checkout")
    @patch("agentguard.api.billing_routes.LEMONSQUEEZY_STORE_ID", "store_1")
    @patch("agentguard.api.billing_routes.LEMONSQUEEZY_TEAM_MONTHLY_VARIANT_ID", "var_team_monthly")
    @patch.dict("os.environ", {"LEMONSQUEEZY_API_KEY": "test_key"}, clear=False)
    def test_create_checkout_with_config(self, mock_create, client):
        """With env vars set, checkout should call Lemon Squeezy."""
        mock_create.return_value = {
            "data": {"id": "ch_1", "attributes": {"url": "https://lemonsqueezy.com/checkout"}}
        }
        response = client.post("/api/v1/billing/checkout", json={
            "tier": "team",
            "billing_cycle": "monthly",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        })
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert data["checkout_url"] == "https://lemonsqueezy.com/checkout"
