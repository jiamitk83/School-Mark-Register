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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import SubjectService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    TEXT_SECONDARY, PRIMARY_DARK, FONT_HEADING,
)


class SubjectImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Subjects")
        self.resize(600, 450)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        info = QLabel("Paste subject data (Name,Code,Description,Active) or load CSV:")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("English,ENG,English Language,Yes\nMathematics,MATH,Mathematics,Yes\nScience,SCI,Science,Yes")
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

        self.preview_table = QTableWidget(0, 5)
        self.preview_table.setHorizontalHeaderLabels(["Name", "Code", "Description", "Active", "Status"])
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
            while len(parts) < 4:
                parts.append("")
            for j, val in enumerate(parts[:4]):
                self.preview_table.setItem(i, j, QTableWidgetItem(val))
            self.preview_table.setItem(i, 4, QTableWidgetItem("Ready"))

    def get_subjects(self) -> list[dict]:
        text = self.text_edit.toPlainText()
        subjects = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            while len(parts) < 4:
                parts.append("")
            name, code, desc, active = parts[0], parts[1], parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else "Yes"
            if name:
                subjects.append({
                    "name": name,
                    "code": code.upper(),
                    "description": desc if desc else None,
                    "is_active": active.lower() in ("yes", "true", "1", "y")
                })
        return subjects

    def skip_duplicates_enabled(self) -> bool:
        return self.skip_duplicates.isChecked()


class SubjectView(QWidget):
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

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Subject Master")
        title.setStyleSheet(f"font-size: {FONT_HEADING}; font-weight: 600; color: {PRIMARY_DARK};")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.add_subject_btn = QPushButton("Add Subject")
        self.add_subject_btn.clicked.connect(self._add_subject)
        header_layout.addWidget(self.add_subject_btn)
        layout.addLayout(header_layout)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        
        # Tab 1: Subject List
        self.list_tab = self._create_list_tab()
        self.tabs.addTab(self.list_tab, "Subject List")
        
        # Tab 2: Single Entry
        self.single_tab = self._create_single_entry_tab()
        self.tabs.addTab(self.single_tab, "Single Entry")
        
        # Tab 3: Bulk Creation
        self.bulk_tab = self._create_bulk_tab()
        self.tabs.addTab(self.bulk_tab, "Bulk Creation")
        
        # Tab 4: Class & Section Mapping
        self.mapping_tab = self._create_mapping_tab()
        self.tabs.addTab(self.mapping_tab, "Class & Section Mapping")

        layout.addWidget(self.tabs, 1)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

    def _create_list_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)

        # Search/filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(SPACING_MD)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search subjects...")
        self.search_edit.textChanged.connect(self._filter_list)
        self.active_filter = QComboBox()
        self.active_filter.addItems(["All", "Active", "Inactive"])
        self.active_filter.currentTextChanged.connect(self._filter_list)
        filter_layout.addWidget(QLabel("Search:"))
        filter_layout.addWidget(self.search_edit, 1)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.active_filter)
        filter_layout.addStretch()
        
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_csv)
        filter_layout.addWidget(export_btn)
        layout.addLayout(filter_layout)

        # Table
        self.list_table = QTableWidget(0, 6)
        self.list_table.setHorizontalHeaderLabels(["ID", "Name", "Code", "Description", "Active", "Mappings"])
        self.list_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_table.setAlternatingRowColors(True)
        self.list_table.verticalHeader().setVisible(False)
        self.list_table.itemSelectionChanged.connect(self._on_list_selection)
        self.list_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.list_table, 1)

        # List actions
        list_btns = QHBoxLayout()
        list_btns.setSpacing(SPACING_MD)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_subject)
        self.activate_btn = QPushButton("Activate")
        self.activate_btn.clicked.connect(self._activate_subject)
        self.deactivate_btn = QPushButton("Deactivate")
        self.deactivate_btn.clicked.connect(self._deactivate_subject)
        self.mapping_btn = QPushButton("Manage Mappings")
        self.mapping_btn.clicked.connect(self._open_mapping_tab)
        for b in (self.edit_btn, self.activate_btn, self.deactivate_btn, self.mapping_btn):
            list_btns.addWidget(b)
        list_btns.addStretch()
        layout.addLayout(list_btns)

        return tab

    def _create_single_entry_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(SPACING_LG)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        form = QGroupBox("Subject Details")
        form_layout = QGridLayout(form)
        form_layout.setSpacing(SPACING_MD)
        form_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Subject name, e.g. English")
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Subject code, e.g. ENG")
        self.code_edit.setMaxLength(20)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description (optional)")
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(True)
        
        self.save_subject_btn = QPushButton("Save Subject")
        self.save_subject_btn.clicked.connect(self._save_subject)

        form_layout.addWidget(QLabel("Name *"), 0, 0)
        form_layout.addWidget(self.name_edit, 0, 1)
        form_layout.addWidget(QLabel("Code *"), 1, 0)
        form_layout.addWidget(self.code_edit, 1, 1)
        form_layout.addWidget(QLabel("Description"), 2, 0)
        form_layout.addWidget(self.desc_edit, 2, 1)
        form_layout.addWidget(self.active_check, 3, 0, 1, 2)
        form_layout.addWidget(self.save_subject_btn, 4, 0, 1, 2)
        form_layout.setColumnStretch(1, 1)

        layout.addWidget(form)
        layout.addStretch()

        return tab

    def _create_bulk_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(SPACING_LG)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        info = QLabel("Import multiple subjects from CSV or paste data:")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.bulk_import_btn = QPushButton("Import Subjects")
        self.bulk_import_btn.clicked.connect(self._bulk_import)
        layout.addWidget(self.bulk_import_btn)

        export_layout = QHBoxLayout()
        self.export_subjects_btn = QPushButton("Export Subjects CSV")
        self.export_subjects_btn.clicked.connect(self._export_subjects_csv)
        self.export_mappings_btn = QPushButton("Export Mappings CSV")
        self.export_mappings_btn.clicked.connect(self._export_mappings_csv)
        export_layout.addWidget(self.export_subjects_btn)
        export_layout.addWidget(self.export_mappings_btn)
        export_layout.addStretch()
        layout.addLayout(export_layout)

        layout.addStretch()
        return tab

    def _create_mapping_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)

        # --- Cascade Selectors ---
        selectors_group = QGroupBox("Cascade Assignment: Class → Section → Subject")
        selectors_layout = QGridLayout(selectors_group)
        selectors_layout.setSpacing(SPACING_MD)
        selectors_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        # Class selector
        self.cascade_class_combo = QComboBox()
        self.cascade_class_combo.setMinimumWidth(300)
        self.cascade_class_combo.currentIndexChanged.connect(self._on_cascade_class_changed)
        selectors_layout.addWidget(QLabel("Class:"), 0, 0)
        selectors_layout.addWidget(self.cascade_class_combo, 0, 1)

        # Section selector
        self.cascade_section_combo = QComboBox()
        self.cascade_section_combo.setMinimumWidth(300)
        self.cascade_section_combo.currentIndexChanged.connect(self._on_cascade_section_changed)
        self.cascade_section_combo.setEnabled(False)
        selectors_layout.addWidget(QLabel("Section:"), 1, 0)
        selectors_layout.addWidget(self.cascade_section_combo, 1, 1)

        # Subject selector
        self.cascade_subject_combo = QComboBox()
        self.cascade_subject_combo.setMinimumWidth(300)
        self.cascade_subject_combo.setEnabled(False)
        self.cascade_subject_combo.currentIndexChanged.connect(self._on_cascade_subject_changed)
        selectors_layout.addWidget(QLabel("Subject:"), 2, 0)
        selectors_layout.addWidget(self.cascade_subject_combo, 2, 1)

        # Assign button
        self.cascade_assign_btn = QPushButton("Assign Subject")
        self.cascade_assign_btn.setEnabled(False)
        self.cascade_assign_btn.clicked.connect(self._cascade_assign_subject)
        selectors_layout.addWidget(self.cascade_assign_btn, 3, 0, 1, 2)

        layout.addWidget(selectors_group)

        # --- Existing Assignments Table ---
        assignments_group = QGroupBox("Current Assignments for Selected Class & Section")
        assignments_layout = QVBoxLayout(assignments_group)
        assignments_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)
        assignments_layout.setSpacing(SPACING_MD)

        self.cascade_assignments_table = QTableWidget(0, 4)
        self.cascade_assignments_table.setHorizontalHeaderLabels(["Subject", "Code", "Active", "Action"])
        self.cascade_assignments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cascade_assignments_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cascade_assignments_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cascade_assignments_table.setAlternatingRowColors(True)
        self.cascade_assignments_table.verticalHeader().setVisible(False)
        self.cascade_assignments_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        assignments_layout.addWidget(self.cascade_assignments_table, 1)
        layout.addWidget(assignments_group, 1)

        return tab

    # --- Cascade Event Handlers ---

    def _on_cascade_class_changed(self) -> None:
        """Called when class selection changes. Load sections for the selected class."""
        self.cascade_section_combo.setEnabled(False)
        self.cascade_section_combo.clear()
        self.cascade_subject_combo.setEnabled(False)
        self.cascade_subject_combo.clear()
        self.cascade_assign_btn.setEnabled(False)
        self.cascade_assignments_table.setRowCount(0)

        class_id = self.cascade_class_combo.currentData()
        if class_id is None:
            return

        # Load sections for this class
        section_service = self._section_service()
        try:
            sections = section_service.list_active_sections(class_id)
        finally:
            section_service.session.close()

        if not sections:
            self.cascade_section_combo.addItem("No sections available", None)
            return

        self.cascade_section_combo.addItem("Select Section", None)
        for sec in sections:
            self.cascade_section_combo.addItem(sec.name, sec.id)
        self.cascade_section_combo.setEnabled(True)

    def _on_cascade_section_changed(self) -> None:
        """Called when section selection changes. Load available subjects."""
        self.cascade_subject_combo.setEnabled(False)
        self.cascade_subject_combo.clear()
        self.cascade_assign_btn.setEnabled(False)
        self.cascade_assignments_table.setRowCount(0)

        section_id = self.cascade_section_combo.currentData()
        class_id = self.cascade_class_combo.currentData()

        if section_id is None or class_id is None:
            return

        # Refresh assignments for this class+section (always, even if no available subjects)
        self._refresh_cascade_assignments(class_id, section_id)

        # Load available subjects for this class+section
        service = self._service()
        try:
            subjects = service.get_available_subjects_for_section(class_id, section_id)
        finally:
            service.session.close()

        if not subjects:
            self.cascade_subject_combo.addItem("All subjects already assigned", None)
            return

        self.cascade_subject_combo.addItem("Select Subject", None)
        for subj in subjects:
            self.cascade_subject_combo.addItem(f"{subj.name} ({subj.code})", subj.id)
        self.cascade_subject_combo.setEnabled(True)

    def _on_cascade_subject_changed(self) -> None:
        """Called when subject selection changes. Enable assign button if valid subject selected."""
        subject_id = self.cascade_subject_combo.currentData()
        self.cascade_assign_btn.setEnabled(subject_id is not None)

    def _refresh_cascade_assignments(self, class_id: int, section_id: int) -> None:
        """Refresh the assignments table for the selected class+section."""
        service = self._service()
        try:
            assignments = service.get_assignments_for_class_section(class_id, section_id)
        finally:
            service.session.close()

        self.cascade_assignments_table.setRowCount(len(assignments))
        for row, mapping in enumerate(assignments):
            values = [
                mapping.subject.name,
                mapping.subject.code,
                "Yes" if mapping.is_active else "No",
                ""
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if val == "Yes":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    else:
                        item.setForeground(Qt.GlobalColor.darkRed)
                self.cascade_assignments_table.setItem(row, col, item)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setProperty("mapping_id", mapping.id)
            remove_btn.setProperty("subject_id", mapping.subject_id)
            remove_btn.setProperty("section_id", mapping.section_id)
            try:
                remove_btn.clicked.disconnect(self._cascade_remove_assignment)
            except TypeError:
                pass
            remove_btn.clicked.connect(self._cascade_remove_assignment)
            self.cascade_assignments_table.setCellWidget(row, 3, remove_btn)

    def _cascade_assign_subject(self) -> None:
        """Assign the selected subject to the selected class+section."""
        class_id = self.cascade_class_combo.currentData()
        section_id = self.cascade_section_combo.currentData()
        subject_id = self.cascade_subject_combo.currentData()

        if not all([class_id, section_id, subject_id]):
            self._show_error("Select class, section, and subject")
            return

        service = self._service()
        try:
            service.assign_subject_to_section(subject_id, class_id, section_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        # Refresh subjects list and assignments
        self._on_cascade_section_changed()
        self._show_error("Subject assigned successfully")

    def _cascade_remove_assignment(self) -> None:
        """Remove a subject from a section."""
        btn = self.sender()
        if not btn:
            return
        subject_id = btn.property("subject_id")
        section_id = btn.property("section_id")

        if subject_id is None or section_id is None:
            return

        service = self._service()
        try:
            service.remove_subject_from_section(subject_id, section_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        # Refresh
        self._on_cascade_section_changed()
        self._show_error("Assignment removed")

    def _service(self) -> SubjectService:
        return SubjectService(self.session_factory())

    def _class_service(self):
        from services import ClassService
        return ClassService(self.session_factory())

    def _section_service(self):
        from services import SectionService
        return SectionService(self.session_factory())

    def _clear_error(self) -> None:
        clear_error_label(self.error_label)
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

    def _load_subjects(self) -> None:
        service = self._service()
        try:
            subjects = service.list_subjects()
        finally:
            service.session.close()

    def _load_classes_for_mapping(self) -> None:
        service = self._class_service()
        try:
            classes = service.list_active_classes()
            self._cached_classes = classes
            # Also populate cascade class combo
            self.cascade_class_combo.clear()
            self.cascade_class_combo.addItem("Select Class", None)
            for cls in classes:
                self.cascade_class_combo.addItem(cls.name, cls.id)
        finally:
            service.session.close()

    def refresh(self) -> None:
        self._clear_error()
        self._selected_id = None
        self._load_subjects()
        self._load_classes_for_mapping()
        self._refresh_list()
        self._refresh_single_entry()

    def _refresh_list(self) -> None:
        self._clear_error()
        self._selected_id = None
        self.list_table.setRowCount(0)
        
        service = self._service()
        try:
            subjects = service.list_subjects()
        finally:
            service.session.close()
        
        search_text = self.search_edit.text().lower() if hasattr(self, 'search_edit') else ""
        status_filter = self.active_filter.currentText() if hasattr(self, 'active_filter') else "All"
        
        for subj in subjects:
            if search_text and search_text not in subj.name.lower() and search_text not in subj.code.lower():
                continue
            if status_filter == "Active" and not subj.is_active:
                continue
            if status_filter == "Inactive" and subj.is_active:
                continue
            
            row = self.list_table.rowCount()
            self.list_table.insertRow(row)
            service = self._service()
            class_count = len(service.get_active_class_mappings(subj.id))
            section_count = len(service.get_active_section_mappings(subj.id))
            total_mappings = class_count + section_count
            service.session.close()
            
            values = [
                str(subj.id),
                subj.name,
                subj.code,
                subj.description or "",
                "Yes" if subj.is_active else "No",
                str(total_mappings)
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, subj.id)
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if val == "Yes":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    else:
                        item.setForeground(Qt.GlobalColor.darkRed)
                self.list_table.setItem(row, col, item)
        self.list_table.clearSelection()
        # Restore selection if we have a selected_id
        if self._selected_id is not None:
            for row in range(self.list_table.rowCount()):
                item = self.list_table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == self._selected_id:
                    self.list_table.selectRow(row)
                    break

    def _refresh_single_entry(self) -> None:
        pass  # Form is cleared on selection change

    def _filter_list(self) -> None:
        self._refresh_list()

    def _on_list_selection(self) -> None:
        self._clear_error()
        self._selected_id = None
        row = self.list_table.currentRow()
        if row < 0:
            return
        id_item = self.list_table.item(row, 0)
        if id_item is None:
            return
        self._selected_id = int(id_item.text())
        self._open_mapping_tab()
        
        # Populate single entry form
        service = self._service()
        try:
            subj = service.get_subject(self._selected_id)
        finally:
            service.session.close()
        if subj:
            self.name_edit.setText(subj.name)
            self.code_edit.setText(subj.code)
            self.desc_edit.setText(subj.description or "")
            self.active_check.setChecked(subj.is_active)

    def _filter_list(self) -> None:
        self._refresh_list()

    def _add_subject(self) -> None:
        self.tabs.setCurrentWidget(self.single_tab)
        self._clear_form()

    def _clear_form(self) -> None:
        self.name_edit.clear()
        self.code_edit.clear()
        self.desc_edit.clear()
        self.active_check.setChecked(True)
        self._selected_id = None
        self.list_table.clearSelection()

    def _save_subject(self) -> None:
        self._clear_error()
        name = self.name_edit.text().strip()
        code = self.code_edit.text().strip().upper()
        desc = self.desc_edit.text().strip()
        is_active = self.active_check.isChecked()
        
        if not name:
            self._show_error("Subject name is required")
            return
        if not code:
            self._show_error("Subject code is required")
            return
        
        was_new = self._selected_id is None
        service = self._service()
        try:
            if was_new:
                subj = service.add_subject(name, code, desc or None, self.active_check.isChecked())
                self._selected_id = subj.id
            else:
                service.update_subject(self._selected_id, name, code, desc or None, self.active_check.isChecked())
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        
        # Refresh list but preserve selection
        self._refresh_list()
        # Update mapping tab if needed
        if was_new:
            self._load_subjects()
        self._refresh_mapping_tab()

    def _edit_subject(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a subject to edit")
            return
        self.tabs.setCurrentWidget(self.single_tab)

    def _activate_subject(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a subject")
            return
        self._clear_error()
        service = self._service()
        try:
            service.activate_subject(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _deactivate_subject(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a subject")
            return
        self._clear_error()
        service = self._service()
        try:
            service.deactivate_subject(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _bulk_import(self) -> None:
        dialog = SubjectImportDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        subjects = dialog.get_subjects()
        if not subjects:
            self._show_error("No subjects provided")
            return
        service = self._service()
        try:
            created, errors = service.bulk_import_subjects(subjects, dialog.skip_duplicates_enabled())
            if errors:
                self._show_error(f"Imported {len(created)}; issues: {'; '.join(errors)}")
            else:
                self._show_error(f"Imported {len(created)} subjects")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
        finally:
            service.session.close()
        self.refresh()

    def _open_mapping_tab(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a subject")
            return
        self.tabs.setCurrentWidget(self.mapping_tab)

    def _export_csv(self) -> None:
        service = self._service()
        try:
            csv_content = service.export_subjects_to_csv()
            path, _ = QFileDialog.getSaveFileName(self, "Export Subjects", "subjects.csv", "CSV Files (*.csv)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(csv_content)
                self._show_error(f"Exported to {path}")
        except Exception as exc:
            service.session.rollback()
            self._show_error(f"Export failed: {exc}")
        finally:
            service.session.close()

    def _export_subjects_csv(self) -> None:
        self._export_csv()

    def _export_mappings_csv(self) -> None:
        service = self._service()
        try:
            csv_content = service.export_mappings_to_csv()
            path, _ = QFileDialog.getSaveFileName(self, "Export Mappings", "subject_mappings.csv", "CSV Files (*.csv)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(csv_content)
                self._show_error(f"Exported to {path}")
        except Exception as exc:
            service.session.rollback()
            self._show_error(f"Export failed: {exc}")
        finally:
            service.session.close()

    