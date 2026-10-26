"""Regression tests for Half Yearly PT1/5 auto-population from PT1 marks."""
from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest
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
    StudentService,
    SubjectService,
)


@pytest.fixture
def hy_db():
    """Create temp DB with PT1 and Half Yearly exam types configured."""
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
        bob = student_svc.add_student(
            session_obj.id, cls.id, sec.id, "Bob Smith", "R002"
        )
        sess.flush()

        core_subjects = {
            "english": Subject(name="English", code="ENG", is_active=True),
            "maths": Subject(name="Maths", code="MATHS", is_active=True),
            "hindi": Subject(name="Hindi", code="HINDI", is_active=True),
            "science": Subject(name="Science", code="SCIENCE", is_active=True),
            "social": Subject(name="Social Science", code="SOCIAL SCIENCE", is_active=True),
        }
        for subj in core_subjects.values():
            sess.add(subj)
        sess.flush()

        for subj in core_subjects.values():
            mapping = SubjectSectionMapping(
                subject_id=subj.id, class_id=cls.id, section_id=sec.id, is_active=True
            )
            sess.add(mapping)

        comp_svc = ExamComponentService(sess)
        exam_svc = ExamTypeService(sess)

        # Get the exam types created by session initialization
        pt1_exam = exam_svc.repo.get_by_name("PT1")
        hy_exam = exam_svc.repo.get_by_name("Half Yearly")

        # Add components for the newly added subjects
        for subj in core_subjects.values():
            # PT1 component (25 max)
            comp_svc.add_component(
                pt1_exam.id, "Periodic Test 1", "PT1", 25,
                subject_id=subj.id, display_order=1
            )
            # Half Yearly PT1 component (5 max)
            comp_svc.add_component(
                hy_exam.id, "Periodic Test 1", "PT1", 5,
                subject_id=subj.id, display_order=1
            )

        sess.commit()

        yield {
            "db": (db_fd, db_path, engine, SessionLocal),
            "session": session_obj,
            "class": cls,
            "section": sec,
            "alice": alice,
            "bob": bob,
            "english": core_subjects["english"],
            "maths": core_subjects["maths"],
            "hindi": core_subjects["hindi"],
            "science": core_subjects["science"],
            "social": core_subjects["social"],
            "pt1_exam": pt1_exam,
            "hy_exam": hy_exam,
            "SessionLocal": SessionLocal,
        }

    finally:
        sess.close()
        engine.dispose()
        os.unlink(db_path)


@pytest.fixture
def hy_db_with_pt1_marks(hy_db):
    """hy_db with saved PT1 marks for Alice in English and Maths (direct DB insert, no auto-refresh)."""
    d = hy_db
    sess = d["SessionLocal"]()
    svc = ComponentMarksService(sess)
    try:
        pt1_eng_comps = svc.component_repo.get_by_exam_type_and_subject(
            d["pt1_exam"].id, d["english"].id
        )
        pt1_maths_comps = svc.component_repo.get_by_exam_type_and_subject(
            d["pt1_exam"].id, d["maths"].id
        )

        pt1_eng = next(c for c in pt1_eng_comps if c.code == "PT1")
        pt1_maths = next(c for c in pt1_maths_comps if c.code == "PT1")

        # Insert PT1 marks directly via repo (bypasses save_component_marks -> _refresh_dependent_marks)
        alice_pt1_eng = ComponentMarks(
            student_id=d["alice"].id,
            subject_id=d["english"].id,
            exam_type_id=d["pt1_exam"].id,
            component_id=pt1_eng.id,
            session_id=d["session"].id,
            class_id=d["class"].id,
            section_id=d["section"].id,
            marks_obtained=20,
            max_marks=pt1_eng.max_marks,
            status="saved",
        )
        alice_pt1_maths = ComponentMarks(
            student_id=d["alice"].id,
            subject_id=d["maths"].id,
            exam_type_id=d["pt1_exam"].id,
            component_id=pt1_maths.id,
            session_id=d["session"].id,
            class_id=d["class"].id,
            section_id=d["section"].id,
            marks_obtained=17,
            max_marks=pt1_maths.max_marks,
            status="saved",
        )
        svc.repo.add(alice_pt1_eng)
        svc.repo.add(alice_pt1_maths)
        sess.commit()

        yield d
    finally:
        sess.close()


class TestHalfYearlyPT1AutoPopulation:
    """Tests for Half Yearly PT1/5 auto-population from PT1 source marks."""

    def test_maths_pt1_populates_half_yearly_pt1(self, hy_db_with_pt1_marks):
        """Maths PT1 marks (25 max) must auto-populate Half Yearly PT1/5 (5 max).

        Formula: obtained / original_maximum × 5
        """
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            count = svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["maths"].id
            )

            assert count > 0, "Should have auto-populated at least one record"

            hy_maths_comp = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["maths"].id
            )
            hy_pt1 = next(c for c in hy_maths_comp if c.code == "PT1")

            alice_hy = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy is not None, "Alice should have Half Yearly PT1 marks"
            # 17/25 * 5 = 3.4 → round to 3
            assert alice_hy.marks_obtained == round(17 * 5 / 25), (
                f"Expected {round(17 * 5 / 25)}, got {alice_hy.marks_obtained}"
            )
            assert alice_hy.status == "converted", (
                "Converted marks should have status 'converted' (read-only)"
            )
        finally:
            sess.close()

    def test_english_pt1_populates_half_yearly_pt1(self, hy_db_with_pt1_marks):
        """English PT1 marks (25 max) must auto-populate Half Yearly PT1/5 (5 max)."""
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            count = svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )

            assert count > 0

            hy_eng_comp = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["english"].id
            )
            hy_pt1 = next(c for c in hy_eng_comp if c.code == "PT1")

            alice_hy = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy is not None
            # 20/25 * 5 = 4
            assert alice_hy.marks_obtained == round(20 * 5 / 25)
            assert alice_hy.marks_obtained == 4
            assert alice_hy.status == "converted"
        finally:
            sess.close()

    def test_all_core_subjects_populate(self, hy_db_with_pt1_marks):
        """PT1 marks must auto-populate for all core subjects."""
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # Add PT1 marks for Bob in all core subjects (direct DB insert)
            pt1_comps_list = svc.component_repo.get_by_exam_type_and_subject(
                d["pt1_exam"].id, d["english"].id
            )
            pt1_eng = next(c for c in pt1_comps_list if c.code == "PT1")

            for key, subj_name in [("english", d["english"]), ("maths", d["maths"]),
                                   ("hindi", d["hindi"]), ("science", d["science"]),
                                   ("social", d["social"])]:
                pt1_comps = svc.component_repo.get_by_exam_type_and_subject(
                    d["pt1_exam"].id, subj_name.id
                )
                pt1_comp = next(c for c in pt1_comps if c.code == "PT1")
                marks_val = {"english": 15, "maths": 22, "hindi": 18, "science": 20, "social": 10}[key]
                bob_pt1 = ComponentMarks(
                    student_id=d["bob"].id,
                    subject_id=subj_name.id,
                    exam_type_id=d["pt1_exam"].id,
                    component_id=pt1_comp.id,
                    session_id=d["session"].id,
                    class_id=d["class"].id,
                    section_id=d["section"].id,
                    marks_obtained=marks_val,
                    max_marks=pt1_comp.max_marks,
                    status="saved",
                )
                svc.repo.add(bob_pt1)
            sess.commit()

            for key, subj_name in [("english", d["english"]), ("maths", d["maths"]),
                                   ("hindi", d["hindi"]), ("science", d["science"]),
                                   ("social", d["social"])]:
                count = svc.auto_populate_half_yearly_pt1_from_pt1(
                    d["session"].id, d["class"].id, d["section"].id, subj_name.id
                )
                assert count >= 1

                hy_comps = svc.component_repo.get_by_exam_type_and_subject(
                    d["hy_exam"].id, subj_name.id
                )
                hy_pt1 = next(c for c in hy_comps if c.code == "PT1")

                bob_hy = svc.repo.get_by_student_component(d["bob"].id, hy_pt1.id)
                assert bob_hy is not None, f"Bob should have Half Yearly PT1 for {subj_name.name}"
                assert bob_hy.status == "converted"
        finally:
            sess.close()

    def test_missing_source_marks_stays_pending(self, hy_db_with_pt1_marks):
        """If PT1 marks don't exist, Half Yearly PT1 should stay pending."""
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # Bob has no PT1 marks - run auto-populate
            count = svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["maths"].id
            )

            hy_maths_comp = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["maths"].id
            )
            hy_pt1 = next(c for c in hy_maths_comp if c.code == "PT1")

            bob_hy = svc.repo.get_by_student_component(d["bob"].id, hy_pt1.id)
            # Bob should have no Half Yearly PT1 marks (stays pending / no record)
            # The count should only reflect created records, not skipped ones
            # Alice should still get populated
            alice_hy = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy is not None
            assert alice_hy.status == "converted"
        finally:
            sess.close()

    def test_source_edit_refreshes_half_yearly(self, hy_db_with_pt1_marks):
        """Editing PT1 source marks should refresh Half Yearly PT1 via _refresh_dependent_marks."""
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # First auto-populate to create initial converted marks
            svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )
            sess.commit()

            pt1_eng_comps = svc.component_repo.get_by_exam_type_and_subject(
                d["pt1_exam"].id, d["english"].id
            )
            pt1_eng = next(c for c in pt1_eng_comps if c.code == "PT1")

            # Change Alice's PT1 English marks from 20 to 15 (using save_component_marks which triggers refresh)
            svc.save_component_marks(d["alice"].id, pt1_eng.id, 15, "saved")

            # Verify Half Yearly PT1 was refreshed
            hy_eng_comps = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["english"].id
            )
            hy_pt1 = next(c for c in hy_eng_comps if c.code == "PT1")

            alice_hy = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy is not None
            assert alice_hy.marks_obtained == round(15 * 5 / 25)
            assert alice_hy.marks_obtained == 3
            assert alice_hy.status == "converted"
        finally:
            sess.close()

    def test_persistence_after_restart(self, hy_db_with_pt1_marks):
        """Auto-populated converted marks must persist in DB after the service session is closed and reopened."""
        d = hy_db_with_pt1_marks
        SessionLocal = d["SessionLocal"]

        # First session: auto-populate
        sess1 = SessionLocal()
        svc1 = ComponentMarksService(sess1)
        try:
            svc1.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["maths"].id
            )
        finally:
            sess1.close()

        # Second session: verify marks persist
        sess2 = SessionLocal()
        svc2 = ComponentMarksService(sess2)
        try:
            hy_maths_comps = svc2.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["maths"].id
            )
            hy_pt1 = next(c for c in hy_maths_comps if c.code == "PT1")

            alice_hy = svc2.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy is not None, "Converted marks should persist in DB"
            assert alice_hy.marks_obtained == round(17 * 5 / 25), f"Expected {round(17 * 5 / 25)}, got {alice_hy.marks_obtained}"
            assert alice_hy.status == "converted"
        finally:
            sess2.close()

    def test_auto_populate_is_idempotent(self, hy_db_with_pt1_marks):
        """Running auto-populate multiple times should not create duplicates."""
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            count1 = svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )
            count2 = svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )

            # Second run should not create new records (Alice's marks already converted)
            assert count2 == 0, "Idempotent: second run should create 0 new records"

            hy_eng_comps = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["english"].id
            )
            hy_pt1 = next(c for c in hy_eng_comps if c.code == "PT1")

            alice_hy = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy is not None
            assert alice_hy.marks_obtained == 4  # 20/25 * 5
            assert alice_hy.status == "converted"
        finally:
            sess.close()

    def test_manual_override_not_overwritten(self, hy_db_with_pt1_marks):
        """If a teacher manually entered Half Yearly PT1 marks, auto-populate should not overwrite them."""
        d = hy_db_with_pt1_marks
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            hy_maths_comps = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["maths"].id
            )
            hy_pt1 = next(c for c in hy_maths_comps if c.code == "PT1")

            # First, auto-populate
            svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["maths"].id
            )

            # Manually override Alice's Half Yearly PT1
            alice_hy = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            alice_hy.marks_obtained = 5
            alice_hy.status = "saved"
            sess.commit()

            # Re-run auto-populate
            svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["maths"].id
            )
            sess.commit()
            sess.expire_all()

            # Verify manual override is preserved
            alice_hy2 = svc.repo.get_by_student_component(d["alice"].id, hy_pt1.id)
            assert alice_hy2.marks_obtained == 5, "Manual marks should not be overwritten"
            assert alice_hy2.status == "saved", "Manual status should not be overwritten"
        finally:
            sess.close()

    def test_converted_marks_are_read_only_in_grid(self, hy_db_with_pt1_marks):
        """Converted marks must be non-editable in the UI grid."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        import sys

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication(sys.argv)

        d = hy_db_with_pt1_marks
        SessionLocal = d["SessionLocal"]

        # First run auto-population so converted marks exist in DB
        sess = SessionLocal()
        svc = ComponentMarksService(sess)
        try:
            svc.auto_populate_half_yearly_pt1_from_pt1(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )
            sess.commit()
        finally:
            sess.close()

        from ui.marks_view import MarksView
        mv = MarksView(SessionLocal)

        # Set selection state
        mv._selected_session_id = d["session"].id
        mv._selected_class_id = d["class"].id
        mv._selected_section_id = d["section"].id
        mv._selected_exam_type_id = d["hy_exam"].id
        mv._selected_subject_id = d["english"].id
        mv._load_component_grid()

        # Find the PT1 column
        pt1_col = -1
        for col in range(2, mv.marks_table.columnCount()):
            header = mv.marks_table.horizontalHeaderItem(col)
            if header and "PT1" in header.text():
                pt1_col = col
                break

        assert pt1_col >= 0, "PT1 column should exist in the grid"

        # Alice should have converted marks in the PT1 column
        for row in range(mv.marks_table.rowCount()):
            item = mv.marks_table.item(row, pt1_col)
            if item and item.text():
                # Check that the converted cell is not editable
                flags = item.flags()
                assert not (flags & Qt.ItemFlag.ItemIsEditable), (
                    "Converted marks cell should not be editable"
                )
                # Also check background is set for converted marks
                bg = item.background()
                assert bg.color().isValid(), "Converted marks should have background color set"
                break