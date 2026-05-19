"""Billing models for subscription management."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class SubscriptionTier(enum.Enum):
    """Subscription tiers for AgentGuard."""
    
    COMMUNITY = "community"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(enum.Enum):
    """Subscription status from Lemon Squeezy."""
    
    ON_TRIAL = "on_trial"
    ACTIVE = "active"
    PAUSED = "paused"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Subscription:
    """User subscription record.
    
    Maps to Lemon Squeezy subscription data.
    """
    
    id: str  # Internal UUID
    user_id: str
    
    # Lemon Squeezy IDs
    lemon_subscription_id: Optional[str] = None
    lemon_customer_id: Optional[str] = None
    lemon_order_id: Optional[str] = None
    lemon_variant_id: Optional[str] = None
    
    # Subscription details
    tier: SubscriptionTier = SubscriptionTier.COMMUNITY
    status: SubscriptionStatus = SubscriptionStatus.CANCELLED
    
    # Billing cycle
    billing_anchor: Optional[int] = None  # Day of month (1-31)
    renews_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Feature flags (cached for performance)
    features: dict = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if subscription is active and valid."""
        return self.status in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.ON_TRIAL,
        )
    
    def is_paid(self) -> bool:
        """Check if user is on a paid plan."""
        return self.tier in (SubscriptionTier.TEAM, SubscriptionTier.ENTERPRISE) and self.is_active()
    
    def can_access_feature(self, feature: str) -> bool:
        """Check if user can access a specific feature."""
        tier_features = {
            SubscriptionTier.COMMUNITY: ["sdk", "cli", "mcp", "lsp", "basic_policies"],
            SubscriptionTier.TEAM: [
                "sdk", "cli", "mcp", "lsp",
                "api_proxy", "dashboard", "team_policies",
                "audit_export", "advanced_analytics"
            ],
            SubscriptionTier.ENTERPRISE: [
                "sdk", "cli", "mcp", "lsp",
                "api_proxy", "dashboard", "team_policies",
                "audit_export", "advanced_analytics",
                "sso", "sla", "priority_support", "custom_deployment"
            ],
        }
        allowed = tier_features.get(self.tier, [])
        return feature in allowed


@dataclass
class CheckoutSession:
    """Lemon Squeezy checkout session."""
    
    id: str
    url: str
    user_id: str
    variant_id: str
    status: str = "pending"  # pending, completed, expired
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


# Pricing configuration (matches Lemon Squeezy setup)
PRICING_CONFIG = {
    SubscriptionTier.COMMUNITY: {
        "name": "Community",
        "description": "Free for individual developers",
        "price_monthly": 0,
        "price_yearly": 0,
        "features": [
            "Python SDK + CLI",
            "MCP Server + LSP Server",
            "Basic policy templates",
            "Community support",
        ],
        "limits": {
            "validations_per_day": 1000,
            "team_members": 1,
            "audit_retention_days": 7,
        }
    },
    SubscriptionTier.TEAM: {
        "name": "Team",
        "description": "For small teams with shared policies",
        "price_monthly": 29,
        "price_yearly": 290,  # 2 months free
        "features": [
            "Everything in Community",
            "API Proxy + Dashboard",
            "Team policy management",
            "Audit log export",
            "Advanced analytics",
            "Email support",
        ],
        "limits": {
            "validations_per_day": 10000,
            "team_members": 10,
            "audit_retention_days": 90,
        }
    },
    SubscriptionTier.ENTERPRISE: {
        "name": "Enterprise",
        "description": "For organizations with compliance needs",
        "price_monthly": None,  # Contact sales
        "price_yearly": None,
        "features": [
            "Everything in Team",
            "SSO / SAML",
            "Custom deployment",
            "SLA guarantee",
            "Priority support",
            "Compliance reports",
        ],
        "limits": {
            "validations_per_day": -1,  # Unlimited
            "team_members": -1,  # Unlimited
            "audit_retention_days": -1,  # Unlimited
        }
    },
}


def get_pricing(tier: SubscriptionTier) -> dict:
    """Get pricing info for a tier."""
    return PRICING_CONFIG.get(tier, PRICING_CONFIG[SubscriptionTier.COMMUNITY])
