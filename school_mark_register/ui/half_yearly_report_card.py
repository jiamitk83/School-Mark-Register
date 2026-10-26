from __future__ import annotations

import datetime
from io import BytesIO

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database import SessionLocal
from services import ComponentMarksService
from ui.styles import (
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    TEXT_PRIMARY, TEXT_SECONDARY, PRIMARY_DARK,
)

# Scholastic subjects with Half Yearly component configurations.
# Each entry is (display_name, [db_name_variants], component_config).
# component_config describes how to build the Half Yearly total from components.
# Format: (comp_name, code, max_marks) tuples.
# Core: PT1/5 + MA/5 + SE/5 + PF/5 + WE/80
# Computer: PT1/5 + Practical/30 + Theory/50 + MA/5 + SE/5 + PF/5
# French: PT1/5 + Written/40→80 + MA/5 + SE/5 + PF/5
# GK: grade only (excluded from numeric totals)
SCHOLASTIC_SUBJECTS = [
    ("English", ["ENGLISH"], [
        ("Periodic Test 1", "PT1", 5),
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
        ("Written Exam", "WE", 80),
    ]),
    ("Mathematics", ["MATHEMATICS", "MATHS", "MATH"], [
        ("Periodic Test 1", "PT1", 5),
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
        ("Written Exam", "WE", 80),
    ]),
    ("Hindi", ["HINDI"], [
        ("Periodic Test 1", "PT1", 5),
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
        ("Written Exam", "WE", 80),
    ]),
    ("Science", ["SCIENCE"], [
        ("Periodic Test 1", "PT1", 5),
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
        ("Written Exam", "WE", 80),
    ]),
    ("Social Science", ["SOCIAL SCIENCE", "SOCIAL STUDIES"], [
        ("Periodic Test 1", "PT1", 5),
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
        ("Written Exam", "WE", 80),
    ]),
    ("Computer", ["COMPUTER", "COMPUTER SCIENCE"], [
        ("Periodic Test 1", "PT1", 5),
        ("Practical", "PR", 30),
        ("Theory", "TH", 50),
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
    ]),
    ("French", ["FRENCH"], [
        ("Periodic Test 1", "PT1", 5),
        ("Written Paper", "WE", 40),  # Raw marks /40 converted to /80
        ("Multiple Assessment", "MA", 5),
        ("Subject Enrichment", "SE", 5),
        ("Portfolio", "PF", 5),
    ]),
    ("General Knowledge", ["GENERAL KNOWLEDGE", "GK"], [
        # Grade only — no numeric marks; excluded from totals
    ]),
]

# Grade-only subjects (no numeric marks, grade only)
GRADE_ONLY_SUBJECTS = [
    ("Art Education / Animation", ["ART EDUCATION / ANIMATION", "ART", "ART EDUCATION"], []),
    ("Value Education", ["VALUE EDUCATION", "VALUE"], []),
]

SCHOOL_NAME = "Seth Anandram Jaipuria School, New Jajmau"
QUALIFYING_MARKS = 8

# Half Yearly PT1 conversion: obtained / original_max × 5
# This mirrors the auto-population logic in ComponentMarksService.auto_populate_half_yearly_pt1_from_pt1


class HalfYearlyReportCard(QWidget):
    """Half Yearly Report Card / print preview widget.

    Reuses existing Half Yearly result services and component data.
    Follows the approved Half Yearly component configurations and grade scale.
    Includes Scholastic Areas, Grade-Only Subjects, Overall Totals,
    Comparative Performance (where data available), Co-Scholastic Areas
    (where data available), Signature fields, and Date of Issue.
    """

    def __init__(self, session_factory=SessionLocal):
        super().__init__()
        self.session_factory = session_factory
        self._selected_session_id: int | None = None
        self._selected_class_id: int | None = None
        self._selected_section_id: int | None = None
        self._selected_student_id: int | None = None
        self._all_results: dict[int, dict] = {}
        self._students: list = []
        self._current_student: object | None = None
        self._build_ui()
        self._load_sessions()

    # ------------------------------------------------------------------ services

    def _component_service(self) -> ComponentMarksService:
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
        title = QLabel("Half Yearly Report Card")
        title.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {PRIMARY_DARK};")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Cascade selectors
        cascade_group = QGroupBox("Selection: Session → Class → Section → Student")
        cascade_layout = QHBoxLayout(cascade_group)
        cascade_layout.setSpacing(SPACING_MD)
        cascade_layout.setContentsMargins(SPACING_MD, SPACING_MD + SPACING_SM, SPACING_MD, SPACING_MD)

        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)

        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(200)
        self.class_combo.setEnabled(False)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)

        self.section_combo = QComboBox()
        self.section_combo.setMinimumWidth(200)
        self.section_combo.setEnabled(False)
        self.section_combo.currentIndexChanged.connect(self._on_section_changed)

        self.student_combo = QComboBox()
        self.student_combo.setMinimumWidth(250)
        self.student_combo.setEnabled(False)
        self.student_combo.currentIndexChanged.connect(self._on_student_changed)

        for label, combo in (
            ("Session:", self.session_combo),
            ("Class:", self.class_combo),
            ("Section:", self.section_combo),
            ("Student:", self.student_combo),
        ):
            v = QVBoxLayout()
            v.setSpacing(SPACING_XS)
            v.addWidget(QLabel(label))
            v.addWidget(combo)
            cascade_layout.addLayout(v)

        cascade_layout.addStretch()
        layout.addWidget(cascade_group)

        self.info_label = QLabel("Select Session, Class, Section, and Student to view Half Yearly Report Card")
        self.info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-style: italic;")
        layout.addWidget(self.info_label)

        # Report preview area
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.preview_label, 1)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.preview_btn = QPushButton("Preview Report Card")
        self.preview_btn.clicked.connect(self._preview_report_card)
        self.preview_btn.setEnabled(False)
        btn_layout.addWidget(self.preview_btn)

        self.pdf_btn = QPushButton("Export PDF")
        self.pdf_btn.clicked.connect(self._export_pdf)
        self.pdf_btn.setEnabled(False)
        btn_layout.addWidget(self.pdf_btn)

        self.print_btn = QPushButton("Print")
        self.print_btn.clicked.connect(self._print_report_card)
        self.print_btn.setEnabled(False)
        btn_layout.addWidget(self.print_btn)

        layout.addLayout(btn_layout)

        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ------------------------------------------------------------------ helpers

    def _clear_error(self) -> None:
        self.error_label.setText("")
        self.error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

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
        self._selected_student_id = None
        self.class_combo.setEnabled(False)
        self.section_combo.setEnabled(False)
        self.student_combo.setEnabled(False)
        self.class_combo.clear()
        self.section_combo.clear()
        self.student_combo.clear()
        self.preview_label.clear()
        self.preview_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)
        self.print_btn.setEnabled(False)

        idx = self.session_combo.currentIndex()
        if idx < 0:
            return
        session_id = self.session_combo.itemData(idx)
        if session_id is None or session_id == -1:
            return
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
        self._selected_student_id = None
        self.section_combo.setEnabled(False)
        self.student_combo.setEnabled(False)
        self.section_combo.clear()
        self.student_combo.clear()
        self.preview_label.clear()
        self.preview_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)
        self.print_btn.setEnabled(False)

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
        self._selected_student_id = None
        self.student_combo.setEnabled(False)
        self.student_combo.clear()
        self.preview_label.clear()
        self.preview_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)
        self.print_btn.setEnabled(False)

        idx = self.section_combo.currentIndex()
        if idx < 0:
            return
        section_id = self.section_combo.itemData(idx)
        if section_id is None:
            return
        self._selected_section_id = section_id

        service = self._component_service()
        try:
            students = service.student_repo.list_active_by_section(
                self._selected_session_id, self._selected_class_id, self._selected_section_id
            )
            self._students = students
            self.student_combo.blockSignals(True)
            self.student_combo.clear()
            if not students:
                self.student_combo.addItem("No students available", None)
            else:
                self.student_combo.addItem("Select Student", None)
                for st in students:
                    self.student_combo.addItem(f"{st.name} (Roll: {st.roll_number})", st.id)
            self.student_combo.blockSignals(False)
            self.student_combo.setEnabled(True)
        finally:
            service.session.close()

    def _find_subject(self, service, name_variants: list[str]):
        """Try each name variant until a subject is found in the database."""
        for name in name_variants:
            subj = service.subject_repo.get_by_name(name)
            if subj:
                return subj, name
        return None, None

    def _get_component_marks_for_student(self, service, student_id: int, subject_id: int, exam_type_id: int) -> dict:
        """Get all component marks for a student in a subject+exam type."""
        marks_list = service.repo.list_by_section_exam(
            service.session_repo.get_current_id() if hasattr(service.session_repo, 'get_current_id') else 0,
            0, 0, exam_type_id
        )
        # Filter for this student and subject
        student_comps = {}
        for m in marks_list:
            if m.student_id == student_id and m.subject_id == subject_id:
                student_comps[m.component_id] = m
        return student_comps

    # ------------------------------------------------------------------ data loading

    def _on_student_changed(self) -> None:
        self._clear_error()
        self._selected_student_id = None
        self.preview_label.clear()
        self.preview_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)
        self.print_btn.setEnabled(False)

        idx = self.student_combo.currentIndex()
        if idx < 0:
            return
        student_id = self.student_combo.itemData(idx)
        if student_id is None:
            return
        self._selected_student_id = student_id

        # Find student object
        self._current_student = next(
            (s for s in self._students if s.id == student_id), None
        )

        service = self._component_service()
        try:
            pt1_exam_type = service.exam_type_repo.get_by_name("Half Yearly")
            if not pt1_exam_type:
                self.preview_label.setText("Half Yearly exam type not configured.")
                return

            # Build result lookup per subject
            all_subjects = SCHOLASTIC_SUBJECTS + GRADE_ONLY_SUBJECTS
            self._all_results = {}

            for subj_display, name_variants, comp_config in all_subjects:
                # Skip grade-only subjects without components
                if not comp_config:
                    # Find subject object for grade-only lookup
                    subject, matched_name = self._find_subject(service, name_variants)
                    if not subject:
                        self._all_results[subj_display] = {
                            "name": subj_display,
                            "obtained": None,
                            "max_marks": 0,
                            "grade": None,
                            "status": "no_data",
                            "grade_only": True,
                        }
                        continue

                    # For grade-only, check GK grade from Result model if available
                    from models import Result
                    result = next(
                        (
                            r for r in service.result_repo.list_all()
                            if r.student_id == student_id
                            and r.subject_id == subject.id
                            and r.exam_type_id == pt1_exam_type.id
                        ),
                        None,
                    ) if hasattr(service, 'result_repo') else None

                    gk_grade = result.gk_grade if result else None
                    french_equiv_80 = result.french_equivalent_80 if result else None

                    self._all_results[subj_display] = {
                        "name": subj_display,
                        "obtained": None,
                        "max_marks": 0,
                        "grade": gk_grade,
                        "status": "pending" if gk_grade else "no_data",
                        "grade_only": True,
                        "gk_grade": gk_grade,
                        "french_equivalent_80": french_equiv_80,
                    }
                    continue

                # Find subject object
                subject, matched_name = self._find_subject(service, name_variants)
                if not subject:
                    self._all_results[subj_display] = {
                        "name": subj_display,
                        "obtained": None,
                        "max_marks": 0,
                        "grade": None,
                        "status": "no_data",
                        "grade_only": False,
                    }
                    continue

                # Get components for this subject+Half Yearly exam type
                comps = service.component_repo.get_by_exam_type_and_subject(
                    pt1_exam_type.id, subject.id
                )

                # Build component lookup
                marks_list = service.repo.list_by_section_exam(
                    self._selected_session_id,
                    self._selected_class_id,
                    self._selected_section_id,
                    pt1_exam_type.id,
                )
                marks_lookup = {(m.student_id, m.component_id): m for m in marks_list}

                # Calculate total from configured components
                config_weights = {code: max_marks for _, code, max_marks in comp_config}
                max_marks = 0
                obtained_total = 0
                has_all_marks = True
                status = "pending"

                for comp_name, comp_code, comp_max in comp_config:
                    comp = next((c for c in comps if c.code == comp_code), None)
                    if not comp:
                        has_all_marks = False
                        continue

                    max_marks += comp.max_marks
                    key = (student_id, comp.id)
                    marks = marks_lookup.get(key)

                    if marks:
                        if marks.status == "absent":
                            has_all_marks = False
                            status = "absent"
                            break
                        if marks.marks_obtained is not None:
                            obtained_total += marks.marks_obtained
                        else:
                            has_all_marks = False
                    else:
                        has_all_marks = False

                if not has_all_marks:
                    self._all_results[subj_display] = {
                        "name": subj_display,
                        "obtained": None,
                        "max_marks": max_marks if max_marks > 0 else 0,
                        "grade": None,
                        "status": status,
                        "grade_only": False,
                    }
                else:
                    percentage = round((obtained_total / max_marks) * 100, 2) if max_marks > 0 else 0.0
                    grade = service._calculate_grade(percentage)
                    self._all_results[subj_display] = {
                        "name": subj_display,
                        "obtained": obtained_total,
                        "max_marks": max_marks,
                        "percentage": percentage,
                        "grade": grade,
                        "status": status,
                        "grade_only": False,
                    }

                # Also fetch co-scholastic record for this subject if available
                from models import AcademicRecord
                try:
                    ac_record = next(
                        (
                            r for r in service.academic_record_repo.list_all()
                            if r.student_id == student_id
                            and r.subject_id == subject.id
                            and r.session_id == service.session_repo.get_current_id()
                        ),
                        None,
                    ) if hasattr(service, 'academic_record_repo') else None
                    if ac_record:
                        # Store co-scholastic data for this subject
                        self._all_results[subj_display]["co_scholastic"] = {
                            "subject": ac_record.subject,
                            "score": ac_record.score,
                            "student_name": ac_record.student_name,
                        }
                except Exception:
                    pass  # academic_record_repo may not exist; graceful degradation

            # Also fetch overall Result summary for comparative data
            try:
                from models import Result
                overall_result = next(
                    (
                        r for r in service.result_repo.list_all()
                        if r.student_id == student_id
                        and r.exam_type_id == pt1_exam_type.id
                    ),
                    None,
                ) if hasattr(service, 'result_repo') else None
                if overall_result:
                    self._overall_result_data = {
                        "total_obtained": overall_result.total_obtained,
                        "total_max": overall_result.total_max,
                        "percentage": overall_result.percentage,
                        "grade": overall_result.grade,
                        "component_status": overall_result.component_status,
                        "is_gk_excluded": overall_result.is_gk_excluded,
                        "french_equivalent_80": overall_result.french_equivalent_80,
                        "gk_grade": overall_result.gk_grade,
                    }
                else:
                    self._overall_result_data = None
            except Exception:
                self._overall_result_data = None

        finally:
            service.session.close()

        self._build_report_card_html()

    # ------------------------------------------------------------------ report card building

    def _build_report_card_html(self) -> None:
        student = self._current_student
        if not student:
            return

        session = self._get_session_name()
        class_name = self._get_class_name()
        section_name = self._get_section_name()

        scholastic_rows = []
        total_obtained = 0
        total_max = 0
        for subj_display, _, _ in SCHOLASTIC_SUBJECTS:
            result = self._all_results.get(subj_display)
            if result and result.get("status") == "absent":
                scholastic_rows.append(
                    f"<tr><td>{result['name']}</td><td>-</td><td>-</td><td>-</td></tr>"
                )
            elif result and result.get("obtained") is not None:
                total_obtained += result["obtained"]
                total_max += result["max_marks"]
                scholastic_rows.append(
                    f"<tr><td>{result['name']}</td><td>{result['obtained']}</td>"
                    f"<td>{result['max_marks']}</td><td>{result['grade']}</td></tr>"
                )
            else:
                scholastic_rows.append(
                    f"<tr><td>{subj_display}</td><td>-</td><td>-</td><td>-</td></tr>"
                )

        grade_only_rows = []
        co_scholastic_rows = []
        for subj_display, _, _ in GRADE_ONLY_SUBJECTS:
            result = self._all_results.get(subj_display)
            grade = result.get("grade") if result else None
            grade_only_rows.append(
                f"<tr><td>{result['name'] if result else subj_display}</td>"
                f"<td>{grade if grade else '-'}</td></tr>"
            )

        # Co-Scholastic Areas from AcademicRecord where available
        co_scholastic_subjects = set()
        for subj_display, _, _ in SCHOLASTIC_SUBJECTS:
            result = self._all_results.get(subj_display)
            if result and result.get("co_scholastic"):
                co_scholastic_subjects.add(subj_display)

        for subj_display in co_scholastic_subjects:
            result = self._all_results.get(subj_display)
            co = result.get("co_scholastic", {})
            co_scholastic_rows.append(
                f"<tr><td>{co.get('subject', subj_display)}</td>"
                f"<td>{co.get('score', '-')}</td>"
                f"<td>{co.get('student_name', '-')}</td></tr>"
            )

        if total_max > 0:
            percentage = round((total_obtained / total_max) * 100, 2)
        else:
            percentage = None

        # Comparative performance data where available
        comparative_data = getattr(self, '_overall_result_data', None)

        dob_str = student.dob.strftime("%d-%m-%Y") if student.dob else "Not available"

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; color: #000; }}
.header {{ text-align: center; margin-bottom: 20px; }}
.school-name {{ font-size: 18px; font-weight: bold; }}
.exam-heading {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
.academic-year {{ font-size: 14px; margin-top: 5px; }}
.student-details {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.student-details td {{ padding: 4px 10px; border: 1px solid #000; }}
.subject-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.subject-table th, .subject-table td {{ border: 1px solid #000; padding: 6px 10px; text-align: left; }}
.subject-table th {{ background: #f0f0f0; font-weight: bold; }}
.grade-only-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.grade-only-table th, .grade-only-table td {{ border: 1px solid #000; padding: 6px 10px; text-align: left; }}
.grade-only-table th {{ background: #f0f0f0; font-weight: bold; }}
.co-scholastic-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.co-scholastic-table th, .co-scholastic-table td {{ border: 1px solid #000; padding: 6px 10px; text-align: left; }}
.co-scholastic-table th {{ background: #e8f0e8; font-weight: bold; }}
.totals {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.totals td {{ border: 1px solid #000; padding: 6px 10px; }}
.grade-scale {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.grade-scale th, .grade-scale td {{ border: 1px solid #000; padding: 4px 10px; text-align: left; }}
.grade-scale th {{ background: #f0f0f0; font-weight: bold; }}
.signatures {{ width: 100%; margin-top: 40px; border-collapse: collapse; }}
.signatures td {{ padding: 20px 10px; border-top: 1px solid #000; text-align: center; font-size: 12px; }}
.remark {{ margin-bottom: 20px; padding: 10px; border: 1px solid #000; background: #f9f9f9; }}
.comparative {{ width: 100%; margin-bottom: 20px; }}
.comparative th, .comparative td {{ border: 1px solid #000; padding: 6px 10px; text-align: left; }}
.comparative th {{ background: #f0f0f0; font-weight: bold; }}
</style>
</head>

<body>

<div class="header">
    <div class="school-name">{SCHOOL_NAME}</div>
    <div class="exam-heading">HALF YEARLY EXAMINATION</div>
    <div class="academic-year">Academic Year : ({session})</div>
</div>

<table class="student-details">
    <tr>
        <td><b>Student's Name</b></td><td>{student.name}</td>
        <td><b>Roll No</b></td><td>{student.roll_number}</td>
    </tr>
    <tr>
        <td><b>Father's Name</b></td><td>{student.father_name or 'Not available'}</td>
        <td><b>Admission No.</b></td><td>{student.admission_number}</td>
    </tr>
    <tr>
        <td><b>Mother's Name</b></td><td>{student.mother_name or 'Not available'}</td>
        <td><b>Class</b></td><td>{class_name}</td>
    </tr>
    <tr>
        <td><b>Date of Birth</b></td><td>{dob_str}</td>
        <td><b>Section</b></td><td>{section_name}</td>
    </tr>
</table>

<div style="font-size: 16px; font-weight: bold; margin-bottom: 10px;">SCHOLASTIC AREAS</div>
<div>Maximum Marks: {total_max}&nbsp;&nbsp;|&nbsp;&nbsp;Qualifying Marks: {QUALIFYING_MARKS}</div>

<table class="subject-table">
    <tr><th>Subjects</th><th>Marks Obtained</th><th>Max Marks</th><th>Grades</th></tr>
    {chr(10).join(scholastic_rows)}
</table>

<table class="grade-only-table">
    <tr><th>Subjects</th><th>Grade</th></tr>
    {chr(10).join(grade_only_rows)}
</table>

<div style="font-size: 16px; font-weight: bold; margin-bottom: 10px;">CO-SCHOLASTIC AREAS</div>
<table class="co-scholastic-table">
    <tr><th>Subject</th><th>Score</th><th>Student Name</th></tr>
    {chr(10).join(co_scholastic_rows) if co_scholastic_rows else "<tr><td colspan='3'>No co-scholastic records available</td></tr>"}
</table>

<table class="totals">
    <tr><td style="width:50%"><b>Total</b></td><td style="width:50%">{total_obtained if percentage is not None else '-'}</td></tr>
    <tr><td><b>Percentage</b></td><td>{f'{percentage:.2f}%' if percentage is not None else '-'}</td></tr>
</table>

"""

        # Comparative Performance section where data is available
        if getattr(self, '_overall_result_data', None):
            comp = self._overall_result_data
            percentage_str = comp['percentage']
            if percentage_str is not None:
                percentage_str = f"{percentage_str:.2f}%"
            else:
                percentage_str = "-"
            html += f"""<div class="comparative">
    <b>COMPARATIVE PERFORMANCE</b>
    <table class="comparative">
        <tr><td>Total Obtained</td><td>{comp['total_obtained']}</td></tr>
        <tr><td>Total Maximum</td><td>{comp['total_max']}</td></tr>
        <tr><td>Percentage</td><td>{percentage_str}</td></tr>
        <tr><td>Grade</td><td>{comp['grade'] if comp['grade'] else '-'}</td></tr>
        <tr><td>GK Excluded</td><td>{'Yes' if comp['is_gk_excluded'] else 'No'}</td></tr>
        <tr><td>French Equivalent (80)</td><td>{comp['french_equivalent_80'] if comp['french_equivalent_80'] else '-'}</td></tr>
        <tr><td>GK Grade</td><td>{comp['gk_grade'] if comp['gk_grade'] else '-'}</td></tr>
    </table>
</div>"""

        html += f"""<div class="remark">
    <b>OVERALL REMARK :</b> {self._overall_remark(student.name, percentage)}
</div>

<div style="font-size: 14px; font-weight: bold; margin-top: 20px;">KEY TO GRADES FOR SCHOLASTIC AREAS</div>
<table class="grade-scale">
    <tr><th>PERCENTAGE (%)</th><th>MARKS RANGE</th><th>Grade</th></tr>
    <tr><td>91-100</td><td>A1</td><td>A1</td></tr>
    <tr><td>81-90</td><td>A2</td><td>A2</td></tr>
    <tr><td>71-80</td><td>B1</td><td>B1</td></tr>
    <tr><td>61-70</td><td>B2</td><td>B2</td></tr>
    <tr><td>51-60</td><td>C1</td><td>C1</td></tr>
    <tr><td>41-50</td><td>C2</td><td>C2</td></tr>
    <tr><td>33-40</td><td>D</td><td>D</td></tr>
    <tr><td>32 & Below</td><td>E</td><td>E</td></tr>
</table>

<table class="signatures">
    <tr>
        <td>Principal's Signature</td>
        <td>Date of Issue</td>
        <td>Class Teacher's Signature</td>
    </tr>
    <tr>
        <td>__________________</td>
        <td>{datetime.date.today().strftime('%d-%m-%Y')}</td>
        <td>__________________</td>
    </tr>
</table>

</body>
</html>"""

        self.preview_label.setText(html)
        self.preview_btn.setEnabled(True)
        self.pdf_btn.setEnabled(True)
        self.print_btn.setEnabled(True)

    # ------------------------------------------------------------------ actions

    def _preview_report_card(self) -> None:
        """Open report card in default browser preview."""
        html = self.preview_label.text()
        if not html:
            return
        doc = QTextDocument()
        doc.setHtml(html)
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _export_pdf(self) -> None:
        """Export report card to PDF."""
        from PySide6.QtPrintSupport import QPrinter

        html = self.preview_label.text()
        if not html:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Half Yearly Report Card PDF", "half_yearly_report_card.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.PageSize.A4))

        doc = QTextDocument()
        doc.setHtml(html)
        doc.print_(printer)

        QMessageBox.information(self, "PDF Exported", f"Report card saved to:\n{path}")

    def _print_report_card(self) -> None:
        """Print report card."""
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog

        html = self.preview_label.text()
        if not html:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)

    # ------------------------------------------------------------------ helpers

    def _get_session_name(self) -> str:
        service = self._component_service()
        try:
            sess = service.session_repo.get(self._selected_session_id) if self._selected_session_id else None
            return sess.name if sess else "2026/2027"
        finally:
            service.session.close()

    def _get_class_name(self) -> str:
        if not self._selected_class_id:
            return ""
        service = self._component_service()
        try:
            cls = service.class_repo.get(self._selected_class_id)
            return cls.name if cls else ""
        finally:
            service.session.close()

    def _get_section_name(self) -> str:
        if not self._selected_section_id:
            return ""
        service = self._component_service()
        try:
            sec = service.section_repo.get(self._selected_section_id)
            return sec.name if sec else ""
        finally:
            service.session.close()

    def _overall_remark(self, student_name: str, percentage: float | None) -> str:
        if percentage is None:
            return f"{student_name} has not completed all Half Yearly assessments. Please ensure all subject marks are entered."
        first_name = student_name.split()[0] if student_name else "The student"
        if percentage >= 91:
            return f"{first_name} has shown excellent academic performance in Half Yearly. Keep up the good work!"
        elif percentage >= 81:
            return f"{first_name} has shown very good academic performance in Half Yearly. Well done!"
        elif percentage >= 71:
            return f"{first_name} has shown good academic performance in Half Yearly. Keep working hard!"
        elif percentage >= 61:
            return f"{first_name} has shown satisfactory academic performance in Half Yearly."
        elif percentage >= 51:
            return f"{first_name} has shown fair academic performance in Half Yearly. There is room for improvement."
        else:
            return f"{first_name} needs to put in extra effort to improve academic performance in Half Yearly."


def _subject_display(key: str) -> str:
    return key