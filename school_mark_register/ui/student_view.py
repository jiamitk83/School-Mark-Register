from __future__ import annotations

import csv
from datetime import date
from io import StringIO

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import StudentService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    TEXT_SECONDARY,
)


class StudentBulkImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import Students")
        self.resize(600, 450)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        info = QLabel("Paste student data (Name,Roll Number,Father's Name,Mother's Name,Gender,DOB,Phone,Email,Address) or load CSV:")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Alice Johnson,R001,John Johnson,Mary Johnson,F,,1234567890,alice@example.com,123 Main St\n"
            "Bob Smith,R002,Robert Smith,Sarah Smith,M,,0987654321,bob@example.com,456 Oak Ave"
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
            ["Name", "Roll No", "Father's Name", "Mother's Name", "Gender", "Status"]
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
            roll = parts[1] if len(parts) > 1 else ""
            father = parts[2] if len(parts) > 2 else ""
            mother = parts[3] if len(parts) > 3 else ""
            gender = parts[4] if len(parts) > 4 else ""
            self.preview_table.setItem(i, 0, QTableWidgetItem(name))
            self.preview_table.setItem(i, 1, QTableWidgetItem(roll))
            self.preview_table.setItem(i, 2, QTableWidgetItem(father))
            self.preview_table.setItem(i, 3, QTableWidgetItem(mother))
            self.preview_table.setItem(i, 4, QTableWidgetItem(gender))
            self.preview_table.setItem(i, 5, QTableWidgetItem("Ready" if name and roll else "Missing data"))

    def get_entries(self) -> list[dict]:
        text = self.text_edit.toPlainText()
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            while len(parts) < 9:
                parts.append("")
            entry = {
                "name": parts[0],
                "roll_number": parts[1],
                "father_name": parts[2] if parts[2] else None,
                "mother_name": parts[3] if parts[3] else None,
                "gender": parts[4] if parts[4] else None,
                "dob": None,
                "phone": parts[6] if parts[6] else None,
                "email": parts[7] if parts[7] else None,
                "address": parts[8] if parts[8] else None,
            }
            entries.append(entry)
        return entries

    def skip_duplicates_enabled(self) -> bool:
        return self.skip_duplicates.isChecked()


class StudentView(QWidget):
    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_id: int | None = None
        self._selected_session_id: int | None = None
        self._selected_class_id: int | None = None
        self._selected_section_id: int | None = None
        self._build_ui()
        self._load_sessions()
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
        title = QLabel("Student Master")
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

        # Cascade selectors: Session → Class → Section
        cascade_group = QGroupBox("Cascade Selection: Session → Class → Section")
        cascade_layout = QHBoxLayout(cascade_group)
        cascade_layout.setSpacing(SPACING_MD)
        cascade_layout.setContentsMargins(SPACING_MD, SPACING_MD + SPACING_SM, SPACING_MD, SPACING_MD)

        # Session selector
        session_layout = QVBoxLayout()
        session_layout.setSpacing(SPACING_XS)
        session_layout.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        session_layout.addWidget(self.session_combo)
        cascade_layout.addLayout(session_layout)

        # Class selector
        class_layout = QVBoxLayout()
        class_layout.setSpacing(SPACING_XS)
        class_layout.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(200)
        self.class_combo.setEnabled(False)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)
        class_layout.addWidget(self.class_combo)
        cascade_layout.addLayout(class_layout)

        # Section selector
        section_layout = QVBoxLayout()
        section_layout.setSpacing(SPACING_XS)
        section_layout.addWidget(QLabel("Section:"))
        self.section_combo = QComboBox()
        self.section_combo.setMinimumWidth(200)
        self.section_combo.setEnabled(False)
        self.section_combo.currentIndexChanged.connect(self._on_section_changed)
        section_layout.addWidget(self.section_combo)
        cascade_layout.addLayout(section_layout)

        cascade_layout.addStretch()
        layout.addWidget(cascade_group)

        # Student form
        self.form_group = QGroupBox("Student Details")
        form_layout = QFormLayout(self.form_group)
        form_layout.setSpacing(SPACING_MD)
        form_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Full name")
        self.name_edit.setMinimumWidth(300)

        self.roll_edit = QLineEdit()
        self.roll_edit.setPlaceholderText("Roll number")
        self.roll_edit.setMinimumWidth(150)

        self.admission_edit = QLineEdit()
        self.admission_edit.setPlaceholderText("Auto-generated (read-only)")
        self.admission_edit.setReadOnly(True)
        self.admission_edit.setDisabled(True)

        self.father_edit = QLineEdit()
        self.father_edit.setPlaceholderText("Father's name")
        self.father_edit.setMinimumWidth(300)

        self.mother_edit = QLineEdit()
        self.mother_edit.setPlaceholderText("Mother's name")
        self.mother_edit.setMinimumWidth(300)

        self.dob_edit = QDateEdit()
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setDate(QDate.currentDate())
        self.dob_edit.setMinimumWidth(150)

        self.gender_combo = QComboBox()
        self.gender_combo.setMinimumWidth(150)
        self.gender_combo.addItem("Select Gender", None)
        self.gender_combo.addItem("Male", "Male")
        self.gender_combo.addItem("Female", "Female")
        self.gender_combo.addItem("Other", "Other")

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone number")
        self.phone_edit.setMinimumWidth(200)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email address")
        self.email_edit.setMinimumWidth(300)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Residential address")
        self.address_edit.setMinimumWidth(400)

        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)

        form_layout.addRow("Name *", self.name_edit)
        form_layout.addRow("Roll No *", self.roll_edit)
        form_layout.addRow("Admission No", self.admission_edit)
        form_layout.addRow("Father's Name", self.father_edit)
        form_layout.addRow("Mother's Name", self.mother_edit)
        form_layout.addRow("DOB", self.dob_edit)
        form_layout.addRow("Gender", self.gender_combo)
        form_layout.addRow("Phone", self.phone_edit)
        form_layout.addRow("Email", self.email_edit)
        form_layout.addRow("Address", self.address_edit)
        form_layout.addRow("", self.active_check)

        # Form buttons
        form_btn_layout = QHBoxLayout()
        form_btn_layout.setSpacing(SPACING_MD)
        self.add_btn = QPushButton("Add Student")
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

        # Student table
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Admission No", "Roll No", "Name", "Father", "Gender", "Phone", "DOB", "Active"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
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
        self.refresh_btn = QPushButton("Refresh List")
        set_secondary_button(self.refresh_btn, True)
        self.refresh_btn.clicked.connect(self._refresh_list)
        for b in (self.deactivate_btn, self.activate_btn, self.delete_btn, self.refresh_btn):
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

    def _service(self) -> StudentService:
        return StudentService(self.session_factory())

    def _session_service(self):
        from services import SessionService
        return SessionService(self.session_factory())

    def _class_service(self):
        from services import ClassService
        return ClassService(self.session_factory())

    def _section_service(self):
        from services import SectionService
        return SectionService(self.session_factory())

    # --- Error helpers ---

    def _clear_error(self) -> None:
        clear_error_label(self.error_label)
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

    def _reset_form(self) -> None:
        self.name_edit.clear()
        self.roll_edit.clear()
        self.admission_edit.clear()
        self.father_edit.clear()
        self.mother_edit.clear()
        self.dob_edit.setDate(QDate.currentDate())
        self.gender_combo.setCurrentIndex(0)
        self.phone_edit.clear()
        self.email_edit.clear()
        self.address_edit.clear()
        self.active_check.setChecked(True)
        self._selected_id = None

    # --- Cascade loading ---

    def _load_sessions(self) -> None:
        service = self._session_service()
        try:
            sessions = service.list_sessions()
            self.session_combo.blockSignals(True)
            self.session_combo.clear()
            current = None
            if not sessions:
                self.session_combo.addItem("No sessions available", None)
            else:
                current = service.repo.current()
                for sess in sessions:
                    label = sess.name
                    if sess.is_current:
                        label += " (Current)"
                    self.session_combo.addItem(label, sess.id)
            self.session_combo.blockSignals(False)
            if current:
                idx = self.session_combo.findData(current.id)
                if idx >= 0:
                    self.session_combo.setCurrentIndex(idx)
                    self._on_session_changed()
        finally:
            service.session.close()

    def _on_session_changed(self) -> None:
        self._clear_error()
        self._selected_session_id = None
        self._selected_class_id = None
        self._selected_section_id = None
        self.class_combo.setEnabled(False)
        self.section_combo.setEnabled(False)
        self.class_combo.clear()
        self.section_combo.clear()
        self._reset_form()

        idx = self.session_combo.currentIndex()
        if idx < 0:
            return
        session_id = self.session_combo.itemData(idx)
        if session_id is None:
            return
        self._selected_session_id = session_id

        # Load classes
        from services import ClassService
        service = ClassService(self.session_factory())
        try:
            classes = service.list_classes()
            self.class_combo.blockSignals(True)
            self.class_combo.clear()
            if not classes:
                self.class_combo.addItem("No classes available", None)
            else:
                self.class_combo.addItem("Select Class", None)
                for cls in classes:
                    self.class_combo.addItem(cls.name, cls.id)
            self.class_combo.blockSignals(False)
            self.class_combo.setEnabled(True)
        finally:
            service.session.close()

        self.refresh()

    def _on_class_changed(self) -> None:
        self._clear_error()
        self._selected_class_id = None
        self._selected_section_id = None
        self.section_combo.setEnabled(False)
        self.section_combo.clear()
        self._reset_form()

        idx = self.class_combo.currentIndex()
        if idx < 0:
            return
        class_id = self.class_combo.itemData(idx)
        if class_id is None:
            return
        self._selected_class_id = class_id

        # Load sections for this class
        from services import SectionService
        service = SectionService(self.session_factory())
        try:
            sections = service.list_sections(class_id)
            self.section_combo.blockSignals(True)
            self.section_combo.clear()
            if not sections:
                self.section_combo.addItem("No sections available", None)
            else:
                self.section_combo.addItem("Select Section", None)
                for sec in sections:
                    self.section_combo.addItem(sec.name, sec.id)
            self.section_combo.blockSignals(False)
            self.section_combo.setEnabled(True)
        finally:
            service.session.close()

    def _on_section_changed(self) -> None:
        self._clear_error()
        self._selected_section_id = None
        self._reset_form()

        idx = self.section_combo.currentIndex()
        if idx < 0:
            return
        section_id = self.section_combo.itemData(idx)
        if section_id is None:
            return
        self._selected_section_id = section_id
        self._refresh_list()

    # --- Data loading ---

    def refresh(self) -> None:
        self._clear_error()
        self._reset_form()
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._clear_error()
        self._selected_id = None
        self.table.setRowCount(0)

        if self._selected_session_id is None or self._selected_class_id is None or self._selected_section_id is None:
            return

        service = self._service()
        try:
            students = service.list_students(
                self._selected_session_id, self._selected_class_id, self._selected_section_id
            )
        finally:
            service.session.close()

        for row_index, stu in enumerate(students):
            self.table.insertRow(row_index)
            values = [
                str(stu.id),
                stu.admission_number,
                stu.roll_number,
                stu.name,
                stu.father_name or "",
                stu.gender or "",
                stu.phone or "",
                str(stu.dob) if stu.dob else "",
                "Yes" if stu.is_active else "No",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, stu.id)
                if col == 8:
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
            stu = service.get_student(self._selected_id)
        finally:
            service.session.close()
        if stu is None:
            return

        self.admission_edit.setText(stu.admission_number or "")
        self.roll_edit.setText(stu.roll_number or "")
        self.name_edit.setText(stu.name or "")
        self.father_edit.setText(stu.father_name or "")
        self.mother_edit.setText(stu.mother_name or "")
        if stu.dob:
            self.dob_edit.setDate(QDate(stu.dob.year, stu.dob.month, stu.dob.day))
        else:
            self.dob_edit.setDate(QDate.currentDate())
        gender_idx = self.gender_combo.findData(stu.gender)
        self.gender_combo.setCurrentIndex(gender_idx if gender_idx >= 0 else 0)
        self.phone_edit.setText(stu.phone or "")
        self.email_edit.setText(stu.email or "")
        self.address_edit.setText(stu.address or "")
        self.active_check.setChecked(stu.is_active)

    # --- CRUD operations ---

    def _can_add_student(self) -> bool:
        if self._selected_session_id is None or self._selected_class_id is None or self._selected_section_id is None:
            self._show_error("Select session, class, and section first")
            return False
        return True

    def _add(self) -> None:
        if not self._can_add_student():
            return
        self._clear_error()
        name = self.name_edit.text().strip()
        roll_number = self.roll_edit.text().strip()
        if not name:
            self._show_error("Student name is required")
            return
        if not roll_number:
            self._show_error("Roll number is required")
            return

        service = self._service()
        try:
            service.add_student(
                session_id=self._selected_session_id,
                class_id=self._selected_class_id,
                section_id=self._selected_section_id,
                name=name,
                roll_number=roll_number,
                father_name=self.father_edit.text().strip() or None,
                mother_name=self.mother_edit.text().strip() or None,
                dob=self.dob_edit.date().toPython() if self.dob_edit.date().isValid() else None,
                gender=self.gender_combo.currentData() or None,
                phone=self.phone_edit.text().strip() or None,
                email=self.email_edit.text().strip() or None,
                address=self.address_edit.text().strip() or None,
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
            self._show_error("Select a student to edit")
            return
        self._clear_error()
        name = self.name_edit.text().strip()
        roll_number = self.roll_edit.text().strip()
        if not name:
            self._show_error("Student name is required")
            return
        if not roll_number:
            self._show_error("Roll number is required")
            return

        service = self._service()
        try:
            service.update_student(
                student_id=self._selected_id,
                name=name,
                roll_number=roll_number,
                father_name=self.father_edit.text().strip() or None,
                mother_name=self.mother_edit.text().strip() or None,
                dob=self.dob_edit.date().toPython() if self.dob_edit.date().isValid() else None,
                gender=self.gender_combo.currentData() or None,
                phone=self.phone_edit.text().strip() or None,
                email=self.email_edit.text().strip() or None,
                address=self.address_edit.text().strip() or None,
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
            self._show_error("Select a student")
            return
        self._clear_error()
        service = self._service()
        try:
            service.deactivate_student(self._selected_id)
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
            self._show_error("Select a student")
            return
        self._clear_error()
        service = self._service()
        try:
            service.activate_student(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self._refresh_list()

    def _delete(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a student")
            return
        self._clear_error()
        service = self._service()
        try:
            stu = service.get_student(self._selected_id)
            if stu is None:
                self._show_error("Student not found")
                return
            # Check for academic records referencing this student
            from models import AcademicRecord
            records = service.session.query(AcademicRecord).filter_by(
                session_id=stu.session_id,
                class_id=stu.class_id,
                section_id=stu.section_id,
                student_name=stu.name
            ).first()
            if records:
                self._show_error("Cannot delete: student has academic records. Deactivate instead.")
                return
            reply = QMessageBox.question(
                self, "Confirm Delete",
                "Are you sure you want to permanently delete this student?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            service.session.delete(stu)
            service.session.commit()
        except Exception as exc:
            service.session.rollback()
            self._show_error(f"Delete failed: {exc}")
            return
        finally:
            service.session.close()
        self._reset_form()
        self._refresh_list()

    # --- Bulk import & export ---

    def _bulk_import(self) -> None:
        if self._selected_session_id is None or self._selected_class_id is None or self._selected_section_id is None:
            self._show_error("Select session, class, and section first")
            return

        dialog = StudentBulkImportDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        entries = dialog.get_entries()
        if not entries:
            self._show_error("No student data provided")
            return

        service = self._service()
        try:
            created, errors = service.bulk_import(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                entries,
                skip_duplicates=dialog.skip_duplicates_enabled(),
            )
            if errors:
                self._show_error(f"Imported {len(created)}; issues: {'; '.join(errors[:5])}")
            else:
                self._show_error(f"Imported {len(created)} students")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._reset_form()
        self._refresh_list()

    def _export_csv(self) -> None:
        if self._selected_session_id is None or self._selected_class_id is None or self._selected_section_id is None:
            self._show_error("Select session, class, and section first")
            return

        service = self._service()
        try:
            csv_content = service.export_students_to_csv(
                self._selected_session_id, self._selected_class_id, self._selected_section_id
            )
            path, _ = QFileDialog.getSaveFileName(self, "Export Students", "students.csv", "CSV Files (*.csv)")
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
