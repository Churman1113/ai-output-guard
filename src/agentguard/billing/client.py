"""Lemon Squeezy API client."""

from __future__ import annotations

import os
from typing import Optional, Dict, Any
import httpx


class LemonSqueezyClient:
    """Client for Lemon Squeezy API.
    
    Docs: https://docs.lemonsqueezy.com/api
    """
    
    BASE_URL = "https://api.lemonsqueezy.com/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize client with API key.
        
        Args:
            api_key: Lemon Squeezy API key. If not provided, reads from
                    LEMONSQUEEZY_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("LEMONSQUEEZY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Lemon Squeezy API key required. "
                "Set LEMONSQUEEZY_API_KEY environment variable."
            )
        
        self.headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {self.api_key}",
        }
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, headers=self.headers)
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make authenticated API request."""
        response = await self.client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()
    
    # Stores
    async def get_stores(self) -> Dict[str, Any]:
        """List all stores."""
        return await self._request("GET", "/stores")
    
    # Products
    async def get_products(self, store_id: Optional[str] = None) -> Dict[str, Any]:
        """List all products.
        
        Args:
            store_id: Filter by store ID.
        """
        params = {}
        if store_id:
            params["filter[store_id]"] = store_id
        return await self._request("GET", "/products", params=params)
    
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """Get a specific product."""
        return await self._request("GET", f"/products/{product_id}")
    
    # Variants (pricing tiers)
    async def get_variants(self, product_id: Optional[str] = None) -> Dict[str, Any]:
        """List all variants.
        
        Args:
            product_id: Filter by product ID.
        """
        params = {}
        if product_id:
            params["filter[product_id]"] = product_id
        return await self._request("GET", "/variants", params=params)
    
    async def get_variant(self, variant_id: str) -> Dict[str, Any]:
        """Get a specific variant."""
        return await self._request("GET", f"/variants/{variant_id}")
    
    # Checkouts
    async def create_checkout(
        self,
        store_id: str,
        variant_id: str,
        user_email: str,
        user_id: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a checkout session.
        
        Args:
            store_id: Lemon Squeezy store ID.
            variant_id: Product variant ID (pricing tier).
            user_email: Customer email.
            user_id: Internal user ID (stored in checkout data).
            success_url: Redirect URL after successful payment.
            cancel_url: Redirect URL after cancelled payment.
        
        Returns:
            Checkout object with URL for redirect.
        """
        data = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "product_options": {
                        "enabled_variants": [variant_id],
                        "redirect_url": success_url,
                        "receipt_link_url": success_url,
                        "receipt_button_text": "Return to Dashboard",
                    },
                    "checkout_options": {
                        "embed": False,
                        "media": True,
                        "logo": True,
                        "desc": True,
                        "discount": True,
                        "dark": False,
                        "subscription_preview": True,
                        "button_color": "#2DD4BF",  # teal-400
                    },
                    "checkout_data": {
                        "email": user_email,
                        "custom": {
                            "user_id": user_id,
                        },
                    },
                    "expires_at": None,
                    "preview": False,
                },
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": store_id,
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": variant_id,
                        }
                    },
                },
            }
        }
        
        return await self._request("POST", "/checkouts", json=data)
    
    async def get_checkout(self, checkout_id: str) -> Dict[str, Any]:
        """Get checkout details."""
        return await self._request("GET", f"/checkouts/{checkout_id}")
    
    # Customers
    async def get_customers(self, store_id: Optional[str] = None) -> Dict[str, Any]:
        """List all customers."""
        params = {}
        if store_id:
            params["filter[store_id]"] = store_id
        return await self._request("GET", "/customers", params=params)
    
    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Get a specific customer."""
        return await self._request("GET", f"/customers/{customer_id}")
    
    # Subscriptions
    async def get_subscriptions(
        self,
        store_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all subscriptions.
        
        Args:
            store_id: Filter by store ID.
            user_email: Filter by customer email.
        """
        params = {}
        if store_id:
            params["filter[store_id]"] = store_id
        if user_email:
            params["filter[user_email]"] = user_email
        return await self._request("GET", "/subscriptions", params=params)
    
    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get a specific subscription."""
        return await self._request("GET", f"/subscriptions/{subscription_id}")
    
    async def update_subscription(
        self,
        subscription_id: str,
        variant_id: Optional[str] = None,
        pause: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a subscription (upgrade/downgrade/pause).
        
        Args:
            subscription_id: Subscription ID.
            variant_id: New variant ID (for upgrade/downgrade).
            pause: True to pause, False to resume.
        """
        data = {"data": {"type": "subscriptions", "id": subscription_id}}
        attributes = {}
        
        if variant_id:
            attributes["variant_id"] = variant_id
        if pause is not None:
            attributes["pause"] = {"mode": "void" if pause else None}
        
        data["data"]["attributes"] = attributes
        return await self._request("PATCH", f"/subscriptions/{subscription_id}", json=data)
    
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription (at end of billing period)."""
        return await self._request("DELETE", f"/subscriptions/{subscription_id}")
    
    # Billing portal
    async def create_customer_portal(
        self,
        customer_id: str,
        return_url: str,
    ) -> Dict[str, Any]:
        """Create a customer portal session for managing billing.
        
        Args:
            customer_id: Lemon Squeezy customer ID.
            return_url: URL to return to after portal session.
        
        Returns:
            Portal URL for redirect.
        """
        data = {
            "data": {
                "type": "customer-portals",
                "attributes": {
                    "return_url": return_url,
                },
                "relationships": {
                    "customer": {
                        "data": {
                            "type": "customers",
                            "id": customer_id,
                        }
                    }
                },
            }
        }
        return await self._request("POST", "/customer-portals", json=data)
