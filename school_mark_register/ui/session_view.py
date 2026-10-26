from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import SessionService
from ui.styles import (
    set_primary_button, set_secondary_button, set_danger_button,
    clear_error_label, set_error_label,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
)


class SessionView(QWidget):
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

        # Form card
        form = QGroupBox("Academic Session")
        form_layout = QGridLayout(form)
        form_layout.setSpacing(SPACING_MD)
        form_layout.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Session name, e.g. 2026/2027")
        self.start_edit = QDateEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDate(QDate.currentDate())
        self.end_edit = QDateEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDate(QDate.currentDate().addYears(1))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "archived"])
        self.current_check = QCheckBox("Set as current session")
        self.add_btn = QPushButton("Add Session")
        set_primary_button(self.add_btn, True)
        self.add_btn.clicked.connect(self._add)

        form_layout.addWidget(QLabel("Name"), 0, 0)
        form_layout.addWidget(self.name_edit, 0, 1)
        form_layout.addWidget(QLabel("Start Date"), 1, 0)
        form_layout.addWidget(self.start_edit, 1, 1)
        form_layout.addWidget(QLabel("End Date"), 2, 0)
        form_layout.addWidget(self.end_edit, 2, 1)
        form_layout.addWidget(QLabel("Status"), 3, 0)
        form_layout.addWidget(self.status_combo, 3, 1)
        form_layout.addWidget(self.current_check, 4, 0, 1, 2)
        form_layout.addWidget(self.add_btn, 5, 0, 1, 2)
        form_layout.setColumnStretch(1, 1)

        layout.addWidget(form)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Start", "End", "Status", "Current", "Created"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(SPACING_MD)
        self.save_btn = QPushButton("Save Changes")
        set_secondary_button(self.save_btn, True)
        self.save_btn.clicked.connect(self._save)
        self.set_current_btn = QPushButton("Set Current")
        set_secondary_button(self.set_current_btn, True)
        self.set_current_btn.clicked.connect(self._set_current)
        self.archive_btn = QPushButton("Archive")
        set_secondary_button(self.archive_btn, True)
        self.archive_btn.clicked.connect(self._archive)
        self.delete_btn = QPushButton("Delete")
        set_danger_button(self.delete_btn, True)
        self.delete_btn.clicked.connect(self._delete)
        self.refresh_btn = QPushButton("Refresh")
        set_secondary_button(self.refresh_btn, True)
        self.refresh_btn.clicked.connect(self.refresh)
        for b in (self.save_btn, self.set_current_btn, self.archive_btn, self.delete_btn, self.refresh_btn):
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

    def _service(self) -> SessionService:
        return SessionService(self.session_factory())

    def _clear_error(self) -> None:
        clear_error_label(self.error_label)
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        set_error_label(self.error_label, message)
        self.error_label.setVisible(True)

    def _reset_form(self) -> None:
        self.name_edit.clear()
        self.start_edit.setDate(QDate.currentDate())
        self.end_edit.setDate(QDate.currentDate().addYears(1))
        self.status_combo.setCurrentIndex(0)
        self.current_check.setChecked(False)

    def refresh(self) -> None:
        self._clear_error()
        self._selected_id = None
        self._reset_form()
        self.table.setRowCount(0)
        service = self._service()
        try:
            sessions = service.list_sessions()
        finally:
            service.session.close()
        for row_index, session_obj in enumerate(sessions):
            self.table.insertRow(row_index)
            values = [
                str(session_obj.id),
                session_obj.name,
                str(session_obj.start_date),
                str(session_obj.end_date),
                session_obj.status,
                "Yes" if session_obj.is_current else "No",
                str(session_obj.created_at)[:10] if session_obj.created_at else "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, session_obj.id)
                if column == 5 and value == "Yes":
                    item.setForeground(Qt.GlobalColor.white)
                    item.setBackground(Qt.GlobalColor.darkBlue)
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
            session_obj = service.get_session(self._selected_id)
        finally:
            service.session.close()
        if session_obj is None:
            return
        self.name_edit.setText(session_obj.name)
        self.start_edit.setDate(
            QDate(session_obj.start_date.year, session_obj.start_date.month, session_obj.start_date.day)
        )
        self.end_edit.setDate(
            QDate(session_obj.end_date.year, session_obj.end_date.month, session_obj.end_date.day)
        )
        self.status_combo.setCurrentText(session_obj.status)
        self.current_check.setChecked(bool(session_obj.is_current))

    def _add(self) -> None:
        self._clear_error()
        service = self._service()
        try:
            service.add_session(
                self.name_edit.text(),
                self.start_edit.date().toPython(),
                self.end_edit.date().toPython(),
                self.status_combo.currentText(),
                self.current_check.isChecked(),
            )
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.name_edit.clear()
        self.current_check.setChecked(False)
        self.refresh()

    def _save(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a session to edit")
            return
        self._clear_error()
        service = self._service()
        try:
            service.update_session(
                self._selected_id,
                self.name_edit.text(),
                self.start_edit.date().toPython(),
                self.end_edit.date().toPython(),
                self.status_combo.currentText(),
            )
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _set_current(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a session")
            return
        self._clear_error()
        service = self._service()
        try:
            service.set_current(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _archive(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a session")
            return
        self._clear_error()
        service = self._service()
        try:
            service.archive_session(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()

    def _delete(self) -> None:
        if self._selected_id is None:
            self._show_error("Select a session")
            return
        self._clear_error()
        service = self._service()
        try:
            service.delete_session(self._selected_id)
        except ValueError as exc:
            service.session.rollback()
            self._show_error(str(exc))
            return
        finally:
            service.session.close()
        self.refresh()