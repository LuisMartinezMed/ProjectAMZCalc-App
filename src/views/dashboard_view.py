"""
Dashboard view – KPI cards + recent sales table.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.controllers.inventory_controller import get_dashboard_kpis
from src.database import get_session
from src.models.models import Sale


class KpiCard(QFrame):
    """Single KPI card widget."""

    def __init__(self, title: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "kpi-card")
        self.setObjectName("kpiCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)

        self._value_label = QLabel(value)
        self._value_label.setProperty("class", "kpi-value")
        self._value_label.setStyleSheet("font-size:26px;font-weight:bold;color:#232F3E;")

        self._title_label = QLabel(title)
        self._title_label.setProperty("class", "kpi-label")
        self._title_label.setStyleSheet("font-size:12px;color:#6B7785;")

        layout.addWidget(self._value_label)
        layout.addWidget(self._title_label)

        self.setStyleSheet(
            "KpiCard{background:#fff;border:1px solid #E3E6E8;border-radius:8px;}"
        )

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


class DashboardView(QWidget):
    """Central dashboard with KPIs and recent activity."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # Title
        title = QLabel("Dashboard")
        title.setProperty("class", "section-title")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#232F3E;")
        root.addWidget(title)

        # KPI row
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(16)

        self.kpi_revenue = KpiCard("Total Revenue", "$0.00")
        self.kpi_profit = KpiCard("Total Profit", "$0.00")
        self.kpi_units = KpiCard("Units Sold", "0")
        self.kpi_roi = KpiCard("Average ROI", "0 %")
        self.kpi_inv_value = KpiCard("Inventory Value", "$0.00")
        self.kpi_low_stock = KpiCard("Low Stock Alerts", "0")

        kpi_grid.addWidget(self.kpi_revenue, 0, 0)
        kpi_grid.addWidget(self.kpi_profit, 0, 1)
        kpi_grid.addWidget(self.kpi_units, 0, 2)
        kpi_grid.addWidget(self.kpi_roi, 1, 0)
        kpi_grid.addWidget(self.kpi_inv_value, 1, 1)
        kpi_grid.addWidget(self.kpi_low_stock, 1, 2)

        root.addLayout(kpi_grid)

        # Recent sales table
        table_title = QLabel("Recent Sales")
        table_title.setStyleSheet("font-size:15px;font-weight:bold;color:#232F3E;margin-top:8px;")
        root.addWidget(table_title)

        self.sales_table = QTableWidget(0, 7)
        self.sales_table.setHorizontalHeaderLabels(
            ["Date", "Product", "Qty", "Price", "Fees", "Profit", "ROI %"]
        )
        self.sales_table.horizontalHeader().setStretchLastSection(True)
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sales_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sales_table.setAlternatingRowColors(True)
        self.sales_table.verticalHeader().setVisible(False)
        root.addWidget(self.sales_table)

    # -------------------------------------------------------------- Refresh
    def refresh(self) -> None:
        """Reload KPIs and recent sales from the database."""
        session = get_session()
        try:
            kpis = get_dashboard_kpis(session)

            self.kpi_revenue.set_value(f"${kpis['total_revenue']:,.2f}")
            self.kpi_profit.set_value(f"${kpis['total_profit']:,.2f}")
            self.kpi_units.set_value(f"{kpis['total_units_sold']:,}")
            self.kpi_roi.set_value(f"{kpis['avg_roi']:.1f} %")
            self.kpi_inv_value.set_value(f"${kpis['inventory_value']:,.2f}")
            self.kpi_low_stock.set_value(str(kpis["low_stock_count"]))

            # Recent 20 sales
            recent_sales = (
                session.query(Sale)
                .order_by(Sale.sale_date.desc())
                .limit(20)
                .all()
            )
            self.sales_table.setRowCount(len(recent_sales))
            for row, sale in enumerate(recent_sales):
                product_name = sale.product.name if sale.product else "—"
                total_fees = sale.referral_fee + sale.fba_fee + sale.shipping_cost
                cogs_total = sale.cogs_each * sale.quantity
                roi = (sale.net_profit / cogs_total * 100) if cogs_total > 0 else 0

                items = [
                    sale.sale_date.strftime("%Y-%m-%d"),
                    product_name,
                    str(sale.quantity),
                    f"${sale.sell_price_each:.2f}",
                    f"${total_fees:.2f}",
                    f"${sale.net_profit:.2f}",
                    f"{roi:.1f}%",
                ]
                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter)
                    # Color-code profit
                    if col == 5:
                        color = "#067D62" if sale.net_profit >= 0 else "#DC3545"
                        item.setForeground(Qt.GlobalColor.darkGreen if sale.net_profit >= 0 else Qt.GlobalColor.red)
                    self.sales_table.setItem(row, col, item)
        finally:
            session.close()
