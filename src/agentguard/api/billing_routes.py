"""Billing API routes for Lemon Squeezy integration."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel

from agentguard.billing import LemonSqueezyClient, Subscription, SubscriptionTier
from agentguard.billing.models import get_pricing, PRICING_CONFIG
from agentguard.billing.webhooks import handle_webhook, verify_signature, WebhookError


router = APIRouter(prefix="/billing", tags=["billing"])


# Configuration (from environment)
LEMONSQUEEZY_STORE_ID = os.environ.get("LEMONSQUEEZY_STORE_ID")
LEMONSQUEEZY_TEAM_MONTHLY_VARIANT_ID = os.environ.get("LEMONSQUEEZY_TEAM_MONTHLY_VARIANT_ID")
LEMONSQUEEZY_TEAM_YEARLY_VARIANT_ID = os.environ.get("LEMONSQUEEZY_TEAM_YEARLY_VARIANT_ID")


class PricingResponse(BaseModel):
    """Pricing information response."""
    tier: str
    name: str
    description: str
    price_monthly: Optional[int]
    price_yearly: Optional[int]
    features: list[str]
    limits: dict


class CheckoutRequest(BaseModel):
    """Create checkout session request."""
    tier: str  # "team" or "enterprise"
    billing_cycle: str = "monthly"  # "monthly" or "yearly"
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    """Checkout session response."""
    checkout_url: str
    checkout_id: str


class SubscriptionResponse(BaseModel):
    """User subscription response."""
    tier: str
    status: str
    is_active: bool
    is_paid: bool
    renews_at: Optional[str]
    ends_at: Optional[str]
    features: list[str]


class PortalResponse(BaseModel):
    """Customer portal response."""
    portal_url: str


# Dependency to get billing client
async def get_billing_client() -> LemonSqueezyClient:
    """Get Lemon Squeezy client."""
    try:
        client = LemonSqueezyClient()
        yield client
    finally:
        await client.close()


@router.get("/pricing", response_model=list[PricingResponse])
async def get_pricing_info() -> list[PricingResponse]:
    """Get all pricing tiers."""
    pricing = []
    for tier in SubscriptionTier:
        config = get_pricing(tier)
        pricing.append(PricingResponse(
            tier=tier.value,
            name=config["name"],
            description=config["description"],
            price_monthly=config["price_monthly"],
            price_yearly=config["price_yearly"],
            features=config["features"],
            limits=config["limits"],
        ))
    return pricing


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    client: LemonSqueezyClient = Depends(get_billing_client),
) -> CheckoutResponse:
    """Create a checkout session for subscription.
    
    Returns a URL to redirect the user to Lemon Squeezy checkout.
    """
    if not LEMONSQUEEZY_STORE_ID:
        raise HTTPException(500, "Billing not configured")
    
    # Map tier to variant ID
    variant_id = None
    if request.tier == "team":
        if request.billing_cycle == "yearly":
            variant_id = LEMONSQUEEZY_TEAM_YEARLY_VARIANT_ID
        else:
            variant_id = LEMONSQUEEZY_TEAM_MONTHLY_VARIANT_ID
    
    if not variant_id:
        raise HTTPException(400, f"Invalid tier or billing cycle: {request.tier}/{request.billing_cycle}")
    
    # TODO: Get user email from authenticated session
    user_email = "user@example.com"  # Replace with actual user email
    user_id = "user_123"  # Replace with actual user ID
    
    try:
        result = await client.create_checkout(
            store_id=LEMONSQUEEZY_STORE_ID,
            variant_id=variant_id,
            user_email=user_email,
            user_id=user_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        
        checkout_data = result.get("data", {})
        checkout_id = checkout_data.get("id")
        checkout_url = checkout_data.get("attributes", {}).get("url")
        
        return CheckoutResponse(
            checkout_url=checkout_url,
            checkout_id=checkout_id,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to create checkout: {e}")


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription() -> SubscriptionResponse:
    """Get current user's subscription."""
    # TODO: Get user ID from authenticated session
    user_id = "user_123"
    
    # TODO: Get from database
    # For now, return free tier
    return SubscriptionResponse(
        tier="community",
        status="active",
        is_active=True,
        is_paid=False,
        renews_at=None,
        ends_at=None,
        features=get_pricing(SubscriptionTier.COMMUNITY)["features"],
    )


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    client: LemonSqueezyClient = Depends(get_billing_client),
) -> PortalResponse:
    """Create a customer portal session for managing billing.
    
    Returns a URL to redirect the user to the customer portal.
    """
    # TODO: Get user's Lemon Squeezy customer ID from database
    customer_id = "cust_xxx"  # Replace with actual customer ID
    return_url = "https://agentguard.dev/dashboard/billing"
    
    try:
        result = await client.create_customer_portal(
            customer_id=customer_id,
            return_url=return_url,
        )
        portal_url = result.get("data", {}).get("attributes", {}).get("url")
        return PortalResponse(portal_url=portal_url)
    except Exception as e:
        raise HTTPException(500, f"Failed to create portal: {e}")


@router.post("/webhook")
async def webhook_handler(
    request: Request,
    x_signature: Optional[str] = Header(None),
):
    """Handle Lemon Squeezy webhooks.
    
    Webhook events:
    - subscription_created
    - subscription_updated
    - subscription_cancelled
    - subscription_resumed
    - subscription_expired
    - subscription_paused
    - subscription_unpaused
    - order_created
    - order_refunded
    """
    # Read raw body for signature verification
    body = await request.body()
    
    # Verify signature
    if x_signature:
        try:
            if not verify_signature(body, x_signature):
                raise HTTPException(401, "Invalid signature")
        except WebhookError:
            # Signature verification not configured, skip in development
            pass
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    # Handle event
    try:
        await handle_webhook(payload)
        return {"status": "ok"}
    except WebhookError as e:
        raise HTTPException(500, str(e))


@router.get("/github-sponsors")
async def get_github_sponsors_url() -> dict:
    """Get GitHub Sponsors URL for donations."""
    return {
        "url": "https://github.com/sponsors/Churman1113",  # Update with your username
        "tiers": [
            {"name": "☕ Coffee", "amount": "$5/month", "description": "Buy me a coffee"},
            {"name": "🚀 Supporter", "amount": "$25/month", "description": "Support development"},
            {"name": "💎 Sponsor", "amount": "$100/month", "description": "Logo on README + priority support"},
        ],
    }
