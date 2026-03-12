"""
Product form dialog – modal form for adding a new product to the inventory.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.controllers.inventory_controller import (
    add_product_from_dict,
    get_product_by_sku,
    list_categories,
)
from src.database import get_session

# Default categories shown before any custom ones exist
_DEFAULT_CATEGORIES = [
    "Beauty & Personal Care",
    "Electronics",
    "Home & Kitchen",
    "Sports & Outdoors",
    "Toys & Games",
    "Health & Household",
    "Grocery",
    "Clothing",
    "Office Products",
    "Other",
]


class ProductFormDialog(QDialog):
    """Modal dialog to capture a new product's information."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add New Product")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("New Product")
        title.setStyleSheet("font-size:18px;font-weight:bold;color:#232F3E;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Text fields ---
        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("e.g. MY-SKU-001")
        form.addRow("SKU:", self.sku_input)

        self.asin_input = QLineEdit()
        self.asin_input.setPlaceholderText("e.g. B09XXXXXXX")
        self.asin_input.setMaxLength(10)
        form.addRow("ASIN:", self.asin_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Product name")
        form.addRow("Name:", self.name_input)

        # --- Dropdowns ---
        self.category_combo = QComboBox()
        self._populate_categories()
        form.addRow("Category:", self.category_combo)

        self.fulfillment_combo = QComboBox()
        self.fulfillment_combo.addItems(["FBA", "FBM"])
        form.addRow("Fulfillment:", self.fulfillment_combo)

        # --- Numeric fields (with validators) ---
        dbl = QDoubleValidator(0.0, 999999.99, 2)
        int_val = QIntValidator(0, 999999)

        self.cost_input = QLineEdit()
        self.cost_input.setValidator(dbl)
        self.cost_input.setPlaceholderText("0.00")
        form.addRow("Cost ($):", self.cost_input)

        self.price_input = QLineEdit()
        self.price_input.setValidator(dbl)
        self.price_input.setPlaceholderText("0.00")
        form.addRow("Sell Price ($):", self.price_input)

        self.weight_input = QLineEdit()
        self.weight_input.setValidator(dbl)
        self.weight_input.setPlaceholderText("oz")
        form.addRow("Weight (oz):", self.weight_input)

        self.length_input = QLineEdit()
        self.length_input.setValidator(dbl)
        self.length_input.setPlaceholderText("in")
        form.addRow("Length (in):", self.length_input)

        self.width_input = QLineEdit()
        self.width_input.setValidator(dbl)
        self.width_input.setPlaceholderText("in")
        form.addRow("Width (in):", self.width_input)

        self.height_input = QLineEdit()
        self.height_input.setValidator(dbl)
        self.height_input.setPlaceholderText("in")
        form.addRow("Height (in):", self.height_input)

        self.stock_input = QLineEdit()
        self.stock_input.setValidator(int_val)
        self.stock_input.setPlaceholderText("0")
        form.addRow("Initial Stock:", self.stock_input)

        layout.addLayout(form)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Product")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_save)

        layout.addLayout(btn_row)

    # -------------------------------------------------------- Category list
    def _populate_categories(self) -> None:
        session = get_session()
        try:
            db_cats = list_categories(session)
            names = [c.name for c in db_cats]
        finally:
            session.close()

        # Merge DB categories with defaults (no duplicates)
        all_cats = list(dict.fromkeys(names + _DEFAULT_CATEGORIES))
        self.category_combo.addItems(all_cats)

    # -------------------------------------------------------- Save handler
    def _on_save(self) -> None:
        # Gather & validate
        sku = self.sku_input.text().strip()
        asin = self.asin_input.text().strip()
        name = self.name_input.text().strip()

        if not sku or not asin or not name:
            QMessageBox.warning(self, "Validation", "SKU, ASIN, and Name are required.")
            return

        try:
            cost = float(self.cost_input.text() or 0)
            price = float(self.price_input.text() or 0)
            weight = float(self.weight_input.text() or 0)
            length = float(self.length_input.text() or 0)
            width = float(self.width_input.text() or 0)
            height = float(self.height_input.text() or 0)
            stock = int(self.stock_input.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Validation", "Numeric fields contain invalid values.")
            return

        # Check duplicate SKU
        session = get_session()
        try:
            if get_product_by_sku(session, sku):
                QMessageBox.warning(self, "Duplicate", f"A product with SKU '{sku}' already exists.")
                return

            data = {
                "sku": sku,
                "asin": asin,
                "name": name,
                "category": self.category_combo.currentText(),
                "fulfillment_type": self.fulfillment_combo.currentText(),
                "buy_price": cost,
                "sell_price": price,
                "weight_oz": weight,
                "length_in": length,
                "width_in": width,
                "height_in": height,
                "stock": stock,
            }
            add_product_from_dict(session, data)
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Could not save product:\n{exc}")
            return
        finally:
            session.close()

        self.accept()  # closes dialog with QDialog.Accepted
