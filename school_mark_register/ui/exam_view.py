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
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import ExamTypeService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    TEXT_SECONDARY,
)


class ExamTypeImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import Exam Types")
        self.resize(600, 450)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        info = QLabel("Paste exam type data (Name,Code,Description,Max Marks,Weightage,Active) or load CSV:")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Mid-term,MT,Mid-term Examination,100,0.5,Yes\n"
            "Final,FIN,Final Examination,100,1.0,Yes\n"
            "Unit Test,UT,Unit Test,50,0.25,Yes"
        )
        layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING_MD)
        self.load_csv_btn = QPushButton("Load CSV...")
        self.load_csv_btn.clicked.connect(self._load_csv)
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self._preview)
        for b in (self.load_csv_btn, self.preview_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.preview_table = QTableWidget(0, 6)
        self.preview_table.setHorizontalHeaderLabels(
            ["Name", "Code", "Description", "Max Marks", "Weightage", "Status"]
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table)

        self.skip_duplicates = QCheckBox("Skip duplicates")
        self.skip_duplicates.setChecked(True)
        layout.addWidget(self.skip_duplicates)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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
                        lines.append(",".join(row))
            self.text_edit.setPlainText("\n".join(lines))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load CSV: {exc}")

    def _preview(self):
        text = self.text_edit.toPlainText()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        self.preview_table.setRowCount(len(lines))
        for i, line in enumerate(lines):
            parts = [p.strip() for p in line.split(",")]
            name = parts[0] if len(parts) > 0 else ""
            code = parts[1] if len(parts) > 1 else ""
            desc = parts[2] if len(parts) > 2 else ""
            max_marks = parts[3] if len(parts) > 3 else "100"
            weightage = parts[4] if len(parts) > 4 else "1.0"
            active = parts[5] if len(parts) > 5 else "Yes"
            self.preview_table.setItem(i, 0, QTableWidgetItem(name))
            self.preview_table.setItem(i, 1, QTableWidgetItem(code))
            self.preview_table.setItem(i, 2, QTableWidgetItem(desc))
            self.preview_table.setItem(i, 3, QTableWidgetItem(max_marks))
            self.preview_table.setItem(i, 4, QTableWidgetItem(weightage))
            self.preview_table.setItem(i, 5, QTableWidgetItem("Ready" if name and code else "Missing data"))

    def get_entries(self) -> list[dict]:
        text = self.text_edit.toPlainText()
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            while len(parts) < 6:
                parts.append("")
            entry = {
                "name": parts[0],
                "code": parts[1],
                "description": parts[2] if parts[2] else None,
                "max_marks": int(parts[3]) if parts[3] else 100,
                "weightage": float(parts[4]) if parts[4] else 1.0,
                "is_active": parts[5].lower() in ("yes", "true", "1", "y"),
            }
            entries.append(entry)
        return entries

    def skip_duplicates_enabled(self) -> bool:
        return self.skip_duplicates.isChecked()


class ExamView(QWidget):
    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_id: int | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Create scroll area for the entire page
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(SPACING_LG)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Exam Configuration")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #1e3a5f;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        header_layout.addWidget(self.export_csv_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        # Form
        self.form_group = QGroupBox("Exam Type Details")
        form_layout = QFormLayout(self.form_group)
        form_layout.setSpacing(SPACING_MD)
        form_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Exam type name, e.g. Mid-term")
        self.name_edit.setMinimumWidth(300)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Short code, e.g. MT")
        self.code_edit.setMaxLength(20)
        self.code_edit.setMinimumWidth(150)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description (optional)")
        self.desc_edit.setMinimumWidth(300)

        self.max_marks_spin = QSpinBox()
        self.max_marks_spin.setRange(1, 1000)
        self.max_marks_spin.setValue(100)
        self.max_marks_spin.setMinimumWidth(150)

        self.weightage_spin = QDoubleSpinBox()
        self.weightage_spin.setRange(0.0, 10.0)
        self.weightage_spin.setSingleStep(0.25)
        self.weightage_spin.setValue(1.0)
        self.weightage_spin.setDecimals(2)
        self.weightage_spin.setMinimumWidth(150)

        self.order_edit = QLineEdit()
        self.order_edit.setPlaceholderText("Display order (auto if empty)")
        self.order_edit.setMinimumWidth(150)

        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)

        form_layout.addRow("Name *", self.name_edit)
        form_layout.addRow("Code *", self.code_edit)
        form_layout.addRow("Description", self.desc_edit)
        form_layout.addRow("Max Marks *", self.max_marks_spin)
        form_layout.addRow("Weightage", self.weightage_spin)
        form_layout.addRow("Display Order", self.order_edit)
        form_layout.addRow("", self.active_check)

        # Form buttons
        form_btn_layout = QHBoxLayout()
        form_btn_layout.setSpacing(SPACING_MD)
        self.add_btn = QPushButton("Add Exam Type")
        set_primary_button(self.add_btn, True)
        self.add_btn.clicked.connect(self._add)
        form_btn_layout.addWidget(self.add_btn)
        self.save_btn = QPushButton("Save Changes")
        set_secondary_button(self.save_btn, True)
        self.save_btn.clicked.connect(self._save)
        self.bulk_import_btn = QPushButton("Bulk Import...")
        set_primary_button(self.bulk_import_btn, True)
        self.bulk_import_btn.clicked.connect(self._bulk_import)
        form_btn_layout.addWidget(self.save_btn)
        form_btn_layout.addWidget(self.bulk_import_btn)
        form_btn_layout.addStretch()
        form_layout.addRow(form_btn_layout)

        layout.addWidget(self.form_group)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Code", "Description", "Max Marks", "Weightage", "Display Order", "Active"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Table action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(SPACING_MD)
        self.deactivate_btn = QPushButton("Deactivate")
        set_secondary_button(self.deactivate_btn, True)
        self.deactivate_btn.clicked.connect(self._deactivate)
        self.activate_btn = QPushButton("Activate")
        set_secondary_button(self.activate_btn, True)
        self.activate_btn.clicked.connect(self._activate)
        self.delete_btn = QPushButton("Delete")
        set_danger_button(self.delete_btn, True)
        self.delete_btn.clicked.connect(self._delete)
        self.move_up_btn = QPushButton("Move Up")
        set_secondary_button(self.move_up_btn, True)
        self.move_up_btn.clicked.connect(self._move_up)
        self.move_down_btn = QPushButton("Move Down")
        set_secondary_button(self.move_down_btn, True)
        self.move_down_btn.clicked.connect(self._move_down)
        self.refresh_btn = QPushButton("Refresh List")
        set_secondary_button(self.refresh_btn, True)
        self.refresh_btn.clicked.connect(self._refresh_list)
        for b in (
            self.deactivate_btn,
            self.activate_btn,
            self.delete_btn,
            self.move_up_btn,
            self.move_down_btn,
            self.refresh_btn,
        ):
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Set the scroll area widget
        scroll.setWidget(content)

        # Main layout for the view
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # --- Service helpers ---

    def _service(self) -> ExamTypeService:
        return ExamTypeService(self.session_factory())

    # --- Error helpers ---

    def _clear_error(self) -> None:
        clear_error_label(self.error_label)
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

    def _reset_form(self) -> None:
        self.name_edit.clear()
        self.code_edit.clear()
        self.desc_edit.clear()
        self.max_marks_spin.setValue(100)
        self.weightage_spin.setValue(1.0)
        self.order_edit.clear()
        self.active_check.setChecked(True)
        self._selected_id = None

    # --- Data loading ---

    def refresh(self) -> None:
        self._clear_error()
        self._reset_form()
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._clear_error()
        self._selected_id = None
        self.table.setRowCount(0)

        service = self._service()
        try:
            exam_types = service.list_exam_types()
        finally:
            service.session.close()

        for row_index, et in enumerate(exam_types):
            self.table.insertRow(row_index)
            values = [
                str(et.id),
                et.name,
                et.code,
                et.description or "",
                str(et.max_marks),
                str(et.weightage),
                str(et.display_order),
                "Yes" if et.is_active else "No",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, et.id)
                if col == 7:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if val == "Yes":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    else:
                        item.setForeground(Qt.GlobalColor.darkRed)
                self.table.setItem(row_index, col, item)
        self.table.clearSelection()

    def _on_selection(self) -> None:
        self._clear_error()
        self._selected_id = None
        row = self.table.currentRow()
        if row < 0:
            return
        id_item = self.table.item(row, 0)
        if id_item is None:
            return
        self._selected_id = int(id_item.text())

        service = self._service()
        try:
            et = service.get_exam_type(self._selected_id)
        finally:
            service.session.close()
        if et is None:
            return

        self.name_edit.setText(et.name)
        self.code_edit.setText(et.code)
        self.desc_edit.setText(et.description or "")
        self.max_marks_spin.setValue(et.max_marks)
        self.weightage_spin.setValue(et.weightage)
        self.order_edit.setText(str(et.display_order))
        self.active_check.setChecked(et.is_active)

    # --- CRUD operations ---

    def _add(self) -> None:
        self._clear_error()
        name = self.name_edit.text().strip()
        code = self.code_edit.text().strip().upper()
        if not name:
            self._show_error("Exam type name is required")
            return
        if not code:
            self._show_error("Exam type code is required")
            return

        service = self._service()
        try:
            order_text = self.order_edit.text().strip()
            display_order = int(order_text) if order_text else None
            service.add_exam_type(
                name=name,
                code=code,
                description=self.desc_edit.text().strip() or None,
                max_marks=self.max_marks_spin.value(),
                weightage=self.weightage_spin.value(),
                display_order=display_order,
                is_active=self.active_check.isChecked(),
            )
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._reset_form()
        self._refresh_list()

    def _save(self) -> None:
        if self._selected_id is None:
            self._show_error("Select an exam type to edit")
            return
        self._clear_error()
        name = self.name_edit.text().strip()
        code = self.code_edit.text().strip().upper()
        if not name:
            self._show_error("Exam type name is required")
            return
        if not code:
            self._show_error("Exam type code is required")
            return

        service = self._service()
        try:
            order_text = self.order_edit.text().strip()
            display_order = int(order_text) if order_text else None
            service.update_exam_type(
                exam_type_id=self._selected_id,
                name=name,
                code=code,
                description=self.desc_edit.text().strip() or None,
                max_marks=self.max_marks_spin.value(),
                weightage=self.weightage_spin.value(),
                display_order=display_order,
                is_active=self.active_check.isChecked(),
            )
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._refresh_list()

    def _deactivate(self) -> None:
        if self._selected_id is None:
            self._show_error("Select an exam type")
            return
        self._clear_error()
        service = self._service()
        try:
            service.deactivate_exam_type(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._reset_form()
        self._refresh_list()

    def _activate(self) -> None:
        if self._selected_id is None:
            self._show_error("Select an exam type")
            return
        self._clear_error()
        service = self._service()
        try:
            service.activate_exam_type(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._refresh_list()

    def _delete(self) -> None:
        if self._selected_id is None:
            self._show_error("Select an exam type")
            return
        self._clear_error()
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to permanently delete this exam type?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        service = self._service()
        try:
            service.session.delete(service.repo.get(self._selected_id))
            service.session.commit()
        except Exception as exc:
            service.session.rollback()
            self._show_error(f"Delete failed: {exc}")
            return
        finally:
            service.session.close()
        self._reset_form()
        self._refresh_list()

    def _move_up(self) -> None:
        if self._selected_id is None:
            self._show_error("Select an exam type")
            return
        self._clear_error()
        service = self._service()
        try:
            exam_types = service.list_exam_types()
            idx = next((i for i, et in enumerate(exam_types) if et.id == self._selected_id), -1)
            if idx <= 0:
                self._show_error("Already at top")
                return
            exam_types[idx], exam_types[idx - 1] = exam_types[idx - 1], exam_types[idx]
            service.reorder_exam_types([(et.id, et.display_order) for et in exam_types])
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._refresh_list()

    def _move_down(self) -> None:
        if self._selected_id is None:
            self._show_error("Select an exam type")
            return
        self._clear_error()
        service = self._service()
        try:
            exam_types = service.list_exam_types()
            idx = next((i for i, et in enumerate(exam_types) if et.id == self._selected_id), -1)
            if idx < 0 or idx >= len(exam_types) - 1:
                self._show_error("Already at bottom")
                return
            exam_types[idx], exam_types[idx + 1] = exam_types[idx + 1], exam_types[idx]
            service.reorder_exam_types([(et.id, et.display_order) for et in exam_types])
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._refresh_list()

    # --- Bulk import & export ---

    def _bulk_import(self) -> None:
        dialog = ExamTypeImportDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        entries = dialog.get_entries()
        if not entries:
            self._show_error("No exam type data provided")
            return

        service = self._service()
        try:
            created, errors = service.bulk_import(entries, dialog.skip_duplicates_enabled())
            if errors:
                self._show_error(f"Imported {len(created)}; issues: {'; '.join(errors[:5])}")
            else:
                self._show_error(f"Imported {len(created)} exam types")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._reset_form()
        self._refresh_list()

    def _export_csv(self) -> None:
        service = self._service()
        try:
            csv_content = service.export_exam_types_to_csv()
            path, _ = QFileDialog.getSaveFileName(self, "Export Exam Types", "exam_types.csv", "CSV Files (*.csv)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(csv_content)
                self._show_error(f"Exported to {path}")
        except Exception as exc:
            service.session.rollback()
            self._show_error(f"Export failed: {exc}")
            return
        finally:
            service.session.close()