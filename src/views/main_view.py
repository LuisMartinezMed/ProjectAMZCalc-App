"""
Main application window – sidebar navigation + stacked content area.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.views.dashboard_view import DashboardView
from src.views.inventory_view import InventoryView

_STYLE_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "styles" / "style.qss"


class MainWindow(QMainWindow):
    """Primary window with sidebar and stacked views."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Amazon Inventory & Profit Master")
        self.setMinimumSize(1100, 680)
        self.resize(1280, 780)

        # Load stylesheet
        if _STYLE_PATH.exists():
            self.setStyleSheet(_STYLE_PATH.read_text(encoding="utf-8"))

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Branding
        app_title = QLabel("AMZ Master")
        app_title.setObjectName("appTitle")
        sb_layout.addWidget(app_title)

        subtitle = QLabel("Inventory & Profit")
        subtitle.setObjectName("appSubtitle")
        sb_layout.addWidget(subtitle)

        # Nav buttons
        self._nav_buttons: list[QPushButton] = []
        self._stack = QStackedWidget()

        self.dashboard_view = DashboardView()
        self.inventory_view = InventoryView()

        self._add_nav("📊  Dashboard", self.dashboard_view)
        self._add_nav("📦  Inventory", self.inventory_view)

        for btn in self._nav_buttons:
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # Version label
        version = QLabel("v1.0.0  –  MVP")
        version.setStyleSheet("color:#5A6B7D;font-size:11px;padding:12px 20px;")
        sb_layout.addWidget(version)

        root_layout.addWidget(sidebar)

        # ── Content area ──────────────────────────────────
        root_layout.addWidget(self._stack)

        # Default to dashboard
        self._select_nav(0)

    # --------------------------------------------------------- Nav helpers
    def _add_nav(self, label: str, widget: QWidget) -> None:
        btn = QPushButton(label)
        btn.setCheckable(True)
        idx = len(self._nav_buttons)
        btn.clicked.connect(lambda checked, i=idx: self._select_nav(i))
        self._nav_buttons.append(btn)
        self._stack.addWidget(widget)

    def _select_nav(self, index: int) -> None:
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        self._stack.setCurrentIndex(index)

        # Refresh active view when selected
        current = self._stack.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()
