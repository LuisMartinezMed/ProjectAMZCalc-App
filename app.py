"""
Amazon Inventory & Profit Master – Application entry point.

Usage:
    python app.py          Launch the GUI (seeds DB on first run).
    python app.py --seed   Re-seed the database and launch.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports resolve.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from src.database import init_db
from src.seed import seed
from src.views.main_view import MainWindow


def main() -> None:
    # Initialize database tables
    init_db()

    # Seed on first run or when --seed flag is passed
    if "--seed" in sys.argv:
        seed()
    else:
        # Auto-seed if DB is empty
        from src.database import get_session
        from src.models.models import Product

        session = get_session()
        try:
            if session.query(Product).count() == 0:
                seed()
        finally:
            session.close()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
