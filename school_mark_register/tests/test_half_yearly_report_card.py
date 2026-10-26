"""Tests for the Half Yearly Report Card feature."""
from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import (
    AcademicSession,
    Class,
    ComponentMarks,
    ExamComponent,
    ExamType,
    Section,
    Student,
    Subject,
    SubjectSectionMapping,
)
from services import (
    ComponentMarksService,
    ExamTypeService,
    ExamComponentService,
    SectionService,
    StudentService,
)
from ui.half_yearly_report_card import (
    HalfYearlyReportCard,
    SCHOLASTIC_SUBJECTS,
    GRADE_ONLY_SUBJECTS,
)


@pytest.fixture
def hy_qt_app():
    """Ensure QApplication runs in offscreen mode for headless Qt tests."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


@pytest.fixture
def hy_rc_db():
    """Create temp DB with Half Yearly exam types and components configured."""
    from services import ClassService, SectionService
    from services import SessionService

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sess = SessionLocal()

    try:
        session_svc = SessionService(sess)
        session_obj = session_svc.add_session(
            "2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True
        )
        sess.flush()

        class_svc = ClassService(sess)
        cls = class_svc.add_class("Class 9")

        section_svc = SectionService(sess)
        sec = section_svc.add_section(cls.id, "Section A")

        student_svc = StudentService(sess)
        alice = student_svc.add_student(
            session_obj.id, cls.id, sec.id, "Alice Johnson", "R001"
        )

        english = Subject(name="English", code="ENG", is_active=True)
        maths = Subject(name="Maths", code="MATHS", is_active=True)
        for subj in [english, maths]:
            sess.add(subj)
        sess.flush()

        for subj in [english, maths]:
            mapping = SubjectSectionMapping(
                subject_id=subj.id, class_id=cls.id, section_id=sec.id, is_active=True
            )
            sess.add(mapping)

        comp_svc = ExamComponentService(sess)
        exam_svc = ExamTypeService(sess)

        hy_exam = exam_svc.repo.get_by_name("Half Yearly")
        pt1_exam = exam_svc.repo.get_by_name("PT1")

        for subj in [english, maths]:
            comp_svc.add_component(
                pt1_exam.id, "Periodic Test 1", "PT1", 25,
                subject_id=subj.id, display_order=1
            )
            hy_components = [
                ("Periodic Test 1", "PT1", 5, 1),
                ("Multiple Assessment", "MA", 5, 2),
                ("Subject Enrichment", "SE", 5, 3),
                ("Portfolio", "PF", 5, 4),
                ("Written Exam", "WE", 80, 5),
            ]
            for name, code, max_marks, order in hy_components:
                comp_svc.add_component(
                    hy_exam.id, name, code, max_marks,
                    subject_id=subj.id, display_order=order
                )

        sess.commit()

        yield {
            "db": (db_fd, db_path, engine, SessionLocal),
            "session": session_obj,
            "class": cls,
            "section": sec,
            "alice": alice,
            "english": english,
            "maths": maths,
            "hy_exam": hy_exam,
            "pt1_exam": pt1_exam,
            "SessionLocal": SessionLocal,
        }

    finally:
        sess.close()
        engine.dispose()
        os.unlink(db_path)


class TestHalfYearlyReportCard:
    """Tests for the Half Yearly Report Card."""

    def test_scholastic_subjects_config(self):
        """Core subject configuration includes required components."""
        core = next(
            s for s in SCHOLASTIC_SUBJECTS if s[0] == "English"
        )
        display_name, variants, comps = core
        codes = {c[1] for c in comps}
        assert "PT1" in codes
        assert "MA" in codes
        assert "SE" in codes
        assert "PF" in codes
        assert "WE" in codes
        # WE max should be 80
        we = next((c for c in comps if c[1] == "WE"), None)
        assert we is not None and we[2] == 80

    def test_grade_only_subjects(self):
        """Grade-only subjects should not have numeric components."""
        gk = next(
            s for s in SCHOLASTIC_SUBJECTS if s[0] == "General Knowledge"
        )
        display_name, variants, comps = gk
        assert len(comps) == 0  # Grade only

    def test_report_card_instantiates(self, hy_rc_db, hy_qt_app):
        """HalfYearlyReportCard widget can be instantiated."""
        rc = HalfYearlyReportCard(hy_rc_db["SessionLocal"])
        assert rc is not None
        rc.close() if hasattr(rc, 'close') else None

    def test_student_dropdown_populated_on_section_change(self, hy_rc_db, hy_qt_app):
        """Students load into the Student dropdown when a section is selected."""
        rc = HalfYearlyReportCard(hy_rc_db["SessionLocal"])
        try:
            cls_idx = rc.class_combo.findData(hy_rc_db["class"].id)
            assert cls_idx >= 0
            rc.class_combo.setCurrentIndex(cls_idx)
            rc._on_class_changed()

            idx = rc.section_combo.findData(hy_rc_db["section"].id)
            assert idx >= 0
            rc.section_combo.setCurrentIndex(idx)
            rc._on_section_changed()

            assert rc.student_combo.isEnabled()
            assert rc.student_combo.count() == 2
            assert rc.student_combo.itemData(0) is None
            assert rc.student_combo.itemData(1) == hy_rc_db["alice"].id
            assert "Alice Johnson" in rc.student_combo.itemText(1)
        finally:
            rc.close()

    def test_student_selection_loads_report_with_pending_marks(self, hy_rc_db, hy_qt_app):
        """Selecting a student with no Half Yearly marks still loads a pending report."""
        rc = HalfYearlyReportCard(hy_rc_db["SessionLocal"])
        try:
            cls_idx = rc.class_combo.findData(hy_rc_db["class"].id)
            assert cls_idx >= 0
            rc.class_combo.setCurrentIndex(cls_idx)
            rc._on_class_changed()

            idx = rc.section_combo.findData(hy_rc_db["section"].id)
            assert idx >= 0
            rc.section_combo.setCurrentIndex(idx)
            rc._on_section_changed()

            rc.student_combo.setCurrentIndex(1)

            assert rc._selected_student_id == hy_rc_db["alice"].id
            assert rc.preview_btn.isEnabled()
            assert "Alice Johnson" in rc.preview_label.text()
        finally:
            rc.close()

    def test_empty_state_when_no_students(self, hy_rc_db, hy_qt_app):
        """Shows 'No students available' when section has no students."""
        rc = HalfYearlyReportCard(hy_rc_db["SessionLocal"])
        try:
            sess = hy_rc_db["SessionLocal"]()
            section_svc = SectionService(sess)
            empty_sec = section_svc.add_section(hy_rc_db["class"].id, "Section B")
            empty_sec_id = empty_sec.id
            sess.close()

            cls_idx = rc.class_combo.findData(hy_rc_db["class"].id)
            assert cls_idx >= 0
            rc.class_combo.setCurrentIndex(cls_idx)
            rc._on_class_changed()

            idx = rc.section_combo.findData(empty_sec_id)
            assert idx >= 0
            rc.section_combo.setCurrentIndex(idx)
            rc._on_section_changed()

            assert rc.student_combo.isEnabled()
            assert rc.student_combo.count() == 1
            assert rc.student_combo.itemData(0) is None
            assert "No students" in rc.student_combo.itemText(0)
            assert not rc.preview_btn.isEnabled()
        finally:
            rc.close()

    def test_section_change_refreshes_student_dropdown(self, hy_rc_db, hy_qt_app):
        """Changing section clears and repopulates the Student dropdown."""
        rc = HalfYearlyReportCard(hy_rc_db["SessionLocal"])
        try:
            cls_idx = rc.class_combo.findData(hy_rc_db["class"].id)
            assert cls_idx >= 0
            rc.class_combo.setCurrentIndex(cls_idx)
            rc._on_class_changed()

            idx = rc.section_combo.findData(hy_rc_db["section"].id)
            assert idx >= 0
            rc.section_combo.setCurrentIndex(idx)
            rc._on_section_changed()
            assert rc.student_combo.count() == 2
            assert rc.student_combo.itemData(1) == hy_rc_db["alice"].id

            sess = hy_rc_db["SessionLocal"]()
            section_svc = SectionService(sess)
            student_svc = StudentService(sess)
            sec_b = section_svc.add_section(hy_rc_db["class"].id, "Section B")
            sec_b_id = sec_b.id
            bob = student_svc.add_student(
                hy_rc_db["session"].id, hy_rc_db["class"].id, sec_b_id,
                "Bob Smith", "R002",
            )
            bob_id = bob.id
            sess.close()

            cls_idx = rc.class_combo.findData(hy_rc_db["class"].id)
            assert cls_idx >= 0
            rc.class_combo.setCurrentIndex(cls_idx)
            rc._on_class_changed()
            idx = rc.section_combo.findData(sec_b_id)
            assert idx >= 0
            rc.section_combo.setCurrentIndex(idx)
            rc._on_section_changed()
            assert rc.student_combo.count() == 2
            assert rc.student_combo.itemData(1) == bob_id
            assert "Bob Smith" in rc.student_combo.itemText(1)

            found_alice = any(
                rc.student_combo.itemData(i) == hy_rc_db["alice"].id
                for i in range(rc.student_combo.count())
            )
            assert not found_alice
        finally:
            rc.close()
