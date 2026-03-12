"""
SQLAlchemy ORM models for Amazon Inventory & Profit Master.

Defines the core data schema:
- Category: Dynamic product categories (Beauty, Electronics, etc.)
- Product: SKU/ASIN-based product catalog with cost/price/stock tracking.
- Sale: Per-transaction record with fee breakdown and net profit.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Category(Base):
    """
    Dynamic product category.

    Amazon charges different Referral Fee percentages per category.
    This table allows adding new categories at runtime without code changes.

    Attributes:
        referral_fee_pct: Amazon Referral Fee as a decimal (e.g. 0.15 = 15%).
    """

    __tablename__ = "categories"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(120), unique=True, nullable=False)
    referral_fee_pct: float = Column(Float, nullable=False, default=0.15)
    description: Optional[str] = Column(Text, nullable=True)

    products = relationship("Product", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category(name='{self.name}', fee={self.referral_fee_pct:.0%})>"


class Product(Base):
    """
    Amazon product listing.

    Tracks both sourcing cost (buy_price) and current listing price (sell_price).
    fulfillment_type distinguishes FBA vs FBM for fee calculations.

    Attributes:
        sku: Seller-assigned Stock Keeping Unit.
        asin: Amazon Standard Identification Number.
        buy_price: Cost of goods sold (COGS) per unit.
        sell_price: Current Amazon listing price.
        fba_fee: Estimated FBA fulfillment fee per unit (0 if FBM).
        shipping_cost: Inbound shipping / prep cost per unit.
        stock: Current inventory quantity.
        reorder_point: Alert threshold – warn when stock <= this value.
        fulfillment_type: 'FBA' or 'FBM'.
    """

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("sku", name="uq_product_sku"),)

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    sku: str = Column(String(40), nullable=False)
    asin: str = Column(String(10), nullable=False)
    name: str = Column(String(255), nullable=False)
    category_id: int = Column(Integer, ForeignKey("categories.id"), nullable=False)
    buy_price: float = Column(Float, nullable=False, default=0.0)
    sell_price: float = Column(Float, nullable=False, default=0.0)
    weight_oz: float = Column(Float, nullable=False, default=0.0)
    length_in: float = Column(Float, nullable=False, default=0.0)
    width_in: float = Column(Float, nullable=False, default=0.0)
    height_in: float = Column(Float, nullable=False, default=0.0)
    fba_fee: float = Column(Float, nullable=False, default=0.0)
    shipping_cost: float = Column(Float, nullable=False, default=0.0)
    stock: int = Column(Integer, nullable=False, default=0)
    reorder_point: int = Column(Integer, nullable=False, default=5)
    fulfillment_type: str = Column(String(3), nullable=False, default="FBA")
    image_url: Optional[str] = Column(String(512), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    sales = relationship("Sale", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(sku='{self.sku}', name='{self.name}')>"


class Sale(Base):
    """
    Individual sale transaction.

    Stores the fee breakdown so profit can be audited retroactively.

    Fee calculation for Beauty & Personal Care (FBA):
        referral_fee  = sell_price × category.referral_fee_pct  (15 % est.)
        total_fees    = referral_fee + fba_fee + shipping_cost
        net_profit    = sell_price − COGS − total_fees

    Attributes:
        quantity: Units sold in this transaction.
        sell_price_each: Price per unit at time of sale.
        cogs_each: COGS per unit at time of sale.
        referral_fee: Amazon referral fee charged.
        fba_fee: FBA fulfillment fee charged (0 if FBM).
        shipping_cost: Shipping / logistics cost allocated.
        net_profit: Final profit after all deductions.
    """

    __tablename__ = "sales"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    product_id: int = Column(Integer, ForeignKey("products.id"), nullable=False)
    sale_date: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    quantity: int = Column(Integer, nullable=False, default=1)
    sell_price_each: float = Column(Float, nullable=False)
    cogs_each: float = Column(Float, nullable=False)
    referral_fee: float = Column(Float, nullable=False, default=0.0)
    fba_fee: float = Column(Float, nullable=False, default=0.0)
    shipping_cost: float = Column(Float, nullable=False, default=0.0)
    net_profit: float = Column(Float, nullable=False, default=0.0)

    product = relationship("Product", back_populates="sales")

    def __repr__(self) -> str:
        return (
            f"<Sale(product_id={self.product_id}, qty={self.quantity}, "
            f"profit=${self.net_profit:.2f})>"
        )
