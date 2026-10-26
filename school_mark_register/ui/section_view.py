from __future__ import annotations

import csv
from io import StringIO

from PySide6.QtCore import Qt
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
from services import SectionService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    TEXT_SECONDARY,
)


class BulkImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import Sections")
        self.resize(500, 400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        info = QLabel("Paste section names (one per line) or load from CSV/Excel:")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Section A\nSection B\nSection C\n...")
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

        self.preview_list = QTableWidget(0, 3)
        self.preview_list.setHorizontalHeaderLabels(["Section Name", "Display Order", "Status"])
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

    def _load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                lines = []
                for row in reader:
                    if row:
                        if len(row) > 1 and row[1].strip():
                            lines.append(f"{row[0]},{row[1]}")
                        else:
                            lines.append(row[0])
            self.text_edit.setPlainText("\n".join(lines))
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
            parts = name.split(",")
            section_name = parts[0].strip()
            display_order = parts[1].strip() if len(parts) > 1 else ""
            self.preview_list.setItem(i, 0, QTableWidgetItem(section_name))
            self.preview_list.setItem(i, 1, QTableWidgetItem(display_order))
            self.preview_list.setItem(i, 2, QTableWidgetItem("Ready"))

    def get_entries(self) -> list[tuple[str, int | None]]:
        """Return list of (name, display_order) tuples."""
        text = self.text_edit.toPlainText()
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            name = parts[0].strip()
            display_order = None
            if len(parts) > 1 and parts[1].strip():
                try:
                    display_order = int(parts[1].strip())
                except ValueError:
                    display_order = None
            entries.append((name, display_order))
        return entries

    def skip_duplicates_enabled(self) -> bool:
        return self.skip_duplicates.isChecked()


class SectionView(QWidget):
    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_class_id: int | None = None
        self._selected_section_id: int | None = None
        self._build_ui()
        self._load_classes()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_LG)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        # Class selector
        class_group = QGroupBox("Select Class")
        class_layout = QHBoxLayout(class_group)
        class_layout.setSpacing(SPACING_MD)
        class_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(300)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)
        class_label = QLabel("Class:")
        class_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 500;")
        class_layout.addWidget(class_label)
        class_layout.addWidget(self.class_combo)
        class_layout.addStretch()
        layout.addWidget(class_group)

        # Form
        form = QGroupBox("Section Master")
        form_layout = QGridLayout(form)
        form_layout.setSpacing(SPACING_MD)
        form_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Section name, e.g. Section A")
        self.order_edit = QLineEdit()
        self.order_edit.setPlaceholderText("Display order (auto if empty)")
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)
        self.add_btn = QPushButton("Add Section")
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

    def _service(self) -> SectionService:
        return SectionService(self.session_factory())

    def _class_service(self):
        from services import ClassService
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

    def _load_classes(self) -> None:
        service = self._class_service()
        try:
            classes = service.list_active_classes()
            self.class_combo.clear()
            for cls in classes:
                self.class_combo.addItem(cls.name, cls.id)
        finally:
            service.session.close()

    def _on_class_changed(self) -> None:
        self._selected_class_id = None
        self._selected_section_id = None
        self._reset_form()
        idx = self.class_combo.currentIndex()
        if idx >= 0:
            self._selected_class_id = self.class_combo.itemData(idx)
            self.refresh()

    def refresh(self) -> None:
        self._clear_error()
        self._selected_section_id = None
        self._reset_form()
        self.table.setRowCount(0)
        if self._selected_class_id is None:
            return
        service = self._service()
        try:
            sections = service.list_sections(self._selected_class_id)
        finally:
            service.session.close()
        for row_index, sec in enumerate(sections):
            self.table.insertRow(row_index)
            values = [
                str(sec.id),
                sec.name,
                str(sec.display_order),
                "Yes" if sec.is_active else "No",
                str(sec.created_at)[:10] if sec.created_at else "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, sec.id)
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
        self._selected_section_id = None
        self._reset_form()
        row = self.table.currentRow()
        if row < 0:
            return
        id_item = self.table.item(row, 0)
        if id_item is None:
            return
        self._selected_section_id = int(id_item.text())
        service = self._service()
        try:
            sec = service.get_section(self._selected_section_id)
        finally:
            service.session.close()
        if sec is None:
            return
        self.name_edit.setText(sec.name)
        self.order_edit.setText(str(sec.display_order))
        self.active_check.setChecked(sec.is_active)

    def _add(self) -> None:
        if self._selected_class_id is None:
            self._show_error("Select a class first")
            return
        self._clear_error()
        name = self.name_edit.text().strip()
        if not name:
            self._show_error("Section name is required")
            return
        order_text = self.order_edit.text().strip()
        display_order = int(order_text) if order_text else None
        service = self._service()
        try:
            service.add_section(self._selected_class_id, name, display_order, self.active_check.isChecked())
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._reset_form()
        self.refresh()

    def _save(self) -> None:
        if self._selected_section_id is None:
            self._show_error("Select a section to edit")
            return
        self._clear_error()
        name = self.name_edit.text().strip()
        order_text = self.order_edit.text().strip()
        display_order = int(order_text) if order_text else None
        service = self._service()
        try:
            service.update_section(self._selected_section_id, name or None, display_order, self.active_check.isChecked())
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _deactivate(self) -> None:
        if self._selected_section_id is None:
            self._show_error("Select a section")
            return
        self._clear_error()
        service = self._service()
        try:
            service.deactivate_section(self._selected_section_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _activate(self) -> None:
        if self._selected_section_id is None:
            self._show_error("Select a section")
            return
        self._clear_error()
        service = self._service()
        try:
            service.activate_section(self._selected_section_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _move_up(self) -> None:
        if self._selected_section_id is None or self._selected_class_id is None:
            self._show_error("Select a section")
            return
        self._clear_error()
        service = self._service()
        try:
            sections = service.list_sections(self._selected_class_id)
            idx = next((i for i, s in enumerate(sections) if s.id == self._selected_section_id), -1)
            if idx <= 0:
                self._show_error("Already at top")
                return
            sections[idx], sections[idx - 1] = sections[idx - 1], sections[idx]
            service.reorder_sections(self._selected_class_id, [(s.id, s.display_order) for s in sections])
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _move_down(self) -> None:
        if self._selected_section_id is None or self._selected_class_id is None:
            self._show_error("Select a section")
            return
        self._clear_error()
        service = self._service()
        try:
            sections = service.list_sections(self._selected_class_id)
            idx = next((i for i, s in enumerate(sections) if s.id == self._selected_section_id), -1)
            if idx < 0 or idx >= len(sections) - 1:
                self._show_error("Already at bottom")
                return
            sections[idx], sections[idx + 1] = sections[idx + 1], sections[idx]
            service.reorder_sections(self._selected_class_id, [(s.id, s.display_order) for s in sections])
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _bulk_import(self) -> None:
        if self._selected_class_id is None:
            self._show_error("Select a class first")
            return
        dialog = BulkImportDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        entries = dialog.get_entries()
        if not entries:
            self._show_error("No section names provided")
            return
        service = self._service()
        try:
            created, errors = service.bulk_import(self._selected_class_id, [e[0] for e in entries], dialog.skip_duplicates_enabled())
            if errors:
                self._show_error(f"Imported {len(created)}; issues: {'; '.join(errors)}")
            else:
                self._show_error(f"Imported {len(created)} sections")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
        finally:
            service.session.close()
        self.refresh()