from __future__ import annotations

import csv
from io import StringIO

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from models import STANDARD_CLASSES
from services import ClassService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    TEXT_SECONDARY,
)


class BulkImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import Classes")
        self.resize(500, 400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        info = QLabel("Paste class names (one per line) or load from CSV/Excel:")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Nursery\nLKG\nUKG\nClass 1\nClass 2\n...")
        layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING_MD)
        self.load_csv_btn = QPushButton("Load CSV...")
        set_secondary_button(self.load_csv_btn, True)
        self.load_csv_btn.clicked.connect(self._load_csv)
        self.load_txt_btn = QPushButton("Load Text...")
        set_secondary_button(self.load_txt_btn, True)
        self.load_txt_btn.clicked.connect(self._load_txt)
        self.preview_btn = QPushButton("Preview")
        set_secondary_button(self.preview_btn, True)
        self.preview_btn.clicked.connect(self._preview)
        for b in (self.load_csv_btn, self.load_txt_btn, self.preview_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.preview_list = QTableWidget(0, 2)
        self.preview_list.setHorizontalHeaderLabels(["Class Name", "Status"])
        self.preview_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_list.setAlternatingRowColors(True)
        self.preview_list.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_list)

        self.skip_duplicates = QCheckBox("Skip duplicates")
        self.skip_duplicates.setChecked(True)
        layout.addWidget(self.skip_duplicates)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn:
            set_primary_button(ok_btn, True)
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn:
            set_secondary_button(cancel_btn, True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._created: list[str] = []
        self._errors: list[str] = []

    def _load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                names = [row[0] for row in reader if row]
            self.text_edit.setPlainText("\n".join(names))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load CSV: {exc}")

    def _load_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Text File", "", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.text_edit.setPlainText(content)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load file: {exc}")

    def _preview(self):
        text = self.text_edit.toPlainText()
        names = [line.strip() for line in text.splitlines() if line.strip()]
        self.preview_list.setRowCount(len(names))
        for i, name in enumerate(names):
            self.preview_list.setItem(i, 0, QTableWidgetItem(name))
            self.preview_list.setItem(i, 1, QTableWidgetItem("Ready"))

    def get_names(self) -> list[str]:
        text = self.text_edit.toPlainText()
        return [line.strip() for line in text.splitlines() if line.strip()]

    def skip_duplicates_enabled(self) -> bool:
        return self.skip_duplicates.isChecked()


class ClassView(QWidget):
    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_id: int | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_LG)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        # Form
        form = QGroupBox("Class Master")
        form_layout = QGridLayout(form)
        form_layout.setSpacing(SPACING_MD)
        form_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Class name, e.g. Class 1")
        self.order_edit = QLineEdit()
        self.order_edit.setPlaceholderText("Display order (auto if empty)")
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)
        self.add_btn = QPushButton("Add Class")
        set_primary_button(self.add_btn, True)
        self.add_btn.clicked.connect(self._add)

        form_layout.addWidget(QLabel("Name"), 0, 0)
        form_layout.addWidget(self.name_edit, 0, 1)
        form_layout.addWidget(QLabel("Display Order"), 1, 0)
        form_layout.addWidget(self.order_edit, 1, 1)
        form_layout.addWidget(self.active_check, 2, 0, 1, 2)
        form_layout.addWidget(self.add_btn, 3, 0, 1, 2)
        form_layout.setColumnStretch(1, 1)

        layout.addWidget(form)

        # Quick standard classes
        std_row = QHBoxLayout()
        std_row.setSpacing(SPACING_SM)
        std_label = QLabel("Quick add:")
        std_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 500;")
        std_row.addWidget(std_label)
        for std_name in STANDARD_CLASSES:
            btn = QPushButton(std_name)
            set_secondary_button(btn, True)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked, n=std_name: self._quick_add(n))
            std_row.addWidget(btn)
        std_row.addStretch()
        layout.addLayout(std_row)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Display Order", "Active", "Created"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(SPACING_MD)
        self.save_btn = QPushButton("Save Changes")
        set_secondary_button(self.save_btn, True)
        self.save_btn.clicked.connect(self._save)
        self.deactivate_btn = QPushButton("Deactivate")
        set_secondary_button(self.deactivate_btn, True)
        self.deactivate_btn.clicked.connect(self._deactivate)
        self.activate_btn = QPushButton("Activate")
        set_secondary_button(self.activate_btn, True)
        self.activate_btn.clicked.connect(self._activate)
        self.move_up_btn = QPushButton("Move Up")
        set_secondary_button(self.move_up_btn, True)
        self.move_up_btn.clicked.connect(self._move_up)
        self.move_down_btn = QPushButton("Move Down")
        set_secondary_button(self.move_down_btn, True)
        self.move_down_btn.clicked.connect(self._move_down)
        self.bulk_import_btn = QPushButton("Bulk Import...")
        set_primary_button(self.bulk_import_btn, True)
        self.bulk_import_btn.clicked.connect(self._bulk_import)
        self.refresh_btn = QPushButton("Refresh")
        set_secondary_button(self.refresh_btn, True)
        self.refresh_btn.clicked.connect(self.refresh)
        for b in (
            self.save_btn,
            self.deactivate_btn,
            self.activate_btn,
            self.move_up_btn,
            self.move_down_btn,
            self.bulk_import_btn,
            self.refresh_btn,
        ):
            btns.addWidget(b)
        btns.addStretch()
        layout.addLayout(btns)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

    def _service(self) -> ClassService:
        return ClassService(self.session_factory())

    def _clear_error(self) -> None:
        clear_error_label(self.error_label)
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

    def _reset_form(self) -> None:
        self.name_edit.clear()
        self.order_edit.clear()
        self.active_check.setChecked(True)

    def refresh(self) -> None:
        self._clear_error()
        self._selected_id = None
        self._reset_form()
        self.table.setRowCount(0)
        service = self._service()
        try:
            classes = service.list_classes()
        finally:
            service.session.close()
        for row_index, cls in enumerate(classes):
            self.table.insertRow(row_index)
            values = [
                str(cls.id),
                cls.name,
                str(cls.display_order),
                "Yes" if cls.is_active else "No",
                str(cls.created_at)[:10] if cls.created_at else "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, cls.id)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if value == "Yes":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    else:
                        item.setForeground(Qt.GlobalColor.darkRed)
                self.table.setItem(row_index, column, item)
        self.table.clearSelection()

    def _on_selection(self) -> None:
        self._clear_error()
        self._selected_id = None
        self._reset_form()
        row = self.table.currentRow()
        if row < 0:
            return
        id_item = self.table.item(row, 0)
        if id_item is None:
            return
        self._selected_id = int(id_item.text())
        service = self._service()
        try:
            cls = service.get_class(self._selected_id)
        finally:
            service.session.close()
        if cls is None:
            return
        self.name_edit.setText(cls.name)
        self.order_edit.setText(str(cls.display_order))
        self.active_check.setChecked(cls.is_active)

    def _add(self) -> None:
        self._clear_error()
        name = self.name_edit.text().strip()
        if not name:
            self._show_error("Class name is required")
            return
        order_text = self.order_edit.text().strip()
        display_order = int(order_text) if order_text else None
        service = self._service()
        try:
            service.add_class(name, display_order, self.active_check.isChecked())
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._reset_form()
        self.refresh()

    def _save(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a class to edit")
            return
        self._clear_error()
        name = self.name_edit.text().strip()
        order_text = self.order_edit.text().strip()
        display_order = int(order_text) if order_text else None
        service = self._service()
        try:
            service.update_class(self._selected_id, name or None, display_order, self.active_check.isChecked())
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _deactivate(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a class")
            return
        self._clear_error()
        service = self._service()
        try:
            service.deactivate_class(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _activate(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a class")
            return
        self._clear_error()
        service = self._service()
        try:
            service.activate_class(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _move_up(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a class")
            return
        self._clear_error()
        service = self._service()
        try:
            classes = service.list_classes()
            idx = next((i for i, c in enumerate(classes) if c.id == self._selected_id), -1)
            if idx <= 0:
                self._show_error("Already at top")
                return
            classes[idx], classes[idx - 1] = classes[idx - 1], classes[idx]
            service.reorder_classes([(c.id, c.display_order) for c in classes])
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _move_down(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a class")
            return
        self._clear_error()
        service = self._service()
        try:
            classes = service.list_classes()
            idx = next((i for i, c in enumerate(classes) if c.id == self._selected_id), -1)
            if idx < 0 or idx >= len(classes) - 1:
                self._show_error("Already at bottom")
                return
            classes[idx], classes[idx + 1] = classes[idx + 1], classes[idx]
            service.reorder_classes([(c.id, c.display_order) for c in classes])
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _bulk_import(self) -> None:
        dialog = BulkImportDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        names = dialog.get_names()
        if not names:
            self._show_error("No class names provided")
            return
        service = self._service()
        try:
            created, errors = service.bulk_import(names, dialog.skip_duplicates_enabled())
            if errors:
                self._show_error(f"Imported {len(created)}; issues: {'; '.join(errors)}")
            else:
                self._show_error(f"Imported {len(created)} classes")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
        finally:
            service.session.close()
        self.refresh()

    def _quick_add(self, name: str) -> None:
        self._clear_error()
        service = self._service()
        try:
            service.add_class(name)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()