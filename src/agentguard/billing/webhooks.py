"""Lemon Squeezy webhook handlers.

Docs: https://docs.lemonsqueezy.com/guides/developer-guide/webhooks
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime
from typing import Dict, Any, Optional

from agentguard.billing.models import (
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)


class WebhookError(Exception):
    """Webhook processing error."""
    pass


class WebhookSignatureError(WebhookError):
    """Invalid webhook signature."""
    pass


def verify_signature(payload: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """Verify Lemon Squeezy webhook signature.
    
    Args:
        payload: Raw request body.
        signature: X-Signature header value.
        secret: Webhook signing secret. If not provided, reads from
                LEMONSQUEEZY_WEBHOOK_SECRET environment variable.
    
    Returns:
        True if signature is valid.
    """
    secret = secret or os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET")
    if not secret:
        raise WebhookError("Webhook secret not configured")
    
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def parse_event(payload: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """Parse webhook event from payload.
    
    Returns:
        Tuple of (event_name, event_data)
    """
    event_name = payload.get("meta", {}).get("event_name")
    event_data = payload.get("data", {})
    return event_name, event_data


class SubscriptionStore:
    """In-memory subscription store (replace with database in production)."""
    
    def __init__(self):
        self._subscriptions: Dict[str, Subscription] = {}
        self._lemon_id_map: Dict[str, str] = {}  # lemon_subscription_id -> internal_id
    
    def get_by_user(self, user_id: str) -> Optional[Subscription]:
        """Get subscription by user ID."""
        for sub in self._subscriptions.values():
            if sub.user_id == user_id:
                return sub
        return None
    
    def get_by_lemon_id(self, lemon_id: str) -> Optional[Subscription]:
        """Get subscription by Lemon Squeezy ID."""
        internal_id = self._lemon_id_map.get(lemon_id)
        if internal_id:
            return self._subscriptions.get(internal_id)
        return None
    
    def save(self, subscription: Subscription) -> None:
        """Save or update subscription."""
        self._subscriptions[subscription.id] = subscription
        if subscription.lemon_subscription_id:
            self._lemon_id_map[subscription.lemon_subscription_id] = subscription.id


# Global store instance (use dependency injection in production)
subscription_store = SubscriptionStore()


def map_tier_from_variant(variant_id: str) -> SubscriptionTier:
    """Map Lemon Squeezy variant ID to subscription tier.
    
    Configure these mappings based on your Lemon Squeezy setup.
    """
    # TODO: Configure with actual variant IDs from Lemon Squeezy
    variant_tier_map = {
        "variant_team_monthly": SubscriptionTier.TEAM,
        "variant_team_yearly": SubscriptionTier.TEAM,
        "variant_enterprise": SubscriptionTier.ENTERPRISE,
    }
    return variant_tier_map.get(variant_id, SubscriptionTier.COMMUNITY)


def map_status(lemon_status: str) -> SubscriptionStatus:
    """Map Lemon Squeezy status to internal status."""
    status_map = {
        "on_trial": SubscriptionStatus.ON_TRIAL,
        "active": SubscriptionStatus.ACTIVE,
        "paused": SubscriptionStatus.PAUSED,
        "past_due": SubscriptionStatus.PAST_DUE,
        "unpaid": SubscriptionStatus.UNPAID,
        "cancelled": SubscriptionStatus.CANCELLED,
        "expired": SubscriptionStatus.EXPIRED,
    }
    return status_map.get(lemon_status, SubscriptionStatus.CANCELLED)


async def handle_subscription_created(event_data: Dict[str, Any]) -> None:
    """Handle subscription_created event."""
    attrs = event_data.get("attributes", {})
    relationships = event_data.get("relationships", {})
    
    # Extract IDs
    lemon_subscription_id = event_data.get("id")
    lemon_customer_id = relationships.get("customer", {}).get("data", {}).get("id")
    lemon_order_id = relationships.get("order", {}).get("data", {}).get("id")
    lemon_variant_id = relationships.get("variant", {}).get("data", {}).get("id")
    
    # Get user ID from checkout data
    user_id = attrs.get("user_id") or attrs.get("checkout_data", {}).get("custom", {}).get("user_id")
    
    if not user_id:
        raise WebhookError("No user_id found in subscription data")
    
    # Check for existing subscription
    existing = subscription_store.get_by_user(user_id)
    
    subscription = Subscription(
        id=existing.id if existing else f"sub_{user_id}",
        user_id=user_id,
        lemon_subscription_id=lemon_subscription_id,
        lemon_customer_id=lemon_customer_id,
        lemon_order_id=lemon_order_id,
        lemon_variant_id=lemon_variant_id,
        tier=map_tier_from_variant(lemon_variant_id),
        status=map_status(attrs.get("status", "cancelled")),
        billing_anchor=attrs.get("billing_anchor"),
        renews_at=parse_datetime(attrs.get("renews_at")),
        ends_at=parse_datetime(attrs.get("ends_at")),
        trial_ends_at=parse_datetime(attrs.get("trial_ends_at")),
        updated_at=datetime.utcnow(),
    )
    
    subscription_store.save(subscription)
    print(f"[billing] Subscription created: {subscription.id} -> {subscription.tier.value}")


async def handle_subscription_updated(event_data: Dict[str, Any]) -> None:
    """Handle subscription_updated event."""
    lemon_id = event_data.get("id")
    existing = subscription_store.get_by_lemon_id(lemon_id)
    
    if not existing:
        # Treat as create if not exists
        await handle_subscription_created(event_data)
        return
    
    attrs = event_data.get("attributes", {})
    relationships = event_data.get("relationships", {})
    
    # Update fields
    existing.status = map_status(attrs.get("status", existing.status.value))
    existing.lemon_variant_id = relationships.get("variant", {}).get("data", {}).get("id") or existing.lemon_variant_id
    existing.tier = map_tier_from_variant(existing.lemon_variant_id)
    existing.billing_anchor = attrs.get("billing_anchor", existing.billing_anchor)
    existing.renews_at = parse_datetime(attrs.get("renews_at")) or existing.renews_at
    existing.ends_at = parse_datetime(attrs.get("ends_at")) or existing.ends_at
    existing.trial_ends_at = parse_datetime(attrs.get("trial_ends_at")) or existing.trial_ends_at
    existing.updated_at = datetime.utcnow()
    
    subscription_store.save(existing)
    print(f"[billing] Subscription updated: {existing.id} -> {existing.status.value}")


async def handle_subscription_cancelled(event_data: Dict[str, Any]) -> None:
    """Handle subscription_cancelled event."""
    lemon_id = event_data.get("id")
    existing = subscription_store.get_by_lemon_id(lemon_id)
    
    if existing:
        existing.status = SubscriptionStatus.CANCELLED
        existing.ends_at = parse_datetime(event_data.get("attributes", {}).get("ends_at"))
        existing.updated_at = datetime.utcnow()
        subscription_store.save(existing)
        print(f"[billing] Subscription cancelled: {existing.id}")


async def handle_subscription_resumed(event_data: Dict[str, Any]) -> None:
    """Handle subscription_resumed event."""
    await handle_subscription_updated(event_data)


async def handle_subscription_expired(event_data: Dict[str, Any]) -> None:
    """Handle subscription_expired event."""
    lemon_id = event_data.get("id")
    existing = subscription_store.get_by_lemon_id(lemon_id)
    
    if existing:
        existing.status = SubscriptionStatus.EXPIRED
        existing.updated_at = datetime.utcnow()
        subscription_store.save(existing)
        print(f"[billing] Subscription expired: {existing.id}")


async def handle_subscription_paused(event_data: Dict[str, Any]) -> None:
    """Handle subscription_paused event."""
    lemon_id = event_data.get("id")
    existing = subscription_store.get_by_lemon_id(lemon_id)
    
    if existing:
        existing.status = SubscriptionStatus.PAUSED
        existing.updated_at = datetime.utcnow()
        subscription_store.save(existing)
        print(f"[billing] Subscription paused: {existing.id}")


async def handle_subscription_unpaused(event_data: Dict[str, Any]) -> None:
    """Handle subscription_unpaused event."""
    await handle_subscription_updated(event_data)


async def handle_payment_success(event_data: Dict[str, Any]) -> None:
    """Handle order_created / payment_success event."""
    # Payment succeeded - subscription should already be created/updated
    # This is mainly for logging or additional processing
    print(f"[billing] Payment success: {event_data.get('id')}")


async def handle_payment_failed(event_data: Dict[str, Any]) -> None:
    """Handle payment_failed event."""
    # Payment failed - subscription status will be updated via subscription_updated
    print(f"[billing] Payment failed: {event_data.get('id')}")


# Event handler registry
EVENT_HANDLERS = {
    "subscription_created": handle_subscription_created,
    "subscription_updated": handle_subscription_updated,
    "subscription_cancelled": handle_subscription_cancelled,
    "subscription_resumed": handle_subscription_resumed,
    "subscription_expired": handle_subscription_expired,
    "subscription_paused": handle_subscription_paused,
    "subscription_unpaused": handle_subscription_unpaused,
    "order_created": handle_payment_success,
    "order_refunded": handle_payment_failed,
}


async def handle_webhook(payload: Dict[str, Any]) -> None:
    """Main webhook entry point.
    
    Args:
        payload: Parsed JSON webhook payload.
    
    Raises:
        WebhookError: If event handling fails.
    """
    event_name, event_data = parse_event(payload)
    
    handler = EVENT_HANDLERS.get(event_name)
    if not handler:
        print(f"[billing] Unhandled webhook event: {event_name}")
        return
    
    try:
        await handler(event_data)
    except Exception as e:
        raise WebhookError(f"Failed to handle {event_name}: {e}") from e


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        # Handle various ISO formats
        value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
