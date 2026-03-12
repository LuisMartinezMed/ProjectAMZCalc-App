"""
Seed script – Populates the database with initial categories, the Mitchum
product, and sample sales so the dashboard is not empty on first launch.

Run directly:  python -m src.seed
"""

import random
from datetime import datetime, timedelta

from src.controllers.inventory_controller import (
    get_or_create_category,
    record_sale,
)
from src.database import get_session, init_db
from src.models.models import Product


def seed() -> None:
    """Insert seed data if the database is empty."""
    init_db()
    session = get_session()

    try:
        # ── Categories (dynamic – add more here for future phases) ────
        beauty = get_or_create_category(
            session,
            name="Beauty & Personal Care",
            referral_fee_pct=0.15,
            description="Cosmetics, skincare, deodorants, fragrances, etc.",
        )
        get_or_create_category(
            session,
            name="Electronics",
            referral_fee_pct=0.08,
            description="Consumer electronics, accessories.",
        )
        get_or_create_category(
            session,
            name="Home & Kitchen",
            referral_fee_pct=0.15,
            description="Furniture, kitchenware, décor.",
        )
        get_or_create_category(
            session,
            name="Health & Household",
            referral_fee_pct=0.15,
            description="Vitamins, supplements, cleaning supplies.",
        )

        # ── Seed product: Mitchum Men Gel Antiperspirant ──────────────
        existing = session.query(Product).filter_by(sku="MITCH-GEL-225").first()
        if existing:
            print("Seed data already present – skipping.")
            return

        mitchum = Product(
            sku="MITCH-GEL-225",
            asin="B00V3L22TU",
            name="Mitchum Men Gel Antiperspirant Unscented 2.25 Oz",
            category_id=beauty.id,
            buy_price=2.50,        # Wholesale / COGS per unit
            sell_price=8.99,       # Amazon listing price
            weight_oz=2.25,
            length_in=5.5,
            width_in=2.5,
            height_in=1.5,
            fba_fee=3.22,          # Estimated FBA fulfillment fee
            shipping_cost=0.55,    # Inbound shipping per unit
            stock=48,
            reorder_point=10,
            fulfillment_type="FBA",
        )
        session.add(mitchum)
        session.commit()

        # Additional sample products
        dove = Product(
            sku="DOVE-SOAP-4PK",
            asin="B008O9GKXE",
            name="Dove Beauty Bar Sensitive Skin 4 oz (4-Pack)",
            category_id=beauty.id,
            buy_price=4.20,
            sell_price=12.49,
            weight_oz=16.0,
            length_in=6.0,
            width_in=4.0,
            height_in=3.0,
            fba_fee=3.86,
            shipping_cost=0.75,
            stock=10,
            reorder_point=8,
            fulfillment_type="FBA",
        )

        neutrogena = Product(
            sku="NEUT-WASH-6OZ",
            asin="B00HNSSV4W",
            name="Neutrogena Oil-Free Acne Wash 6 oz",
            category_id=beauty.id,
            buy_price=5.10,
            sell_price=11.97,
            weight_oz=6.5,
            length_in=7.0,
            width_in=2.5,
            height_in=1.5,
            fba_fee=3.45,
            shipping_cost=0.60,
            stock=3,           # low stock to trigger alert
            reorder_point=5,
            fulfillment_type="FBA",
        )

        session.add_all([dove, neutrogena])
        session.commit()

        # ── Sample sales (last 30 days) ──────────────────────────────
        products = [mitchum, dove, neutrogena]
        now = datetime.utcnow()
        for _ in range(25):
            product = random.choice(products)
            qty = random.randint(1, 4)
            days_ago = random.randint(0, 30)
            sale_date = now - timedelta(days=days_ago)
            record_sale(session, product, quantity=qty, sale_date=sale_date)

        print("✓ Seed data loaded successfully.")
        print(f"  • Categories: 4")
        print(f"  • Products: 3")
        print(f"  • Sample sales: 25")

    finally:
        session.close()


if __name__ == "__main__":
    seed()
