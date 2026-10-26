from __future__ import annotations

from PySide6.QtWidgets import QApplication

# Color palette
PRIMARY_DARK = "#1e3a5f"      # Dark navy for sidebar, headers
PRIMARY = "#2d6da3"           # Primary blue
PRIMARY_LIGHT = "#3a8fd6"     # Lighter blue for hover
ACCENT = "#4aa3ff"            # Accent blue for focus
WHITE = "#ffffff"
BG_LIGHT = "#f5f7fa"          # Light background
BG_CARD = "#ffffff"           # Card/panel background
BORDER = "#d0d8e0"            # Border color
BORDER_FOCUS = "#2d6da3"      # Focus border
TEXT_PRIMARY = "#1a2a3a"      # Primary text
TEXT_SECONDARY = "#5a6a7a"    # Secondary text
TEXT_MUTED = "#9aa5b1"        # Muted text
ERROR = "#c0392b"             # Error red
ERROR_BG = "#fdf2f2"          # Error background
SUCCESS = "#27ae60"           # Success green
SUCCESS_BG = "#eafaf1"        # Success background
WARNING = "#f39c12"           # Warning amber

# Spacing
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

# Border radius
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8

# Font sizes
FONT_SM = "12px"
FONT_BASE = "13px"
FONT_LG = "15px"
FONT_XL = "18px"
FONT_HEADING = "20px"

# Global stylesheet
GLOBAL_QSS = f"""
/* Base application */
QWidget {{
    font-family: "Segoe UI", "Inter", "Roboto", "Helvetica Neue", Arial, sans-serif;
    font-size: {FONT_BASE};
    color: {TEXT_PRIMARY};
    background-color: {BG_LIGHT};
}}

/* Main window */
QMainWindow {{
    background-color: {BG_LIGHT};
}}

/* Group boxes */
QGroupBox {{
    font-size: {FONT_LG};
    font-weight: 600;
    color: {PRIMARY_DARK};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_MD}px;
    margin-top: {SPACING_MD}px;
    padding-top: {SPACING_LG}px;
    background-color: {BG_CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {SPACING_MD}px;
    padding: 0 {SPACING_SM}px;
    background-color: {BG_CARD};
}}

/* Labels */
QLabel {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_BASE};
}}

/* Line edits, combo boxes, date edits, spin boxes */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background-color: {WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_BASE};
    color: {TEXT_PRIMARY};
    selection-background-color: {PRIMARY_LIGHT};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 2px solid {BORDER_FOCUS};
    background-color: {WHITE};
}}
QLineEdit::placeholder, QComboBox::placeholder {{
    color: {TEXT_MUTED};
}}
QComboBox::drop-down {{
    border: none;
    width: {SPACING_LG}px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    background-color: {WHITE};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {TEXT_PRIMARY};
}}
QDateEdit::drop-down {{
    border: none;
    width: {SPACING_LG}px;
}}

/* Check boxes */
QCheckBox {{
    spacing: {SPACING_SM}px;
    font-size: {FONT_BASE};
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: {RADIUS_SM}px;
    background-color: {WHITE};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
}}
QCheckBox::indicator:hover {{
    border-color: {PRIMARY_LIGHT};
}}

/* Buttons - Base */
QPushButton {{
    font-size: {FONT_BASE};
    font-weight: 500;
    border-radius: {RADIUS_SM}px;
    padding: {SPACING_SM}px {SPACING_LG}px;
    min-height: 32px;
    border: 1px solid transparent;
}}

/* Primary button */
QPushButton[primary="true"] {{
    background-color: {PRIMARY};
    color: {WHITE};
    border-color: {PRIMARY};
}}
QPushButton[primary="true"]:hover {{
    background-color: {PRIMARY_LIGHT};
    border-color: {PRIMARY_LIGHT};
}}
QPushButton[primary="true"]:pressed {{
    background-color: {PRIMARY_DARK};
    border-color: {PRIMARY_DARK};
}}
QPushButton[primary="true"]:disabled {{
    background-color: {TEXT_MUTED};
    border-color: {TEXT_MUTED};
    color: {BG_CARD};
}}

/* Secondary button */
QPushButton[secondary="true"] {{
    background-color: {BG_CARD};
    color: {PRIMARY};
    border-color: {PRIMARY};
}}
QPushButton[secondary="true"]:hover {{
    background-color: #e8f0f8;
    border-color: {PRIMARY_LIGHT};
}}
QPushButton[secondary="true"]:pressed {{
    background-color: #d0e0f0;
    border-color: {PRIMARY_DARK};
}}
QPushButton[secondary="true"]:disabled {{
    background-color: {BG_LIGHT};
    border-color: {TEXT_MUTED};
    color: {TEXT_MUTED};
}}

/* Danger button */
QPushButton[danger="true"] {{
    background-color: {ERROR};
    color: {WHITE};
    border-color: {ERROR};
}}
QPushButton[danger="true"]:hover {{
    background-color: #e74c3c;
    border-color: #e74c3c;
}}
QPushButton[danger="true"]:pressed {{
    background-color: #a93226;
    border-color: #a93226;
}}
QPushButton[danger="true"]:disabled {{
    background-color: #f5b7b1;
    border-color: #f5b7b1;
    color: {BG_CARD};
}}

/* Default button (no attribute) - treat as secondary */
QPushButton:not([primary]):not([secondary]):not([danger]) {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border-color: {BORDER};
}}
QPushButton:not([primary]):not([secondary]):not([danger]):hover {{
    background-color: {BG_LIGHT};
    border-color: {PRIMARY_LIGHT};
}}
QPushButton:not([primary]):not([secondary]):not([danger]):pressed {{
    background-color: {BORDER};
}}
QPushButton:not([primary]):not([secondary]):not([danger]):disabled {{
    background-color: {BG_LIGHT};
    border-color: {TEXT_MUTED};
    color: {TEXT_MUTED};
}}

/* Tables */
QTableWidget {{
    background-color: {WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_MD}px;
    gridline-color: {BORDER};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {TEXT_PRIMARY};
    alternate-background-color: #fafbfc;
}}
QTableWidget::item {{
    padding: {SPACING_SM}px {SPACING_MD}px;
    border-bottom: 1px solid {BORDER};
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY_LIGHT};
    color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: {PRIMARY_DARK};
    color: {WHITE};
    font-size: {FONT_SM};
    font-weight: 600;
    padding: {SPACING_SM}px {SPACING_MD}px;
    border: none;
    border-right: 1px solid rgba(255,255,255,0.1);
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* Scroll bars */
QScrollBar:vertical {{
    background-color: {BG_LIGHT};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {TEXT_MUTED};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {PRIMARY_LIGHT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: {BG_LIGHT};
    height: 10px;
    border: none.
}}
QScrollBar::handle:horizontal {{
    background-color: {TEXT_MUTED};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {PRIMARY_LIGHT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* List widget (sidebar) */
QListWidget {{
    background-color: {PRIMARY_DARK};
    border: none;
    outline: none;
    font-size: {FONT_BASE};
}}
QListWidget::item {{
    color: {WHITE};
    padding: {SPACING_MD}px {SPACING_LG}px;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
QListWidget::item:selected {{
    background-color: {PRIMARY_LIGHT};
    color: {WHITE};
    font-weight: 500;
}}
QListWidget::item:hover:!selected {{
    background-color: rgba(255,255,255,0.08);
}}

/* Dialogs */
QDialog {{
    background-color: {BG_LIGHT};
}}
QDialog QLabel {{
    color: {TEXT_PRIMARY};
}}
QDialogButtonBox QPushButton {{
    min-width: 100px;
}}

/* Message boxes */
QMessageBox {{
    background-color: {BG_LIGHT};
}}
QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_BASE};
}}
QMessageBox QPushButton {{
    min-width: 90px;
    padding: {SPACING_SM}px {SPACING_MD}px;
}}

/* File dialog */
QFileDialog {{
    background-color: {BG_LIGHT};
}}

/* Progress bar */
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px;
    background-color: {BG_LIGHT};
    text-align: center;
    font-size: {FONT_SM};
}}
QProgressBar::chunk {{
    background-color: {PRIMARY};
    border-radius: {RADIUS_SM}px;
}}

/* Tooltip */
QToolTip {{
    background-color: {PRIMARY_DARK};
    color: {WHITE};
    border: 1px solid {PRIMARY_LIGHT};
    border-radius: {RADIUS_SM}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_SM};
}}

/* Error label */
QLabel[error="true"] {{
    color: {ERROR};
    font-size: {FONT_SM};
    font-weight: 500;
    padding: {SPACING_SM}px {SPACING_MD}px;
    background-color: {ERROR_BG};
    border-radius: {RADIUS_SM}px;
    border: 1px solid {ERROR};
}}

/* Success label */
QLabel[success="true"] {{
    color: {SUCCESS};
    font-size: {FONT_SM};
    font-weight: 500;
    padding: {SPACING_SM}px {SPACING_MD}px;
    background-color: {SUCCESS_BG};
    border-radius: {RADIUS_SM}px;
    border: 1px solid {SUCCESS};
}}

/* Splitter */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:hover {{
    background-color: {PRIMARY_LIGHT};
}}

/* Stacked widget */
QStackedWidget {{
    background-color: {BG_LIGHT};
    border: none;
}}

/* Scroll area */
QScrollArea {{
    border: none;
    background-color: {BG_LIGHT};
}}
QScrollArea > QWidget > QWidget {{
    background-color: {BG_LIGHT};
}}
"""

def apply_global_style(app: QApplication) -> None:
    """Apply the global stylesheet to the application."""
    app.setStyleSheet(GLOBAL_QSS)

def set_primary_button(btn, primary: bool = True) -> None:
    """Set button as primary style."""
    btn.setProperty("primary", primary)
    if not primary:
        btn.setProperty("secondary", True)
    btn.style().unpolish(btn)
    btn.style().polish(btn)

def set_secondary_button(btn, secondary: bool = True) -> None:
    """Set button as secondary style."""
    btn.setProperty("secondary", secondary)
    if not secondary:
        btn.setProperty("primary", True)
    btn.style().unpolish(btn)
    btn.style().polish(btn)

def set_danger_button(btn, danger: bool = True) -> None:
    """Set button as danger style."""
    btn.setProperty("danger", danger)
    btn.style().unpolish(btn)
    btn.style().polish(btn)

def set_error_label(label, message: str = "") -> None:
    """Set label as error style."""
    label.setProperty("error", True)
    label.setText(message)
    label.style().unpolish(label)
    label.style().polish(label)

def clear_error_label(label) -> None:
    """Clear error label style."""
    label.setProperty("error", False)
    label.setText("")
    label.style().unpolish(label)
    label.style().polish(label)