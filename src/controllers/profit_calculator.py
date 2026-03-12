"""
Amazon fee & profit calculation engine.

Implements the core business logic for estimating net profit per unit
and per transaction, factoring in:
    1. COGS (Cost of Goods Sold / Buy Price)
    2. Amazon Referral Fee  – category-dependent percentage of the sale price.
       • Beauty & Personal Care: 15 %
       • Electronics: 8 %
       • (Loaded dynamically from the Category table)
    3. FBA Fulfillment Fee – flat per-unit fee charged by Amazon when using FBA.
    4. Shipping / Prep Cost – inbound shipping and prep per unit.

Formula:
    referral_fee  = sell_price × category.referral_fee_pct
    total_fees    = referral_fee + fba_fee + shipping_cost
    net_profit    = (sell_price − COGS − total_fees) × quantity
    ROI (%)       = (net_profit / (COGS × quantity)) × 100
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProfitBreakdown:
    """Result of a profit calculation with full fee breakdown."""

    sell_price: float
    cogs: float
    referral_fee: float
    fba_fee: float
    shipping_cost: float
    quantity: int
    total_fees: float
    net_profit: float
    roi_pct: float
    margin_pct: float


def calculate_profit(
    sell_price: float,
    cogs: float,
    referral_fee_pct: float,
    fba_fee: float = 0.0,
    shipping_cost: float = 0.0,
    quantity: int = 1,
) -> ProfitBreakdown:
    """
    Calculate net profit and ROI for an Amazon sale.

    Args:
        sell_price: Listing price per unit on Amazon.
        cogs: Cost of goods per unit (buy price).
        referral_fee_pct: Category referral fee as a decimal (0.15 = 15%).
        fba_fee: FBA fulfillment fee per unit (0 if FBM).
        shipping_cost: Inbound shipping / prep cost per unit.
        quantity: Number of units in this transaction.

    Returns:
        ProfitBreakdown with every fee component and final metrics.
    """
    referral_fee: float = sell_price * referral_fee_pct
    total_fees: float = referral_fee + fba_fee + shipping_cost
    profit_per_unit: float = sell_price - cogs - total_fees
    net_profit: float = profit_per_unit * quantity

    total_cost = cogs * quantity
    roi_pct: float = (net_profit / total_cost * 100) if total_cost > 0 else 0.0

    revenue = sell_price * quantity
    margin_pct: float = (net_profit / revenue * 100) if revenue > 0 else 0.0

    return ProfitBreakdown(
        sell_price=sell_price,
        cogs=cogs,
        referral_fee=round(referral_fee, 2),
        fba_fee=fba_fee,
        shipping_cost=shipping_cost,
        quantity=quantity,
        total_fees=round(total_fees, 2),
        net_profit=round(net_profit, 2),
        roi_pct=round(roi_pct, 2),
        margin_pct=round(margin_pct, 2),
    )
