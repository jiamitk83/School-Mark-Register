from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

import models  # noqa: F401  register SQLAlchemy models
from database import SessionLocal, init_database
from ui.main_window import MainWindow


def main() -> int:
    init_database()
    app = QApplication(sys.argv)
    window = MainWindow(SessionLocal)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
