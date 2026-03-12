"""
Inventory view – Product table with stock status, reorder alerts, and profit preview.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.controllers.inventory_controller import (
    delete_product,
    get_all_products,
    get_low_stock_products,
    get_product_by_sku,
    receive_stock,
)
from src.controllers.profit_calculator import calculate_profit
from src.controllers.velocity_engine import (
    calculate_daily_velocity,
    calculate_days_of_supply,
    get_restock_status,
    get_sales_last_30d,
)
from src.database import get_session


class InventoryView(QWidget):
    """Inventory table with stock levels, profit preview, and reorder alerts."""

    COLUMNS = [
        "SKU",
        "ASIN",
        "Product Name",
        "Category",
        "Type",
        "Buy $",
        "Sell $",
        "Ref. Fee",
        "FBA Fee",
        "Shipping",
        "Est. Profit",
        "ROI %",
        "Stock",
        "Velocity (30d)",
        "Days Left",
        "Status",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Inventory")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#232F3E;")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = QPushButton("⟳  Refresh")
        self.btn_refresh.setObjectName("primaryBtn")
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        self.btn_receive = QPushButton("📥  Receive Stock")
        self.btn_receive.setObjectName("primaryBtn")
        self.btn_receive.clicked.connect(self._on_receive_stock)
        header.addWidget(self.btn_receive)

        self.btn_duplicate = QPushButton("📑  Duplicate")
        self.btn_duplicate.setObjectName("primaryBtn")
        self.btn_duplicate.clicked.connect(self._on_duplicate)
        header.addWidget(self.btn_duplicate)

        self.btn_delete = QPushButton("🗑️  Delete")
        self.btn_delete.setObjectName("primaryBtn")
        self.btn_delete.setStyleSheet(
            "QPushButton{background-color:#D32F2F;color:#fff;border:none;"
            "border-radius:5px;padding:8px 20px;font-weight:bold;font-size:13px;}"
            "QPushButton:hover{background-color:#B71C1C;}"
        )
        self.btn_delete.clicked.connect(self._on_delete)
        header.addWidget(self.btn_delete)

        self.btn_add = QPushButton("＋  Add Product")
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.clicked.connect(self._on_add_product)
        header.addWidget(self.btn_add)

        root.addLayout(header)

        # Table
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table)

        # Summary bar
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size:13px;color:#6B7785;padding-top:4px;")
        root.addWidget(self.summary_label)

    # -------------------------------------------------------------- Refresh
    def refresh(self) -> None:
        session = get_session()
        try:
            products = get_all_products(session)
            self.table.setRowCount(len(products))

            total_inv_value = 0.0
            low_stock_count = 0

            for row, p in enumerate(products):
                # ── Financial breakdown (bundle_qty-aware COGS) ──
                effective_cogs = p.buy_price * p.bundle_qty
                breakdown = calculate_profit(
                    sell_price=p.sell_price,
                    cogs=effective_cogs,
                    referral_fee_pct=p.category.referral_fee_pct,
                    fba_fee=p.fba_fee,
                    shipping_cost=p.shipping_cost,
                )

                inv_value = p.stock * p.sell_price
                total_inv_value += inv_value

                # ── Velocity & days-of-supply ──
                sales_30d = get_sales_last_30d(session, p)
                velocity = calculate_daily_velocity(sales_30d)
                days_left = calculate_days_of_supply(p.stock, velocity)
                status = get_restock_status(p.stock, days_left)

                if status != "✓ OK":
                    low_stock_count += 1

                # Format velocity / days-left display
                velocity_text = f"{velocity:.1f} u/d"
                days_left_text = "∞" if days_left >= 999 else f"{days_left:.0f} d"

                values = [
                    p.sku,
                    p.asin,
                    p.name,
                    p.category.name,
                    p.fulfillment_type,
                    f"${p.buy_price:.2f}",
                    f"${p.sell_price:.2f}",
                    f"${breakdown.referral_fee:.2f}",
                    f"${breakdown.fba_fee:.2f}",
                    f"${breakdown.shipping_cost:.2f}",
                    f"${breakdown.net_profit:.2f}",
                    f"{breakdown.roi_pct:.1f}%",
                    str(p.stock),
                    velocity_text,
                    days_left_text,
                    status,
                ]

                col_status = len(self.COLUMNS) - 1   # Status column index
                col_profit = 10                        # Est. Profit column index

                for col, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter)

                    # Color-code Status column
                    if col == col_status:
                        if status == "OUT OF STOCK":
                            item.setBackground(QColor("#D32F2F"))
                            item.setForeground(Qt.GlobalColor.white)
                        elif status == "REORDER SOON":
                            item.setBackground(QColor("#FF9800"))
                            item.setForeground(Qt.GlobalColor.black)
                        else:
                            item.setForeground(QColor("#2E7D32"))

                    # Color-code profit
                    if col == col_profit:
                        if breakdown.net_profit >= 0:
                            item.setForeground(QColor("#2E7D32"))
                        else:
                            item.setForeground(QColor("#D32F2F"))

                    self.table.setItem(row, col, item)

            self.summary_label.setText(
                f"Total Products: {len(products)}  ·  "
                f"Inventory Value: ${total_inv_value:,.2f}  ·  "
                f"Needs Attention: {low_stock_count}"
            )
        finally:
            session.close()

    # --------------------------------------------------------- Add Product
    def _on_add_product(self) -> None:
        from src.views.product_form_view import ProductFormDialog

        dlg = ProductFormDialog(self)
        if dlg.exec():
            self.refresh()

    # ------------------------------------------------------- Receive Stock
    def _on_receive_stock(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Select Product",
                "Please select a product row first."
            )
            return

        name_item = self.table.item(row, 2)
        sku_item = self.table.item(row, 0)
        if not name_item or not sku_item:
            return

        product_name = name_item.text()
        qty, ok = QInputDialog.getInt(
            self,
            "Receive Stock",
            f"Units to add for '{product_name}':",
            1, 1, 999999,
        )
        if not ok:
            return

        sku = sku_item.text()
        session = get_session()
        try:
            product = get_product_by_sku(session, sku)
            if product:
                receive_stock(session, product.id, qty)
        finally:
            session.close()

        self.refresh()

    # ------------------------------------------------------------ Delete
    def _on_delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Select Product",
                "Please select a product row to delete."
            )
            return

        sku_item = self.table.item(row, 0)
        name_item = self.table.item(row, 2)
        if not sku_item or not name_item:
            return

        product_name = name_item.text()
        answer = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete '{product_name}'?\n\n"
            "This will also delete all sales history for this product. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        session = get_session()
        try:
            product = get_product_by_sku(session, sku_item.text())
            if product:
                delete_product(session, product.id)
        finally:
            session.close()

        self.refresh()

    # --------------------------------------------------------- Duplicate
    def _on_duplicate(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Select Product",
                "Please select a product row to duplicate."
            )
            return

        sku_item = self.table.item(row, 0)
        if not sku_item:
            return

        session = get_session()
        try:
            product = get_product_by_sku(session, sku_item.text())
        finally:
            session.close()

        if not product:
            return

        from src.views.product_form_view import ProductFormDialog

        dlg = ProductFormDialog(self, product_to_duplicate=product)
        if dlg.exec():
            self.refresh()
