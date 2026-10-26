from __future__ import annotations

import csv
from io import StringIO

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import ComponentMarksService
from ui.styles import (
    set_primary_button, set_secondary_button,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    TEXT_SECONDARY,
)


class _ResultTableModel(QStandardItemModel):
    """Model backing the Half Yearly results table."""

    HEADERS = ["Roll No", "Admission No", "Student Name", "Max Marks", "Obtained", "Percentage", "Grade", "Status"]

    def __init__(self):
        super().__init__()
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)


class HalfYearlyResultView(QWidget):
    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_session_id: int | None = None
        self._selected_class_id: int | None = None
        self._selected_section_id: int | None = None
        self._selected_subject_id: int | None = None
        self._all_results: list[dict] = []
        self._build_ui()
        self._load_sessions()

    # ------------------------------------------------------------------ services

    def _component_service(self):
        return ComponentMarksService(self.session_factory())

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
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
        title = QLabel("Half Yearly Results")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #1e3a5f;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.export_csv_btn = QPushButton("Export CSV")
        set_secondary_button(self.export_csv_btn, True)
        self.export_csv_btn.clicked.connect(self._export_csv)
        header_layout.addWidget(self.export_csv_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        # Search
        search_layout = QHBoxLayout()
        search_layout.setSpacing(SPACING_MD)
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name, roll number, or admission number...")
        self.search_edit.setMinimumWidth(300)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Cascade selectors
        cascade_group = QGroupBox("Selection: Session → Class → Section → Subject")
        cascade_layout = QHBoxLayout(cascade_group)
        cascade_layout.setSpacing(SPACING_MD)
        cascade_layout.setContentsMargins(SPACING_MD, SPACING_MD + SPACING_SM, SPACING_MD, SPACING_MD)

        session_layout = QVBoxLayout()
        session_layout.setSpacing(SPACING_XS)
        session_layout.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        session_layout.addWidget(self.session_combo)
        cascade_layout.addLayout(session_layout)

        class_layout = QVBoxLayout()
        class_layout.setSpacing(SPACING_XS)
        class_layout.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(200)
        self.class_combo.setEnabled(False)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)
        class_layout.addWidget(self.class_combo)
        cascade_layout.addLayout(class_layout)

        section_layout = QVBoxLayout()
        section_layout.setSpacing(SPACING_XS)
        section_layout.addWidget(QLabel("Section:"))
        self.section_combo = QComboBox()
        self.section_combo.setMinimumWidth(200)
        self.section_combo.setEnabled(False)
        self.section_combo.currentIndexChanged.connect(self._on_section_changed)
        section_layout.addWidget(self.section_combo)
        cascade_layout.addLayout(section_layout)

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

        # Info label
        self.info_label = QLabel("Select Session, Class, Section, and Subject to view Half Yearly results")
        self.info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-style: italic;")
        layout.addWidget(self.info_label)

        # Results table
        self.result_table = QTableView()
        self.result_table.setModel(_ResultTableModel())
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setSortingEnabled(True)

        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setHighlightSections(True)

        # Sort proxy for filtering
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.result_table.model())
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.result_table.setModel(self.proxy_model)

        layout.addWidget(self.result_table, 1)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ------------------------------------------------------------------ helpers

    def _clear_error(self) -> None:
        self.error_label.setProperty("error", False)
        self.error_label.setText("")
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        from ui.styles import set_error_label
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

    def _on_search_changed(self) -> None:
        pattern = self.search_edit.text()
        if not pattern:
            self.proxy_model.setFilterKeyColumn(-1)
            self.proxy_model.setFilterRegExp("")
        else:
            self.proxy_model.setFilterKeyColumn(-1)
            self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
            self.proxy_model.setFilterRegExp(pattern)

    # ------------------------------------------------------------------ cascade

    def _load_sessions(self) -> None:
        service = self._component_service()
        try:
            sessions = service.session_repo.list_all()
            current = service.session_repo.current()
            self.session_combo.blockSignals(True)
            self.session_combo.clear()
            if not sessions:
                self.session_combo.addItem("No sessions available", None)
            else:
                for sess in sessions:
                    label = sess.name
                    if sess.is_current:
                        label += " (Current)"
                    self.session_combo.addItem(label, sess.id)
                self.session_combo.addItem("All Sessions", -1)
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
        self._selected_subject_id = None
        self.class_combo.setEnabled(False)
        self.section_combo.setEnabled(False)
        self.subject_combo.setEnabled(False)
        self.class_combo.clear()
        self.section_combo.clear()
        self.subject_combo.clear()
        self._clear_table()

        idx = self.session_combo.currentIndex()
        if idx < 0:
            return
        session_id = self.session_combo.itemData(idx)
        if session_id is None:
            return
        if session_id == -1:
            return  # "All Sessions" - not supported for now
        self._selected_session_id = session_id

        service = self._component_service()
        try:
            classes = service.class_repo.list_all()
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
        self._selected_section_id = None
        self._selected_subject_id = None
        self.section_combo.setEnabled(False)
        self.subject_combo.setEnabled(False)
        self.section_combo.clear()
        self.subject_combo.clear()
        self._clear_table()

        idx = self.class_combo.currentIndex()
        if idx < 0:
            return
        class_id = self.class_combo.itemData(idx)
        if class_id is None:
            return
        self._selected_class_id = class_id

        service = self._component_service()
        try:
            sections = service.section_repo.list_by_class(class_id)
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
        self._selected_subject_id = None
        self.subject_combo.setEnabled(False)
        self.subject_combo.clear()
        self._clear_table()

        idx = self.section_combo.currentIndex()
        if idx < 0:
            return
        section_id = self.section_combo.itemData(idx)
        if section_id is None:
            return
        self._selected_section_id = section_id

        service = self._component_service()
        try:
            subjects = service.get_half_yearly_subjects_for_class_section(
                self._selected_class_id, section_id
            )
            self.subject_combo.blockSignals(True)
            self.subject_combo.clear()
            if not subjects:
                self.subject_combo.addItem("No subjects with Half Yearly components", None)
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
        self._clear_table()

        idx = self.subject_combo.currentIndex()
        if idx < 0:
            return
        subject_id = self.subject_combo.itemData(idx)
        if subject_id is None:
            return
        self._selected_subject_id = subject_id
        self._load_results()

    # ------------------------------------------------------------------ data

    def _clear_table(self) -> None:
        model = self.result_table.model()
        if isinstance(model, QSortFilterProxyModel):
            source = model.sourceModel()
            source.removeRows(0, source.rowCount())
        else:
            model.removeRows(0, model.rowCount())
        self.info_label.setText("Select Session, Class, Section, and Subject to view Half Yearly results")

    def _load_results(self) -> None:
        if None in (self._selected_session_id, self._selected_class_id, self._selected_section_id, self._selected_subject_id):
            return

        service = self._component_service()
        try:
            self._all_results = service.get_half_yearly_result_summary(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_subject_id,
            )
        except Exception as exc:
            self._show_error(f"Failed to load results: {exc}")
            return
        finally:
            service.session.close()

        self._populate_table()
        count = len(self._all_results)
        self.info_label.setText(f"Showing {count} student{'s' if count != 1 else ''} for Half Yearly result")

    def _populate_table(self) -> None:
        source_model = self.result_table.model()
        if isinstance(source_model, QSortFilterProxyModel):
            source_model = source_model.sourceModel()
        source_model.removeRows(0, source_model.rowCount())

        for row_data in self._all_results:
            row_items = [
                QStandardItem(row_data["roll_number"]),
                QStandardItem(row_data["admission_number"]),
                QStandardItem(row_data["name"]),
                QStandardItem(str(row_data["max_marks"])),
                QStandardItem(
                    str(row_data["obtained_marks"]) if row_data["obtained_marks"] is not None else ""
                ),
                QStandardItem(
                    f"{row_data['percentage']:.2f}" if row_data["percentage"] is not None else ""
                ),
                QStandardItem(row_data["grade"] if row_data["grade"] else ""),
                QStandardItem(row_data["status"]),
            ]
            for item in row_items:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            source_model.appendRow(row_items)

        # Apply coloring based on status
        for row in range(source_model.rowCount()):
            status_item = source_model.item(row, 7)
            if status_item:
                status = status_item.text()
                grade_item = source_model.item(row, 6)
                if status == "absent":
                    for col in range(source_model.columnCount()):
                        source_model.item(row, col).setForeground(Qt.GlobalColor.darkRed)
                elif status == "pending" or status == "locked":
                    for col in range(source_model.columnCount()):
                        source_model.item(row, col).setForeground(Qt.GlobalColor.gray)
                elif grade_item and grade_item.text():
                    if grade_item.text() in ("A1", "A2"):
                        for col in range(source_model.columnCount()):
                            source_model.item(row, col).setForeground(Qt.GlobalColor.darkGreen)
                    elif grade_item.text() in ("B1", "B2", "C1"):
                        for col in range(source_model.columnCount()):
                            source_model.item(row, col).setForeground(Qt.GlobalColor.darkBlue)
                    else:
                        for col in range(source_model.columnCount()):
                            source_model.item(row, col).setForeground(Qt.GlobalColor.darkYellow)

    def refresh(self) -> None:
        self._clear_error()
        self._clear_table()
        if self._selected_subject_id is not None:
            self._load_results()

    # ------------------------------------------------------------------ export

    def _export_csv(self) -> None:
        if self._selected_session_id is None or self._selected_class_id is None or self._selected_section_id is None or self._selected_subject_id is None:
            self._show_error("Select session, class, section, and subject first")
            return

        service = self._component_service()
        try:
            csv_content = service.export_half_yearly_results_to_csv(
                self._selected_session_id,
                self._selected_class_id,
                self._selected_section_id,
                self._selected_subject_id,
            )
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Half Yearly Results", "half_yearly_results.csv", "CSV Files (*.csv)"
            )
            if path:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(csv_content)
                self._show_error(f"Exported to {path}")
        except Exception as exc:
            service.session.rollback()
            self._show_error(f"Export failed: {exc}")
            return
        finally:
            service.session.close()
