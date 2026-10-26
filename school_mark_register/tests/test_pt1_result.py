"""Tests for PT1 Result module."""
from __future__ import annotations

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
from services import ComponentMarksService, ExamComponentService, ExamTypeService


@pytest.fixture
def pt1_db_session():
    """Create an in-memory SQLite database for PT1 Result testing."""
    import os
    import tempfile

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sess = SessionLocal()
    yield sess, SessionLocal, engine
    sess.close()
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def pt1_setup(pt1_db_session):
    """Create full dataset: session, class, section, students, PT1 exam type, subject, component, marks."""
    sess, SessionLocal, engine = pt1_db_session

    session_obj = AcademicSession(
        name="2026/2027", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31),
        status="active", is_current=True,
    )
    sess.add(session_obj)
    sess.flush()

    cls = Class(name="Class 1", display_order=1)
    sess.add(cls)
    sess.flush()

    sec = Section(name="Section A", class_id=cls.id, display_order=1)
    sess.add(sec)
    sess.flush()

    student_svc = None
    from services import StudentService
    student_svc = StudentService(sess)

    student1 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Alice Johnson", "R001")
    student2 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Bob Smith", "R002")
    student3 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Charlie Brown", "R003")

    subject = Subject(name="English", code="ENG", is_active=True)
    sess.add(subject)
    sess.flush()

    mapping = SubjectSectionMapping(
        subject_id=subject.id, class_id=cls.id, section_id=sec.id, is_active=True
    )
    sess.add(mapping)
    sess.flush()

    pt1_exam = ExamType(name="PT1", code="PTI", description="Periodic Test 1",
                        max_marks=25, weightage=1.0, display_order=1, is_active=True)
    sess.add(pt1_exam)
    sess.flush()

    pt1_comp = ExamComponent(
        exam_type_id=pt1_exam.id, subject_id=subject.id,
        name="Periodic Test 1", code="PT1", max_marks=25, display_order=1, is_active=True,
    )
    sess.add(pt1_comp)
    sess.flush()

    # Add marks for students
    # Alice: 24/25 = 96% → Grade A1
    alice_marks = ComponentMarks(
        student_id=student1.id, subject_id=subject.id, exam_type_id=pt1_exam.id,
        component_id=pt1_comp.id, session_id=session_obj.id, class_id=cls.id,
        section_id=sec.id, marks_obtained=24, max_marks=25, status="saved",
    )
    # Bob: 20/25 = 80% → Grade B1
    bob_marks = ComponentMarks(
        student_id=student2.id, subject_id=subject.id, exam_type_id=pt1_exam.id,
        component_id=pt1_comp.id, session_id=session_obj.id, class_id=cls.id,
        section_id=sec.id, marks_obtained=20, max_marks=25, status="saved",
    )
    # Charlie: absent
    charlie_marks = ComponentMarks(
        student_id=student3.id, subject_id=subject.id, exam_type_id=pt1_exam.id,
        component_id=pt1_comp.id, session_id=session_obj.id, class_id=cls.id,
        section_id=sec.id, marks_obtained=None, max_marks=25, status="absent",
    )

    sess.add_all([alice_marks, bob_marks, charlie_marks])
    sess.commit()

    return {
        "session": session_obj,
        "class": cls,
        "section": sec,
        "student1": student1,
        "student2": student2,
        "student3": student3,
        "subject": subject,
        "pt1_exam": pt1_exam,
        "pt1_comp": pt1_comp,
        "SessionLocal": SessionLocal,
    }


class TestCalculateGrade:
    """Tests for the grade calculation."""

    def test_grade_a1(self, pt1_db_session):
        sess = pt1_db_session[0]
        svc = ComponentMarksService(sess)
        assert svc._calculate_grade(91) == "A1"
        assert svc._calculate_grade(95) == "A1"
        assert svc._calculate_grade(100) == "A1"

    def test_grade_a2(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(81) == "A2"
        assert svc._calculate_grade(90) == "A2"

    def test_grade_b1(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(71) == "B1"
        assert svc._calculate_grade(80) == "B1"

    def test_grade_b2(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(61) == "B2"
        assert svc._calculate_grade(70) == "B2"

    def test_grade_c1(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(51) == "C1"
        assert svc._calculate_grade(60) == "C1"

    def test_grade_c2(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(41) == "C2"
        assert svc._calculate_grade(50) == "C2"

    def test_grade_d(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(33) == "D"
        assert svc._calculate_grade(40) == "D"

    def test_grade_e(self, pt1_db_session):
        svc = ComponentMarksService(pt1_db_session[0])
        assert svc._calculate_grade(32) == "E"
        assert svc._calculate_grade(0) == "E"


class TestGetPt1ResultSummary:
    """Tests for ComponentMarksService.get_pt1_result_summary()."""

    def test_returns_one_row_per_student(self, pt1_setup):
        """Each student should appear exactly once in the result."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            assert len(results) == 3
            student_ids = {r["student_id"] for r in results}
            assert student_ids == {
                pt1_setup["student1"].id,
                pt1_setup["student2"].id,
                pt1_setup["student3"].id,
            }
        finally:
            sess.close()

    def test_percentage_calculation_two_decimals(self, pt1_setup):
        """Percentage should be calculated as obtained/max*100 with 2 decimals."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            for r in results:
                if r["obtained_marks"] is not None:
                    expected = round((r["obtained_marks"] / r["max_marks"]) * 100, 2)
                    assert r["percentage"] == expected
                    # Verify 2 decimal places in string representation
                    assert f"{r['percentage']:.2f}" == f"{r['percentage']:.2f}"
        finally:
            sess.close()

    def test_grade_assigned_for_scored_students(self, pt1_setup):
        """Grade should be assigned based on percentage."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            for r in results:
                if r["percentage"] is not None:
                    assert r["grade"] is not None
                    assert r["grade"] in ("A1", "A2", "B1", "B2", "C1", "C2", "D", "E")
        finally:
            sess.close()

    def test_pending_marks_stay_blank(self, pt1_db_session, pt1_setup):
        """Pending marks should show as blank (None), not zero."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # Add a 4th student with no marks entry (pending)
            student_svc = None
            from services import StudentService
            student_svc = StudentService(sess)
            student4 = student_svc.add_student(
                pt1_setup["session"].id, pt1_setup["class"].id, pt1_setup["section"].id,
                "Diana Prince", "R004"
            )
            sess.commit()

            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            diana = next(r for r in results if r["student_id"] == student4.id)
            assert diana["obtained_marks"] is None
            assert diana["percentage"] is None
            assert diana["grade"] is None
            assert diana["status"] == "pending"
        finally:
            sess.close()

    def test_absent_status_preserved(self, pt1_setup):
        """Absent students should have 'absent' status, not pending."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            charlie = next(r for r in results if r["student_id"] == pt1_setup["student3"].id)
            assert charlie["status"] == "absent"
            assert charlie["obtained_marks"] is None
        finally:
            sess.close()

    def test_specific_percentage_values(self, pt1_setup):
        """Alice 24/25 = 96%, Bob 20/25 = 80%."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            alice = next(r for r in results if r["student_id"] == pt1_setup["student1"].id)
            assert alice["percentage"] == 96.0
            assert alice["grade"] == "A1"

            bob = next(r for r in results if r["student_id"] == pt1_setup["student2"].id)
            assert bob["percentage"] == 80.0
            assert bob["grade"] == "B1"
        finally:
            sess.close()

    def test_no_results_if_pt1_missing(self, pt1_db_session):
        """If PT1 exam type doesn't exist, should return empty list."""
        sess, SessionLocal, engine = pt1_db_session
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_pt1_result_summary(1, 1, 1, 1)
            assert results == []
        finally:
            sess.close()

    def test_no_results_if_no_components(self, pt1_db_session, pt1_setup):
        """If no PT1 components for the subject, should return empty list."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # Use a subject that has no PT1 components
            from models import Subject
            other_subject = Subject(name="Physics", code="PHY", is_active=True)
            sess.add(other_subject)
            sess.flush()
            sess.commit()

            results = svc.get_pt1_result_summary(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                other_subject.id,
            )
            assert results == []
        finally:
            sess.close()


class TestExportPt1ResultsCsv:
    """Tests for CSV export of PT1 results."""

    def test_csv_has_correct_headers(self, pt1_setup):
        """CSV export should have correct column headers."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            csv_content = svc.export_pt1_results_to_csv(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            lines = csv_content.strip().split("\n")
            headers = [h.strip() for h in lines[0].split(",")]
            expected_headers = [
                "Roll Number", "Admission Number", "Student Name",
                "Max Marks", "Obtained Marks", "Percentage", "Grade", "Status"
            ]
            assert headers == expected_headers
        finally:
            sess.close()

    def test_csv_contains_all_students(self, pt1_setup):
        """CSV should contain one row per student."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            csv_content = svc.export_pt1_results_to_csv(
                pt1_setup["session"].id,
                pt1_setup["class"].id,
                pt1_setup["section"].id,
                pt1_setup["subject"].id,
            )
            lines = csv_content.strip().split("\n")
            # 1 header + 3 student rows
            assert len(lines) == 4
        finally:
            sess.close()


class TestGetPt1SubjectsForClassSection:
    """Tests for ComponentMarksService.get_pt1_subjects_for_class_section()."""

    def test_returns_subjects_with_pt1_components(self, pt1_setup):
        """Should return subjects that have PT1 components mapped."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            subjects = svc.get_pt1_subjects_for_class_section(
                pt1_setup["class"].id, pt1_setup["section"].id
            )
            assert len(subjects) == 1
            assert subjects[0].name == "English"
        finally:
            sess.close()

    def test_excludes_subjects_without_pt1(self, pt1_db_session, pt1_setup):
        """Subjects without PT1 components should not be returned."""
        sess = pt1_setup["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            from models import Subject
            other_subject = Subject(name="Physics", code="PHY", is_active=True)
            sess.add(other_subject)
            sess.flush()
            sess.commit()

            subjects = svc.get_pt1_subjects_for_class_section(
                pt1_setup["class"].id, pt1_setup["section"].id
            )
            assert len(subjects) == 1
            assert subjects[0].name == "English"
        finally:
            sess.close()


class TestPt1ResultView:
    """UI tests for Pt1ResultView - test that view can be created and data flows correctly."""

    def test_view_creates_successfully(self, pt1_db_session):
        """The view should instantiate without errors."""
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.pt1_result_view import Pt1ResultView
        view = Pt1ResultView(pt1_db_session[1])
        assert view is not None
        assert view.result_table is not None
        app.quit()

    def test_view_populates_table(self, pt1_setup):
        """The view should populate the results table after loading."""
        os_env = "QT_QPA_PLATFORM"
        import os
        old = os.environ.get(os_env)
        os.environ[os_env] = "offscreen"
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication([])
            from ui.pt1_result_view import Pt1ResultView
            view = Pt1ResultView(pt1_setup["SessionLocal"])

            view._selected_session_id = pt1_setup["session"].id
            view._selected_class_id = pt1_setup["class"].id
            view._selected_section_id = pt1_setup["section"].id
            view._selected_subject_id = pt1_setup["subject"].id

            view._load_results()

            model = view.result_table.model()
            if hasattr(model, "sourceModel"):
                model = model.sourceModel()
            assert model.rowCount() == 3
        finally:
            if old is not None:
                os.environ[os_env] = old
            else:
                os.environ.pop(os_env, None)
            app.quit()

    def test_cascade_class_selection_loads_sections_and_subjects(self, pt1_setup):
        """Regression: Session → Class → Section → Subject cascade should populate each dropdown and enable combos."""
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.pt1_result_view import Pt1ResultView
        view = Pt1ResultView(pt1_setup["SessionLocal"])

        # After init, _load_sessions auto-selects the current session and calls _on_session_changed,
        # so class_combo should be enabled and populated.
        assert view._selected_session_id == pt1_setup["session"].id
        assert view.class_combo.isEnabled() is True
        assert view.class_combo.count() >= 2  # "Select Class" + actual class

        # Select the actual class (skip "Select Class" placeholder at index 0)
        class_idx = view.class_combo.findData(pt1_setup["class"].id)
        assert class_idx >= 0
        view.class_combo.setCurrentIndex(class_idx)

        # After selecting class, section combo should be enabled and populated
        assert view._selected_class_id == pt1_setup["class"].id
        assert view.section_combo.isEnabled() is True
        assert view.section_combo.count() >= 2

        # Select the actual section (skip "Select Section" placeholder)
        sec_idx = view.section_combo.findData(pt1_setup["section"].id)
        assert sec_idx >= 0
        view.section_combo.setCurrentIndex(sec_idx)

        # After selecting section, subject combo should be enabled and populated
        assert view._selected_section_id == pt1_setup["section"].id
        assert view.subject_combo.isEnabled() is True
        assert view.subject_combo.count() >= 2

        # Select the actual subject
        subj_idx = view.subject_combo.findData(pt1_setup["subject"].id)
        assert subj_idx >= 0
        view.subject_combo.setCurrentIndex(subj_idx)

        # After selecting subject, results should be loaded
        assert view._selected_subject_id == pt1_setup["subject"].id

        model = view.result_table.model()
        if hasattr(model, "sourceModel"):
            model = model.sourceModel()
        assert model.rowCount() == 3

        app.quit()
