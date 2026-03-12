"""
Inventory controller — CRUD operations and aggregation queries for Products & Sales.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.controllers.profit_calculator import ProfitBreakdown, calculate_profit
from src.models.models import Category, Product, Sale


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------

def get_or_create_category(
    session: Session,
    name: str,
    referral_fee_pct: float = 0.15,
    description: Optional[str] = None,
) -> Category:
    """Return existing category by name or create a new one."""
    cat = session.query(Category).filter_by(name=name).first()
    if cat is None:
        cat = Category(
            name=name,
            referral_fee_pct=referral_fee_pct,
            description=description,
        )
        session.add(cat)
        session.commit()
    return cat


def list_categories(session: Session) -> List[Category]:
    return session.query(Category).order_by(Category.name).all()


# ---------------------------------------------------------------------------
# Product helpers
# ---------------------------------------------------------------------------

def add_product(session: Session, product: Product) -> Product:
    session.add(product)
    session.commit()
    return product


def add_product_from_dict(session: Session, data: dict) -> Product:
    """Create a Product from form data dict and persist it."""
    cat = get_or_create_category(session, data["category"])
    product = Product(
        sku=data["sku"],
        asin=data["asin"],
        name=data["name"],
        category_id=cat.id,
        buy_price=float(data["buy_price"]),
        sell_price=float(data["sell_price"]),
        weight_oz=float(data["weight_oz"]),
        length_in=float(data["length_in"]),
        width_in=float(data["width_in"]),
        height_in=float(data["height_in"]),
        stock=int(data["stock"]),
        bundle_qty=int(data.get("bundle_qty", 1)),
        fulfillment_type=data["fulfillment_type"],
    )
    session.add(product)
    session.commit()
    return product


def get_all_products(session: Session) -> List[Product]:
    return session.query(Product).order_by(Product.name).all()


def get_product_by_sku(session: Session, sku: str) -> Optional[Product]:
    return session.query(Product).filter_by(sku=sku).first()


def update_stock(session: Session, product_id: int, new_stock: int) -> None:
    product = session.query(Product).get(product_id)
    if product:
        product.stock = new_stock
        product.updated_at = datetime.utcnow()
        session.commit()


def receive_stock(session: Session, product_id: int, quantity_added: int) -> None:
    """Add *quantity_added* units to the product's existing stock."""
    product = session.query(Product).get(product_id)
    if product and quantity_added > 0:
        product.stock += quantity_added
        product.updated_at = datetime.utcnow()
        session.commit()


def delete_product(session: Session, product_id: int) -> None:
    """Delete a product and all its associated sales records."""
    session.query(Sale).filter_by(product_id=product_id).delete()
    product = session.query(Product).get(product_id)
    if product:
        session.delete(product)
    session.commit()


def get_low_stock_products(session: Session) -> List[Product]:
    """Return products where stock <= reorder_point."""
    return (
        session.query(Product)
        .filter(Product.stock <= Product.reorder_point)
        .order_by(Product.stock)
        .all()
    )


# ---------------------------------------------------------------------------
# Sale helpers
# ---------------------------------------------------------------------------

def record_sale(
    session: Session,
    product: Product,
    quantity: int = 1,
    sale_date: Optional[datetime] = None,
) -> Sale:
    """
    Record a sale, compute fees, store the net profit, and deduct stock.

    Uses the product's category referral_fee_pct for the fee calculation.
    """
    breakdown: ProfitBreakdown = calculate_profit(
        sell_price=product.sell_price,
        cogs=product.buy_price,
        referral_fee_pct=product.category.referral_fee_pct,
        fba_fee=product.fba_fee,
        shipping_cost=product.shipping_cost,
        quantity=quantity,
    )

    sale = Sale(
        product_id=product.id,
        sale_date=sale_date or datetime.utcnow(),
        quantity=quantity,
        sell_price_each=product.sell_price,
        cogs_each=product.buy_price,
        referral_fee=breakdown.referral_fee * quantity,
        fba_fee=breakdown.fba_fee * quantity,
        shipping_cost=breakdown.shipping_cost * quantity,
        net_profit=breakdown.net_profit,
    )
    session.add(sale)

    # Deduct stock
    product.stock = max(0, product.stock - quantity)
    product.updated_at = datetime.utcnow()

    session.commit()
    return sale


def get_sales_for_product(session: Session, product_id: int) -> List[Sale]:
    return (
        session.query(Sale)
        .filter_by(product_id=product_id)
        .order_by(Sale.sale_date.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Dashboard KPI aggregations
# ---------------------------------------------------------------------------

def get_dashboard_kpis(session: Session) -> dict:
    """
    Aggregate KPIs for the dashboard.

    Returns dict with:
        total_revenue, total_profit, total_units_sold,
        avg_roi, inventory_value, product_count, low_stock_count
    """
    # Sales aggregates
    sales_agg = (
        session.query(
            func.coalesce(func.sum(Sale.sell_price_each * Sale.quantity), 0).label("revenue"),
            func.coalesce(func.sum(Sale.net_profit), 0).label("profit"),
            func.coalesce(func.sum(Sale.quantity), 0).label("units"),
        )
        .one()
    )

    total_revenue: float = float(sales_agg.revenue)
    total_profit: float = float(sales_agg.profit)
    total_units: int = int(sales_agg.units)

    # Total COGS for ROI
    total_cogs = (
        session.query(
            func.coalesce(func.sum(Sale.cogs_each * Sale.quantity), 0)
        ).scalar()
    )
    total_cogs = float(total_cogs)
    avg_roi: float = (total_profit / total_cogs * 100) if total_cogs > 0 else 0.0

    # Inventory value = Σ (stock × sell_price)
    inv_value = (
        session.query(
            func.coalesce(func.sum(Product.stock * Product.sell_price), 0)
        ).scalar()
    )

    product_count: int = session.query(func.count(Product.id)).scalar() or 0
    low_stock_count: int = (
        session.query(func.count(Product.id))
        .filter(Product.stock <= Product.reorder_point)
        .scalar()
        or 0
    )

    return {
        "total_revenue": round(total_revenue, 2),
        "total_profit": round(total_profit, 2),
        "total_units_sold": total_units,
        "avg_roi": round(avg_roi, 2),
        "inventory_value": round(float(inv_value), 2),
        "product_count": product_count,
        "low_stock_count": low_stock_count,
    }
