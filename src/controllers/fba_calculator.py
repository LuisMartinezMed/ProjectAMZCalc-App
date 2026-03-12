"""
fba_calculator.py – Pure financial calculation engine for Amazon FBA/FBM.

Zero dependencies on GUI or database layers.  All monetary arithmetic uses
``decimal.Decimal`` to avoid floating-point rounding errors.

Amazon Fee Components Modeled
─────────────────────────────
1. **Referral Fee** – percentage of sale price, category-dependent.
   • Beauty & Personal Care:  8 % if sell_price ≤ $10.00, else 15 %.
   • Minimum referral fee per item: $0.30.
2. **FBA Fulfillment Fee** – per-unit fee based on size tier & weight.
   Uses Amazon 2024/2025 standard size tiers (Small Standard, Large Standard).
3. **Monthly Storage Fee** – per-cubic-foot charge.
   $0.78 / cu ft  (Jan – Sep)  |  $2.40 / cu ft  (Oct – Dec, Q4).

NOT included (by design): PPC / Advertising costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict

# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────
_TWO = Decimal("0.01")          # quantize helper → 2 decimal places
_FOUR = Decimal("0.0001")       # intermediate precision


def _d(value: float | int | str) -> Decimal:
    """Shorthand: convert any numeric to Decimal."""
    return Decimal(str(value))


# ──────────────────────────────────────────────────────────
# Referral-fee schedule (category → rule)
# Each entry is (low_rate, high_rate, threshold).
# If sell_price ≤ threshold → low_rate, else → high_rate.
# Categories without a split use the same rate for both.
# ──────────────────────────────────────────────────────────
_REFERRAL_FEE_RULES: Dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "Beauty & Personal Care": (_d("0.08"), _d("0.15"), _d("10.00")),
    "Electronics":            (_d("0.08"), _d("0.08"), _d("0.00")),
    "Home & Kitchen":         (_d("0.15"), _d("0.15"), _d("0.00")),
    "Health & Household":     (_d("0.08"), _d("0.15"), _d("10.00")),
}
_DEFAULT_REFERRAL_RULE = (_d("0.15"), _d("0.15"), _d("0.00"))

_MIN_REFERRAL_FEE = _d("0.30")

# ──────────────────────────────────────────────────────────
# FBA Size-Tier table  (Amazon 2024/2025 rates)
#
# Size tier determination (simplified):
#   Small Standard-Size:
#       weight ≤ 16 oz  AND  max(L,W,H) ≤ 15"  AND  min(L,W,H) ≤ 0.75"
#       — OR median dim ≤ 12"
#   Large Standard-Size:
#       weight ≤ 320 oz (20 lb)  AND  max(L,W,H) ≤ 18"  AND  (L+W+H) ≤ 150"
#   Oversize: everything else (not modeled here).
#
# Fee structure (weight-bracket based, simplified to base tiers):
# ──────────────────────────────────────────────────────────
_FBA_TIERS: list[dict] = [
    # Small Standard  (≤ 6 oz)
    {"tier": "Small Standard", "max_weight_oz": _d("6"),  "base_fee": _d("3.22")},
    # Small Standard  (6+ to 16 oz)
    {"tier": "Small Standard", "max_weight_oz": _d("16"), "base_fee": _d("3.40")},
    # Large Standard  (≤ 6 oz)
    {"tier": "Large Standard", "max_weight_oz": _d("6"),  "base_fee": _d("3.86")},
    # Large Standard  (6+ to 16 oz)
    {"tier": "Large Standard", "max_weight_oz": _d("16"), "base_fee": _d("4.08")},
    # Large Standard  (1 to 1.5 lb)
    {"tier": "Large Standard", "max_weight_oz": _d("24"), "base_fee": _d("5.32")},
    # Large Standard  (1.5 to 3 lb)
    {"tier": "Large Standard", "max_weight_oz": _d("48"), "base_fee": _d("6.19")},
    # Large Standard  (3+ to 20 lb) — base + per-lb surcharge above 3 lb
    {"tier": "Large Standard", "max_weight_oz": _d("320"), "base_fee": _d("6.75"),
     "per_lb_above": _d("0.16"), "above_oz": _d("48")},
]

# ──────────────────────────────────────────────────────────
# Storage fees  (per cubic foot / month)
# ──────────────────────────────────────────────────────────
_STORAGE_RATE_STANDARD = _d("0.78")   # Jan – Sep
_STORAGE_RATE_Q4       = _d("2.40")   # Oct – Dec


# ──────────────────────────────────────────────────────────
# ProductSpecs
# ──────────────────────────────────────────────────────────
@dataclass
class ProductSpecs:
    """
    Physical and cost attributes of a single sellable unit.

    All monetary values are expressed in USD.
    Dimensions are in inches; weight in ounces.
    """

    unit_cost_supplier: Decimal
    category: str
    weight_oz: Decimal
    length_in: Decimal
    width_in: Decimal
    height_in: Decimal
    bundle_qty: int = 1
    inbound_shipping_per_unit: Decimal = field(default_factory=lambda: _d("0.00"))

    def __post_init__(self) -> None:
        # Ensure all numerics are Decimal for consistent arithmetic.
        self.unit_cost_supplier = _d(self.unit_cost_supplier)
        self.weight_oz = _d(self.weight_oz)
        self.length_in = _d(self.length_in)
        self.width_in = _d(self.width_in)
        self.height_in = _d(self.height_in)
        self.inbound_shipping_per_unit = _d(self.inbound_shipping_per_unit)


# ──────────────────────────────────────────────────────────
# Rule Engine
# ──────────────────────────────────────────────────────────
class _FeeEngine:
    """Internal rule engine – stateless helper methods."""

    @staticmethod
    def referral_fee(sell_price: Decimal, category: str) -> Decimal:
        """
        Amazon Referral Fee.

        Beauty & Personal Care specifics:
            • sell_price ≤ $10.00  →  8 %
            • sell_price >  $10.00 →  15 %
        Minimum referral fee is always $0.30 per item.
        """
        low_rate, high_rate, threshold = _REFERRAL_FEE_RULES.get(
            category, _DEFAULT_REFERRAL_RULE
        )

        rate = low_rate if (threshold > 0 and sell_price <= threshold) else high_rate
        computed = (sell_price * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        return max(computed, _MIN_REFERRAL_FEE)

    @staticmethod
    def _determine_size_tier(
        weight_oz: Decimal,
        length_in: Decimal,
        width_in: Decimal,
        height_in: Decimal,
    ) -> str:
        """
        Classify a product into Small Standard or Large Standard.

        Simplified 2024/2025 rules:
            Small Standard: weight ≤ 16 oz, longest side ≤ 15", shortest ≤ 0.75"
            Large Standard: weight ≤ 20 lb (320 oz), longest side ≤ 18"
        """
        dims = sorted([length_in, width_in, height_in])
        shortest, median, longest = dims[0], dims[1], dims[2]

        if (
            weight_oz <= _d("16")
            and longest <= _d("15")
            and median <= _d("12")
            and shortest <= _d("0.75")
        ):
            return "Small Standard"

        if weight_oz <= _d("320") and longest <= _d("18"):
            return "Large Standard"

        # Fallback – treat as Large Standard (oversize not modeled)
        return "Large Standard"

    @staticmethod
    def fba_fee(weight_oz: Decimal, length_in: Decimal, width_in: Decimal, height_in: Decimal) -> Decimal:
        """
        FBA Fulfillment Fee based on Amazon 2024/2025 size tiers.

        Determines the size tier, then walks the weight-bracket table to
        find the matching fee.  For Large Standard items above 3 lb the
        fee includes a per-lb surcharge for weight exceeding 48 oz.
        """
        tier = _FeeEngine._determine_size_tier(weight_oz, length_in, width_in, height_in)

        matched_fee = _d("6.75")  # safe fallback

        for bracket in _FBA_TIERS:
            if bracket["tier"] != tier:
                continue
            if weight_oz <= bracket["max_weight_oz"]:
                matched_fee = bracket["base_fee"]
                # per-lb surcharge (Large Standard 3–20 lb bracket)
                if "per_lb_above" in bracket and weight_oz > bracket["above_oz"]:
                    extra_oz = weight_oz - bracket["above_oz"]
                    extra_lb = (extra_oz / _d("16")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    matched_fee += bracket["per_lb_above"] * extra_lb
                break

        return matched_fee.quantize(_TWO, rounding=ROUND_HALF_UP)

    @staticmethod
    def storage_fee(
        length_in: Decimal,
        width_in: Decimal,
        height_in: Decimal,
        months: int = 1,
        is_q4: bool = False,
    ) -> Decimal:
        """
        Monthly inventory storage fee.

        volume_cuft = (L × W × H) / 1728
        rate        = $0.78 (Jan–Sep) or $2.40 (Oct–Dec / Q4)
        fee         = volume_cuft × rate × months
        """
        volume_cubic_in = length_in * width_in * height_in
        volume_cuft = volume_cubic_in / _d("1728")
        rate = _STORAGE_RATE_Q4 if is_q4 else _STORAGE_RATE_STANDARD
        fee = volume_cuft * rate * _d(months)
        return fee.quantize(_TWO, rounding=ROUND_HALF_UP)


# ──────────────────────────────────────────────────────────
# ProfitCalculator
# ──────────────────────────────────────────────────────────
class ProfitCalculator:
    """
    High-level profit analysis for a single Amazon FBA listing.

    Usage::

        specs = ProductSpecs(...)
        result = ProfitCalculator.analyze_profit(8.99, specs, months_in_storage=2)
    """

    @staticmethod
    def analyze_profit(
        sell_price: float | Decimal,
        product: ProductSpecs,
        months_in_storage: int = 1,
        is_q4: bool = False,
    ) -> dict:
        """
        Full profit breakdown for one unit sold at *sell_price*.

        Returns a dict with every fee component and final metrics,
        all values as ``Decimal`` rounded to 2 places.

        Keys returned:
            sell_price, total_revenue, total_cogs,
            referral_fee, fba_fee, storage_fee, total_amazon_fees,
            net_profit, roi_pct, margin_pct
        """
        sp = _d(sell_price)

        # Revenue (single unit)
        total_revenue = sp

        # COGS = supplier cost × bundle qty + inbound shipping
        total_cogs = (
            product.unit_cost_supplier * _d(product.bundle_qty)
            + product.inbound_shipping_per_unit
        ).quantize(_TWO, rounding=ROUND_HALF_UP)

        # Fees
        referral = _FeeEngine.referral_fee(sp, product.category)

        fba = _FeeEngine.fba_fee(
            product.weight_oz,
            product.length_in,
            product.width_in,
            product.height_in,
        )

        storage = _FeeEngine.storage_fee(
            product.length_in,
            product.width_in,
            product.height_in,
            months=months_in_storage,
            is_q4=is_q4,
        )

        total_amazon_fees = (referral + fba + storage).quantize(_TWO, rounding=ROUND_HALF_UP)

        net_profit = (total_revenue - total_cogs - total_amazon_fees).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )

        roi_pct = (
            (net_profit / total_cogs * _d("100")).quantize(_TWO, rounding=ROUND_HALF_UP)
            if total_cogs > 0
            else _d("0.00")
        )

        margin_pct = (
            (net_profit / total_revenue * _d("100")).quantize(_TWO, rounding=ROUND_HALF_UP)
            if total_revenue > 0
            else _d("0.00")
        )

        return {
            "sell_price": sp.quantize(_TWO),
            "total_revenue": total_revenue.quantize(_TWO),
            "total_cogs": total_cogs,
            "referral_fee": referral,
            "fba_fee": fba,
            "storage_fee": storage,
            "total_amazon_fees": total_amazon_fees,
            "net_profit": net_profit,
            "roi_pct": roi_pct,
            "margin_pct": margin_pct,
        }


# ──────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    mitchum = ProductSpecs(
        unit_cost_supplier="2.50",
        category="Beauty & Personal Care",
        weight_oz="3.5",
        length_in="5",
        width_in="3",
        height_in="1",
        bundle_qty=1,
        inbound_shipping_per_unit="0.55",
    )

    result = ProfitCalculator.analyze_profit(
        sell_price="8.99",
        product=mitchum,
        months_in_storage=1,
        is_q4=False,
    )

    print("=" * 56)
    print("  Mitchum Men Gel Antiperspirant Unscented 2.25 Oz")
    print("=" * 56)
    for key, val in result.items():
        label = key.replace("_", " ").title()
        if "pct" in key:
            print(f"  {label:<24}  {val:>8} %")
        else:
            print(f"  {label:<24} ${val:>8}")
    print("=" * 56)
