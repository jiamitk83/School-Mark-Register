from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import ComponentMarksService, MarksService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    TEXT_SECONDARY,
)


class DraftRecoveryDialog(QDialog):
    def __init__(self, draft_vs_saved: dict, student_name: str, subject_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draft Recovery")
        self.resize(500, 350)
        self.draft_vs_saved = draft_vs_saved
        self._build_ui(student_name, subject_name)

    def _build_ui(self, student_name: str, subject_name: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        # Title
        title = QLabel(f"Recover Draft for {student_name} - {subject_name}")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1e3a5f;")
        layout.addWidget(title)

        info = QLabel("You have unsaved draft data. Choose how to proceed:")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Comparison table
        self.table = QTableWidget(3, 3)
        self.table.setHorizontalHeaderLabels(["Field", "Saved (Official)", "Draft (Unsaved)"])
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        draft = self.draft_vs_saved.get("draft")
        saved = self.draft_vs_saved.get("saved")

        rows_data = [
            ("Marks Obtained",
             str(saved.get("marks_obtained")) if saved and saved.get("marks_obtained") is not None else "—",
             str(draft.get("marks_obtained")) if draft and draft.get("marks_obtained") is not None else "—"),
            ("Status",
             saved.get("status", "—").capitalize() if saved else "—",
             draft.get("status", "—").capitalize() if draft else "—"),
            ("Max Marks",
             str(saved.get("max_marks")) if saved else "—",
             str(draft.get("max_marks")) if draft else "—"),
        ]

        for row_idx, (field, saved_val, draft_val) in enumerate(rows_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(field))
            self.table.setItem(row_idx, 1, QTableWidgetItem(saved_val))
            self.table.setItem(row_idx, 2, QTableWidgetItem(draft_val))

        layout.addWidget(self.table)

        # Options
        options_group = QGroupBox("Recovery Options")
        options_layout = QVBoxLayout(options_group)

        self.restore_btn = QPushButton("Restore Draft to Editing")
        self.restore_btn.setToolTip("Load draft values into the grid for further editing")
        set_primary_button(self.restore_btn, True)

        self.discard_btn = QPushButton("Discard Draft")
        self.discard_btn.setToolTip("Permanently delete the unsaved draft")
        set_danger_button(self.discard_btn, True)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Keep draft as-is, return to grid")

        for btn in (self.restore_btn, self.discard_btn, self.cancel_btn):
            options_layout.addWidget(btn)

        layout.addWidget(options_group)

        # Buttons
        buttons = QDialogButtonBox()
        buttons.addButton(self.restore_btn, QDialogButtonBox.ActionRole)
        buttons.addButton(self.discard_btn, QDialogButtonBox.DestructiveRole)
        buttons.addButton(self.cancel_btn, QDialogButtonBox.RejectRole)
        layout.addWidget(buttons)

        self.restore_btn.clicked.connect(lambda: self.done(1))
        self.discard_btn.clicked.connect(lambda: self.done(2))
        self.cancel_btn.clicked.connect(self.reject)

    def get_result(self) -> int:
        return self.result()


class MarksView(QWidget):
    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_session_id: int | None = None
        self._selected_class_id: int | None = None
        self._selected_section_id: int | None = None
        self._selected_exam_type_id: int | None = None
        self._selected_subject_id: int | None = None
        self._components: list = []  # List of (component_id, name, code, max_marks, display_order)
        self._component_marks_data: dict = {}  # (student_id, component_id) -> {marks_obtained, status, max_marks}
        self._build_ui()
        self._load_sessions()

    def _build_ui(self):
        # Create scroll area for the entire page
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(SPACING_LG)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Marks Entry")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #1e3a5f;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.save_all_btn = QPushButton("Save All")
        set_primary_button(self.save_all_btn, True)
        self.save_all_btn.clicked.connect(self._save_all)
        header_layout.addWidget(self.save_all_btn)

        self.save_draft_btn = QPushButton("Save Draft")
        set_secondary_button(self.save_draft_btn, True)
        self.save_draft_btn.clicked.connect(self._save_draft)
        header_layout.addWidget(self.save_draft_btn)

        self.lock_btn = QPushButton("Lock Marks")
        set_secondary_button(self.lock_btn, True)
        self.lock_btn.clicked.connect(self._lock_marks)
        header_layout.addWidget(self.lock_btn)

        self.unlock_btn = QPushButton("Unlock Marks")
        set_secondary_button(self.unlock_btn, True)
        self.unlock_btn.clicked.connect(self._unlock_marks)
        header_layout.addWidget(self.unlock_btn)

        self.promote_btn = QPushButton("Promote Drafts")
        set_secondary_button(self.promote_btn, True)
        self.promote_btn.clicked.connect(self._promote_drafts)
        header_layout.addWidget(self.promote_btn)

        self.recover_btn = QPushButton("Recover")
        set_secondary_button(self.recover_btn, True)
        self.recover_btn.clicked.connect(self._recover_drafts)
        header_layout.addWidget(self.recover_btn)

        self.discard_all_btn = QPushButton("Discard All Drafts")
        set_secondary_button(self.discard_all_btn, True)
        self.discard_all_btn.clicked.connect(self._discard_all_drafts)
        header_layout.addWidget(self.discard_all_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        # Student Search and Status Filters
        filter_group = QGroupBox("Search & Filters")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setSpacing(SPACING_MD)
        filter_layout.setContentsMargins(SPACING_MD, SPACING_MD + SPACING_SM, SPACING_MD, SPACING_MD)

        # Student Search
        search_layout = QVBoxLayout()
        search_layout.setSpacing(SPACING_XS)
        search_layout.addWidget(QLabel("Student Search:"))
        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Search by name or roll number...")
        self.student_search.setMinimumWidth(250)
        self.student_search.textChanged.connect(self._filter_students)
        search_layout.addWidget(self.student_search)
        filter_layout.addLayout(search_layout)

        # Status Filter
        status_layout = QVBoxLayout()
        status_layout.setSpacing(SPACING_XS)
        status_layout.addWidget(QLabel("Status Filter:"))
        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(150)
        self.status_filter.addItems(["All", "Pending", "Saved", "Absent", "Locked", "Draft"])
        self.status_filter.currentTextChanged.connect(self._filter_students)
        status_layout.addWidget(self.status_filter)
        filter_layout.addLayout(status_layout)

        filter_layout.addStretch()
        layout.addWidget(filter_group)

        # Cascade selectors: Session → Class → Section → Exam Type → Subject
        cascade_group = QGroupBox("Selection: Session → Class → Section → Exam Type → Subject")
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

        # Exam Type selector
        exam_layout = QVBoxLayout()
        exam_layout.setSpacing(SPACING_XS)
        exam_layout.addWidget(QLabel("Exam Type:"))
        self.exam_type_combo = QComboBox()
        self.exam_type_combo.setMinimumWidth(200)
        self.exam_type_combo.setEnabled(False)
        self.exam_type_combo.currentIndexChanged.connect(self._on_exam_type_changed)
        exam_layout.addWidget(self.exam_type_combo)
        cascade_layout.addLayout(exam_layout)

        # Subject selector
        subject_layout = QVBoxLayout()
        subject_layout.setSpacing(SPACING_XS)
        subject_layout.addWidget(QLabel("Subject:"))
        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(200)
        self.subject_combo.setEnabled(False)
        self.subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        subject_layout.addWidget(self.subject_combo)
        cascade_layout.addLayout(subject_layout)

        cascade_layout.addStretch()
        layout.addWidget(cascade_group)

        # Component marks grid
        self.grid_group = QGroupBox("Component Marks Entry")
        grid_layout = QVBoxLayout(self.grid_group)
        grid_layout.setSpacing(SPACING_MD)
        grid_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        # Info label
        self.grid_info = QLabel("Select Session, Class, Section, Exam Type, and Subject to load component marks grid")
        self.grid_info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-style: italic;")
        grid_layout.addWidget(self.grid_info)

        # Table for component marks entry
        self.marks_table = QTableWidget(0, 0)
        self.marks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.marks_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.marks_table.setAlternatingRowColors(True)
        self.marks_table.verticalHeader().setVisible(False)
        self.marks_table.itemChanged.connect(self._on_cell_changed)
        grid_layout.addWidget(self.marks_table, 1)

        layout.addWidget(self.grid_group, 1)

        # Detail Panel (hidden by default, shown on row selection)
        self.detail_panel = QGroupBox("Component Detail")
        self.detail_panel.setVisible(False)
        detail_layout = QFormLayout(self.detail_panel)
        detail_layout.setSpacing(SPACING_MD)
        detail_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.detail_student = QLabel("-")
        self.detail_component = QLabel("-")
        self.detail_max_marks = QLabel("-")
        self.detail_marks_obtained = QSpinBox()
        self.detail_marks_obtained.setRange(0, 999)
        self.detail_marks_obtained.setSpecialValueText("—")
        self.detail_marks_obtained.valueChanged.connect(self._on_detail_marks_changed)

        self.detail_status = QComboBox()
        self.detail_status.addItems(["pending", "absent", "saved", "locked"])
        self.detail_status.currentTextChanged.connect(self._on_detail_status_changed)

        self.detail_gk_grade = QLabel("-")
        self.detail_french_equiv = QLabel("-")

        detail_layout.addRow("Student:", self.detail_student)
        detail_layout.addRow("Component:", self.detail_component)
        detail_layout.addRow("Max Marks:", self.detail_max_marks)
        detail_layout.addRow("Marks Obtained:", self.detail_marks_obtained)
        detail_layout.addRow("Status:", self.detail_status)
        detail_layout.addRow("GK Grade:", self.detail_gk_grade)
        detail_layout.addRow("French Equiv (80):", self.detail_french_equiv)

        detail_btn_layout = QHBoxLayout()
        self.detail_save_btn = QPushButton("Save")
        set_primary_button(self.detail_save_btn, True)
        self.detail_save_btn.clicked.connect(self._save_detail)
        detail_btn_layout.addWidget(self.detail_save_btn)

        self.detail_absent_btn = QPushButton("Mark Absent")
        set_secondary_button(self.detail_absent_btn, True)
        self.detail_absent_btn.clicked.connect(self._mark_absent_detail)
        detail_btn_layout.addWidget(self.detail_absent_btn)

        self.detail_cancel_btn = QPushButton("Cancel")
        self.detail_cancel_btn.clicked.connect(self._hide_detail_panel)
        detail_btn_layout.addWidget(self.detail_cancel_btn)
        detail_layout.addRow("", detail_btn_layout)

        layout.addWidget(self.detail_panel)

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

    def _marks_service(self) -> MarksService:
        return MarksService(self.session_factory())

    def _component_service(self) -> ComponentMarksService:
        return ComponentMarksService(self.session_factory())

    def _session_service(self):
        from services import SessionService
        return SessionService(self.session_factory())

    def _class_service(self):
        from services import ClassService
        return ClassService(self.session_factory())

    def _section_service(self):
        from services import SectionService
        return SectionService(self.session_factory())

    def _exam_type_service(self):
        from services import ExamTypeService
        return ExamTypeService(self.session_factory())

    def _subject_service(self):
        from services import SubjectService
        return SubjectService(self.session_factory())

    # --- Error helpers ---

    def _clear_error(self) -> None:
        clear_error_label(self.error_label)
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

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
        self._selected_exam_type_id = None
        self._selected_subject_id = None
        self.class_combo.setEnabled(False)
        self.section_combo.setEnabled(False)
        self.exam_type_combo.setEnabled(False)
        self.subject_combo.setEnabled(False)
        self.class_combo.clear()
        self.section_combo.clear()
        self.exam_type_combo.clear()
        self.subject_combo.clear()
        self._clear_grid()

        idx = self.session_combo.currentIndex()
        if idx < 0:
            return
        session_id = self.session_combo.itemData(idx)
        if session_id is None:
            return
        self._selected_session_id = session_id

        # Load classes
        service = self._class_service()
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

    def _on_class_changed(self) -> None:
        self._clear_error()
        self._selected_class_id = None
        self._selected_section_id = None
        self._selected_exam_type_id = None
        self._selected_subject_id = None
        self.section_combo.setEnabled(False)
        self.exam_type_combo.setEnabled(False)
        self.subject_combo.setEnabled(False)
        self.section_combo.clear()
        self.exam_type_combo.clear()
        self.subject_combo.clear()
        self._clear_grid()

        idx = self.class_combo.currentIndex()
        if idx < 0:
            return
        class_id = self.class_combo.itemData(idx)
        if class_id is None:
            return
        self._selected_class_id = class_id

        # Load sections for this class
        service = self._section_service()
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
        self._selected_exam_type_id = None
        self._selected_subject_id = None
        self.exam_type_combo.setEnabled(False)
        self.subject_combo.setEnabled(False)
        self.exam_type_combo.clear()
        self.subject_combo.clear()
        self._clear_grid()

        idx = self.section_combo.currentIndex()
        if idx < 0:
            return
        section_id = self.section_combo.itemData(idx)
        if section_id is None:
            return
        self._selected_section_id = section_id

        # Load exam types
        service = self._exam_type_service()
        try:
            exam_types = service.list_exam_types()
            self.exam_type_combo.blockSignals(True)
            self.exam_type_combo.clear()
            if not exam_types:
                self.exam_type_combo.addItem("No exam types available", None)
            else:
                self.exam_type_combo.addItem("Select Exam Type", None)
                for et in exam_types:
                    self.exam_type_combo.addItem(f"{et.name} ({et.code})", et.id)
            self.exam_type_combo.blockSignals(False)
            self.exam_type_combo.setEnabled(True)
        finally:
            service.session.close()

    def _on_exam_type_changed(self) -> None:
        self._clear_error()
        self._selected_exam_type_id = None
        self._selected_subject_id = None
        self.subject_combo.setEnabled(False)
        self.subject_combo.clear()
        self._clear_grid()

        idx = self.exam_type_combo.currentIndex()
        if idx < 0:
            return
        exam_type_id = self.exam_type_combo.itemData(idx)
        if exam_type_id is None:
            return
        self._selected_exam_type_id = exam_type_id

        # Load subjects for this class+section
        service = self._subject_service()
        try:
            subjects = service.get_subjects_for_class_section(self._selected_class_id, self._selected_section_id)
            self.subject_combo.blockSignals(True)
            self.subject_combo.clear()
            if not subjects:
                self.subject_combo.addItem("No subjects mapped to this class/section", None)
            else:
                self.subject_combo.addItem("Select Subject", None)
                for subj in subjects:
                    self.subject_combo.addItem(subj.name, subj.id)
            self.subject_combo.blockSignals(False)
            self.subject_combo.setEnabled(True)
        finally:
            service.session.close()

    def _on_subject_changed(self) -> None:
        self._clear_error()
        self._selected_subject_id = None
        self._clear_grid()

        idx = self.subject_combo.currentIndex()
        if idx < 0:
            return
        subject_id = self.subject_combo.itemData(idx)
        if subject_id is None:
            return
        self._selected_subject_id = subject_id
        self._load_component_grid()

    def _clear_grid(self) -> None:
        self.marks_table.setRowCount(0)
        self.marks_table.setColumnCount(0)
        self.grid_info.setText("Select Session, Class, Section, Exam Type, and Subject to load component marks grid")
        self._component_marks_data.clear()
        self._components = []

    def _load_component_grid(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            return

        service = self._component_service()
        try:
            # Get students in this section
            students = service.student_repo.list_active_by_section(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id
            )
            # Get components for this exam type and subject
            self._components = service.component_repo.get_by_exam_type_and_subject(
                self._selected_exam_type_id, self._selected_subject_id
            )

            # Auto-populate Half Yearly PT1/5 marks from saved PT1 marks
            # This ensures the grid shows converted marks even if PT1 marks were saved
            # before this feature was implemented
            hy_exam_type = service.exam_type_repo.get_by_name("Half Yearly")
            if hy_exam_type and self._selected_exam_type_id == hy_exam_type.id:
                service.auto_populate_half_yearly_pt1_from_pt1(
                    self._selected_session_id,
                    self._selected_class_id,
                    self._selected_section_id,
                    self._selected_subject_id,
                )

            # Get existing component marks
            existing_marks = service.list_component_marks_for_entry(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id
            )
            # Build marks lookup: (student_id, component_id) -> marks
            marks_lookup = {(m.student_id, m.component_id): m for m in existing_marks}
        finally:
            service.session.close()

        if not students:
            self.grid_info.setText("No students in this section")
            return
        if not self._components:
            self.grid_info.setText("No components configured for this exam type and subject. Configure in Exam Configuration.")
            return

        # Build table columns: Roll No, Student Name, then one column per component
        num_component_cols = len(self._components)
        total_cols = 2 + num_component_cols  # Roll No, Student Name, then components
        self.marks_table.setColumnCount(total_cols)

        # Set headers
        headers = ["Roll No", "Student Name"]
        for comp in self._components:
            headers.append(f"{comp.name} ({comp.code})\nMax: {comp.max_marks}")
        self.marks_table.setHorizontalHeaderLabels(headers)

        self.marks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.marks_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.marks_table.setAlternatingRowColors(True)
        self.marks_table.verticalHeader().setVisible(False)
        self.marks_table.itemChanged.connect(self._on_cell_changed)
        self.marks_table.itemSelectionChanged.connect(self._on_selection_changed)

        header = self.marks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, total_cols):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # Load existing component marks
        service = self._component_service()
        try:
            existing_marks = service.list_component_marks_for_entry(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id
            )
            marks_lookup = {(m.student_id, m.component_id): m for m in existing_marks}
        finally:
            service.session.close()

        # Build grid: one row per student
        self.marks_table.blockSignals(True)
        self._component_marks_data.clear()
        row = 0
        for student in students:
            self.marks_table.insertRow(row)
            # Roll No
            item = QTableWidgetItem(student.roll_number)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.marks_table.setItem(row, 0, item)
            # Student Name
            item = QTableWidgetItem(student.name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.marks_table.setItem(row, 1, item)

            # Component columns
            for comp_idx, comp in enumerate(self._components):
                col = 2 + comp_idx
                key = (student.id, comp.id)
                marks_entry = marks_lookup.get(key)

                if marks_entry and marks_entry.marks_obtained is not None:
                    marks_text = str(marks_entry.marks_obtained)
                else:
                    marks_text = ""

                item = QTableWidgetItem(marks_text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, (student.id, comp.id))

                # Check if locked
                if marks_entry and marks_entry.status == "locked":
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(Qt.GlobalColor.lightGray)

                # Check if auto-calculated (converted) from PT1
                if marks_entry and marks_entry.status == "converted":
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(QColor("#FFF9C4"))

                self.marks_table.setItem(row, col, item)

                # Store marks data
                self._component_marks_data[key] = {
                    "student_id": student.id,
                    "component_id": comp.id,
                    "marks_obtained": marks_entry.marks_obtained if marks_entry else None,
                    "status": marks_entry.status if marks_entry else "pending",
                    "max_marks": comp.max_marks,
                }
            row += 1

        self.grid_info.setText(f"Loaded {len(students)} students × {len(self._components)} components = {row} entries")
        self.marks_table.blockSignals(False)

    # --- Event handlers ---

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        if item.column() < 2:  # Only component columns are editable (col >= 2)
            return

        row = item.row()
        key = item.data(Qt.ItemDataRole.UserRole)
        if key is None:
            return

        student_id, component_id = key
        if key not in self._component_marks_data:
            return
        text = item.text().strip()
        if not text:
            self._component_marks_data[key]["marks_obtained"] = None
            self._component_marks_data[key]["status"] = "pending"
            return

        try:
            marks = int(text)
            max_marks = self._component_marks_data[key].get("max_marks", 100)
            if marks < 0 or marks > max_marks:
                self._show_error(f"Marks must be between 0 and {max_marks}")
                old_val = self._component_marks_data[key].get("marks_obtained")
                item.setText(str(old_val) if old_val is not None else "")
                return
            self._component_marks_data[key]["marks_obtained"] = marks
            self._component_marks_data[key]["status"] = "saved"
            
            # Auto-save draft after cell change
            self._schedule_autosave()
        except ValueError:
            self._show_error("Invalid marks value")
            old_val = self._component_marks_data[key].get("marks_obtained")
            item.setText(str(old_val) if old_val is not None else "")

    def _on_selection_changed(self) -> None:
        """Handle row selection to show detail panel."""
        selected_rows = self.marks_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self._show_detail_panel(row)
        else:
            self._hide_detail_panel()

    def _schedule_autosave(self) -> None:
        """Schedule an auto-save of drafts after a short delay."""
        if not hasattr(self, '_autosave_timer'):
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setSingleShot(True)
            self._autosave_timer.timeout.connect(self._autosave_drafts)
        self._autosave_timer.start(2000)  # 2 second delay

    def _autosave_drafts(self) -> None:
        """Auto-save current drafts to database."""
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            return

        drafts_data = []
        for key, data in self._component_marks_data.items():
            if data["marks_obtained"] is not None or data["status"] != "pending":
                drafts_data.append({
                    "student_id": data["student_id"],
                    "component_id": data["component_id"],
                    "marks_obtained": data["marks_obtained"],
                    "status": data["status"] if data["marks_obtained"] is not None else "pending",
                })

        if not drafts_data:
            return

        service = self._component_service()
        try:
            for draft_data in drafts_data:
                try:
                    service.save_component_marks(
                        draft_data["student_id"],
                        draft_data["component_id"],
                        draft_data["marks_obtained"],
                        draft_data["status"],
                    )
                except ValueError:
                    pass  # Silently ignore autosave errors
        finally:
            service.session.close()

    # --- CRUD operations ---

    def _save_all(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        marks_data = []
        for key, data in self._component_marks_data.items():
            if data["marks_obtained"] is not None or data["status"] != "pending":
                marks_data.append({
                    "student_id": data["student_id"],
                    "component_id": data["component_id"],
                    "marks_obtained": data["marks_obtained"],
                    "status": data["status"],
                })

        if not marks_data:
            self._show_error("No marks to save")
            return

        service = self._component_service()
        try:
            created, errors = service.bulk_save_component_marks(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id,
                marks_data,
            )
            if errors:
                self._show_error(f"Saved {len(created)}; errors: {'; '.join(errors[:5])}")
            else:
                self._show_error(f"Successfully saved {len(created)} component marks entries")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._load_component_grid()

    def _lock_marks(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        service = self._component_service()
        try:
            count = service.lock_component_marks(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id,
            )
            self._show_error(f"Locked {count} component marks entries")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._load_component_grid()

    def _unlock_marks(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        service = self._component_service()
        try:
            count = service.unlock_component_marks(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id,
            )
            self._show_error(f"Unlocked {count} component marks entries")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._load_component_grid()

    def _save_draft(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        drafts_data = []
        for key, data in self._component_marks_data.items():
            if data["marks_obtained"] is not None or data["status"] != "pending":
                drafts_data.append({
                    "student_id": data["student_id"],
                    "component_id": data["component_id"],
                    "marks_obtained": data["marks_obtained"],
                    "status": data["status"] if data["marks_obtained"] is not None else "pending",
                })

        if not drafts_data:
            self._show_error("No data to save as draft")
            return

        service = self._component_service()
        try:
            errors = []
            for draft_data in drafts_data:
                try:
                    service.save_component_marks(
                        draft_data["student_id"],
                        draft_data["component_id"],
                        draft_data["marks_obtained"],
                        draft_data["status"],
                    )
                except ValueError as exc:
                    errors.append(f"Row {draft_data['student_id']}-{draft_data['component_id']}: {exc}")
            if errors:
                self._show_error(f"Draft saved with errors: {'; '.join(errors[:5])}")
            else:
                self._show_error(f"Successfully saved {len(drafts_data)} draft entries")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._load_component_grid()

    def _promote_drafts(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        # Check if there are any drafts for this subject
        service = self._component_service()
        try:
            drafts = service.list_component_marks_for_entry(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id
            )
            # Filter to drafts for the selected subject
            subject_drafts = [d for d in drafts if d.subject_id == self._selected_subject_id]
        finally:
            service.session.close()

        if not subject_drafts:
            self._show_error("No drafts to promote for this subject")
            return

        reply = QMessageBox.question(
            self, "Promote Drafts",
            f"Promote {len(subject_drafts)} draft entries to official marks?\nThis will overwrite any existing official marks.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        service = self._component_service()
        try:
            created, errors = service.promote_drafts_to_marks(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id,
            )
            if errors:
                self._show_error(f"Promoted {len(created)}; errors: {'; '.join(errors[:5])}")
            else:
                self._show_error(f"Successfully promoted {len(created)} draft entries to official marks")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._load_component_grid()

    def _recover_drafts(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        service = self._component_service()
        try:
            drafts = service.list_component_marks_for_entry(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id
            )
            # Filter to drafts for the selected subject
            subject_drafts = [d for d in drafts if d.subject_id == self._selected_subject_id]
            marks = service.list_component_marks_for_entry(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id
            )
        finally:
            service.session.close()

        if not subject_drafts:
            self._show_error("No drafts to recover")
            return

        # Show recovery dialog for each draft that differs from saved
        recovered = 0
        for draft in subject_drafts:
            key = (draft.student_id, draft.component_id)
            saved = next((m for m in marks if m.student_id == draft.student_id and m.component_id == draft.component_id), None)
            
            # Only show recovery if draft differs from saved
            draft_val = draft.marks_obtained
            saved_val = saved.marks_obtained if saved else None
            draft_status = draft.status
            saved_status = saved.status if saved else None
            
            if draft_val == saved_val and draft_status == saved_status:
                continue
            
            # Get student and component names
            service2 = self._component_service()
            try:
                student_obj = service2.student_repo.get(draft.student_id)
                component_obj = service2.component_repo.get(draft.component_id)
            finally:
                service2.session.close()
            
            if not student_obj or not component_obj:
                continue
            
            draft_vs_saved = {
                "draft": {
                    "marks_obtained": draft.marks_obtained,
                    "status": draft.status,
                    "max_marks": draft.max_marks,
                } if draft else None,
                "saved": {
                    "marks_obtained": saved.marks_obtained if saved else None,
                    "status": saved.status if saved else None,
                    "max_marks": saved.max_marks if saved else None,
                } if saved else None,
            }
            
            dialog = DraftRecoveryDialog(draft_vs_saved, student_obj.name, component_obj.name, self)
            result = dialog.exec()
            
            if result == 1:  # Restore
                # Load draft into component_marks_data for editing
                key = (draft.student_id, draft.component_id)
                self._component_marks_data[key] = {
                    "student_id": draft.student_id,
                    "component_id": draft.component_id,
                    "marks_obtained": draft.marks_obtained,
                    "status": draft.status,
                    "max_marks": draft.max_marks,
                }
                recovered += 1
            elif result == 2:  # Discard
                service3 = self._component_service()
                try:
                    service3.discard_component_marks(draft.student_id, draft.component_id)
                finally:
                    service3.session.close()
        
        if recovered > 0:
            self._show_error(f"Restored {recovered} draft entries to editing grid")
            self._load_component_grid()
        else:
            self._show_error("No drafts required recovery")

    def _discard_all_drafts(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_exam_type_id, self._selected_subject_id):
            self._show_error("Select Session, Class, Section, Exam Type, and Subject first")
            return

        reply = QMessageBox.question(
            self, "Discard All Drafts",
            "Permanently delete all draft entries for this subject in this selection?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        service = self._component_service()
        try:
            count = service.discard_all_drafts(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_exam_type_id,
            )
            self._show_error(f"Discarded {count} draft entries")
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()

        self._load_component_grid()

    # --- Filter and Detail Panel Handlers ---

    def _filter_students(self) -> None:
        """Filter the grid based on student search text and status filter."""
        search_text = self.student_search.text().lower().strip()
        status_filter = self.status_filter.currentText()

        for row in range(self.marks_table.rowCount()):
            show_row = True

            # Student search filter
            if search_text:
                student_name_item = self.marks_table.item(row, 1)
                roll_no_item = self.marks_table.item(row, 0)
                student_name = student_name_item.text().lower() if student_name_item else ""
                roll_no = roll_no_item.text().lower() if roll_no_item else ""
                if search_text not in student_name and search_text not in roll_no:
                    show_row = False

            # Status filter — check if any component cell in this row matches the status
            if show_row and status_filter != "All":
                found_match = False
                for col in range(2, self.marks_table.columnCount()):
                    item = self.marks_table.item(row, col)
                    if item:
                        key = item.data(Qt.ItemDataRole.UserRole)
                        if key:
                            status = self._component_marks_data.get(key, {}).get("status", "pending")
                            if status_filter == status.capitalize():
                                found_match = True
                                break
                if not found_match:
                    show_row = False

            self.marks_table.setRowHidden(row, not show_row)

    def refresh(self) -> None:
        self._clear_error()
        if self._selected_session_id and self._selected_class_id and self._selected_section_id and self._selected_exam_type_id and self._selected_subject_id:
            self._load_component_grid()

    def _show_detail_panel(self, row: int) -> None:
        """Show the detail panel for the selected row."""
        key = None
        for col in range(2, self.marks_table.columnCount()):
            item = self.marks_table.item(row, col)
            if item:
                k = item.data(Qt.ItemDataRole.UserRole)
                if k:
                    key = k
                    break
        if not key:
            return

        student_id, component_id = key
        data = self._component_marks_data.get(key)
        if not data:
            return

        # Get student and component info
        service = self._component_service()
        try:
            student = service.student_repo.get(student_id)
            component = service.component_repo.get(component_id)
        finally:
            service.session.close()

        if not student or not component:
            return

        self._current_detail_key = key
        self.detail_student.setText(f"{student.name} (Roll: {student.roll_number})")
        self.detail_component.setText(f"{component.name} ({component.code})")
        self.detail_max_marks.setText(str(component.max_marks))

        marks_obtained = data.get("marks_obtained")
        self.detail_marks_obtained.setValue(marks_obtained if marks_obtained is not None else 0)
        self.detail_marks_obtained.setMaximum(data.get("max_marks", 100))

        status = data.get("status", "pending")
        status_idx = self.detail_status.findText(status)
        if status_idx >= 0:
            self.detail_status.setCurrentIndex(status_idx)

        # Show GK grade if applicable
        component_service = self._component_service()
        try:
            comp_marks = component_service.get_component_marks_by_student_component(student_id, component_id)
            if comp_marks and comp_marks.component and comp_marks.component.subject:
                subject_name = comp_marks.component.subject.name.upper()
                if subject_name == "GK" and comp_marks.marks_obtained is not None:
                    max_for_percentage = 25 if component.code in ("PT", "PT1", "PT2") else 40
                    if max_for_percentage > 0:
                        percentage = round((comp_marks.marks_obtained / max_for_percentage) * 100)
                    else:
                        percentage = 0

                    if percentage >= 91:
                        gk_grade = "A1"
                    elif percentage >= 81:
                        gk_grade = "A2"
                    elif percentage >= 71:
                        gk_grade = "B1"
                    elif percentage >= 61:
                        gk_grade = "B2"
                    elif percentage >= 51:
                        gk_grade = "C1"
                    elif percentage >= 41:
                        gk_grade = "C2"
                    elif percentage >= 33:
                        gk_grade = "D"
                    else:
                        gk_grade = "E"
                    self.detail_gk_grade.setText(gk_grade)
                else:
                    self.detail_gk_grade.setText("-")
        finally:
            pass

        # French equivalent
        if component.subject and component.subject.name.upper() == "FRENCH" and component.code == "WE":
            marks = self._component_marks_data.get((student_id, component_id))
            if marks and marks.get("marks_obtained") is not None:
                raw = marks["marks_obtained"]
                if raw <= 40:
                    equiv = raw * 2
                else:
                    equiv = raw
                self.detail_french_equiv.setText(str(equiv))
        else:
            self.detail_french_equiv.setText("-")

        self.detail_panel.setVisible(True)

    def _hide_detail_panel(self) -> None:
        """Hide the detail panel."""
        self.detail_panel.setVisible(False)
        self._current_detail_key = None

    def _on_detail_marks_changed(self, value: int) -> None:
        """Handle marks change in detail panel."""
        if not hasattr(self, '_current_detail_key') or not self._current_detail_key:
            return
        key = self._current_detail_key
        if key in self._component_marks_data:
            self._component_marks_data[key]["marks_obtained"] = value
            self._component_marks_data[key]["status"] = "saved"

    def _on_detail_status_changed(self, status: str) -> None:
        """Handle status change in detail panel."""
        if not hasattr(self, '_current_detail_key') or not self._current_detail_key:
            return
        key = self._current_detail_key
        if key in self._component_marks_data:
            self._component_marks_data[key]["status"] = status

    def _save_detail(self) -> None:
        """Save the detail panel changes."""
        if not hasattr(self, '_current_detail_key') or not self._current_detail_key:
            return
        key = self._current_detail_key
        if key not in self._component_marks_data:
            self._hide_detail_panel()
            return

        marks_obtained = self.detail_marks_obtained.value()
        status = self.detail_status.currentText()

        self._component_marks_data[key]["marks_obtained"] = marks_obtained
        self._component_marks_data[key]["status"] = status

        service = self._component_service()
        try:
            service.save_component_marks(
                key[0],
                key[1],
                marks_obtained,
                status,
            )
        finally:
            service.session.close()

        self._hide_detail_panel()
        self._load_component_grid()

    def _mark_absent_detail(self) -> None:
        """Mark the selected component as absent."""
        if not hasattr(self, '_current_detail_key') or not self._current_detail_key:
            return
        key = self._current_detail_key
        if key in self._component_marks_data:
            self._component_marks_data[key]["marks_obtained"] = None
            self._component_marks_data[key]["status"] = "absent"
            self._load_component_grid()
        self._hide_detail_panel()

