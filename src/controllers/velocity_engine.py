"""
velocity_engine.py – Sales Velocity & Days-of-Supply calculator.

Provides:
    • Mock sales history for initial development.
    • calculate_daily_velocity()  – units/day over last 30 days.
    • calculate_days_of_supply()  – how many days current stock will last.
    • get_restock_status()        – status label based on days-of-supply.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.models import Product, Sale

# Lead time assumption (days to ship to FBA warehouse)
LEAD_TIME_DAYS = 14


# ──────────────────────────────────────────────────────────
# Mock sales history (temporary – for products without enough data)
# ──────────────────────────────────────────────────────────
# Maps SKU → simulated units sold in last 30 days
_MOCK_SALES_30D: Dict[str, int] = {
    "MITCH-GEL-225": 45,   # Mitchum  → 1.5 units/day
    "DOVE-SOAP-4PK": 60,   # Dove     → 2.0 units/day
}


def _get_actual_sales_30d(session: Session, product_id: int) -> int:
    """Query real sales from the last 30 days for a product."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    total = (
        session.query(func.coalesce(func.sum(Sale.quantity), 0))
        .filter(Sale.product_id == product_id, Sale.sale_date >= cutoff)
        .scalar()
    )
    return int(total)


def get_sales_last_30d(session: Session, product: Product) -> int:
    """
    Return units sold in the last 30 days.

    Uses mock data when available (for demo/dev); otherwise queries actual
    sale records from the database.
    """
    if product.sku in _MOCK_SALES_30D:
        return _MOCK_SALES_30D[product.sku]
    return _get_actual_sales_30d(session, product.id)


# ──────────────────────────────────────────────────────────
# Core calculations
# ──────────────────────────────────────────────────────────

def calculate_daily_velocity(sales_last_30_days: int) -> float:
    """Average units sold per day over a 30-day window."""
    return round(sales_last_30_days / 30, 2)


def calculate_days_of_supply(current_stock: int, daily_velocity: float) -> float:
    """
    How many days the current stock will last at the given velocity.

    Returns 999.0 when velocity is zero (no sales → infinite supply).
    """
    if daily_velocity <= 0:
        return 999.0
    return round(current_stock / daily_velocity, 1)


def get_restock_status(current_stock: int, days_of_supply: float) -> str:
    """
    Determine inventory status label.

    Rules:
        stock == 0              → "OUT OF STOCK"
        days_of_supply <= 14    → "REORDER SOON"
        days_of_supply > 14     → "✓ OK"
    """
    if current_stock == 0:
        return "OUT OF STOCK"
    if days_of_supply <= LEAD_TIME_DAYS:
        return "REORDER SOON"
    return "✓ OK"
