"""Tests for Half Yearly Result view dropdown cascade (regression test)."""
from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def hy_qt_app():
    """Ensure QApplication runs in offscreen mode for headless Qt tests."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


@pytest.fixture
def hy_view_app(hy_qt_app):
    """Build a fresh HalfYearlyResultView with a populated DB (session + class + section)."""
    from database import Base, SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from datetime import date
    from models import (
        AcademicSession,
        Class,
        Section,
        Subject,
        SubjectSectionMapping,
    )
    from services import StudentService

    import tempfile
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sess = _SessionLocal()

    try:
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

        student_svc = StudentService(sess)
        student_svc.add_student(session_obj.id, cls.id, sec.id, "Alice Johnson", "R001")
        student_svc.add_student(session_obj.id, cls.id, sec.id, "Bob Smith", "R002")

        subject_eng = Subject(name="English", code="ENG", is_active=True)
        sess.add(subject_eng)
        sess.flush()

        mapping = SubjectSectionMapping(
            subject_id=subject_eng.id, class_id=cls.id, section_id=sec.id, is_active=True
        )
        sess.add(mapping)
        sess.flush()

        # No Half Yearly components needed just for cascade testing

        sess.commit()

        from ui.half_yearly_result_view import HalfYearlyResultView
        view = HalfYearlyResultView(_SessionLocal)

        yield view, session_obj, cls, sec, _SessionLocal

    finally:
        sess.close()
        engine.dispose()
        os.unlink(db_path)


@pytest.fixture
def hy_two_class_app(hy_qt_app):
    """Build a HalfYearlyResultView with two classes, each with two sections."""
    from database import Base, SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from datetime import date
    from models import (
        AcademicSession,
        Class,
        Section,
    )

    import tempfile
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sess = _SessionLocal()

    try:
        session_obj = AcademicSession(
            name="2026/2027", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31),
            status="active", is_current=True,
        )
        sess.add(session_obj)
        sess.flush()

        cls_A = Class(name="Class A", display_order=1)
        cls_B = Class(name="Class B", display_order=2)
        sess.add_all([cls_A, cls_B])
        sess.flush()

        sec_A1 = Section(name="Section A1", class_id=cls_A.id, display_order=1)
        sec_A2 = Section(name="Section A2", class_id=cls_A.id, display_order=2)
        sec_B1 = Section(name="Section B1", class_id=cls_B.id, display_order=1)
        sec_B2 = Section(name="Section B2", class_id=cls_B.id, display_order=2)
        sess.add_all([sec_A1, sec_A2, sec_B1, sec_B2])
        sess.commit()

        from ui.half_yearly_result_view import HalfYearlyResultView
        view = HalfYearlyResultView(_SessionLocal)

        yield view, session_obj, cls_A, cls_B, sec_A1, sec_A2, sec_B1, sec_B2

    finally:
        sess.close()
        engine.dispose()
        os.unlink(db_path)


@pytest.fixture
def hy_subjects_app(hy_qt_app):
    """Build a HalfYearlyResultView with Half Yearly exam type,
    component linked to a subject, so subject cascade can be tested."""
    from database import Base, SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from datetime import date
    from models import (
        AcademicSession,
        Class,
        Section,
        Subject,
        SubjectSectionMapping,
        ExamType,
        ExamComponent,
    )

    import tempfile
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sess = _SessionLocal()

    try:
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

        subject_eng = Subject(name="English", code="ENG", is_active=True)
        subject_math = Subject(name="Math", code="MATH", is_active=True)
        sess.add_all([subject_eng, subject_math])
        sess.flush()

        mapping = SubjectSectionMapping(
            subject_id=subject_eng.id, class_id=cls.id, section_id=sec.id, is_active=True
        )
        sess.add(mapping)

        hy_exam_type = ExamType(name="Half Yearly", code="HY", max_marks=100, is_active=True)
        sess.add(hy_exam_type)
        sess.flush()

        comp_eng = ExamComponent(
            exam_type_id=hy_exam_type.id, subject_id=subject_eng.id,
            name="Eng Theory", code="ENG_THEORY", max_marks=80, display_order=1,
        )
        comp_math = ExamComponent(
            exam_type_id=hy_exam_type.id, subject_id=subject_math.id,
            name="Math Theory", code="MATH_THEORY", max_marks=80, display_order=1,
        )
        sess.add_all([comp_eng, comp_math])
        sess.flush()

        sess.commit()

        from ui.half_yearly_result_view import HalfYearlyResultView
        view = HalfYearlyResultView(_SessionLocal)

        yield view, session_obj, cls, sec, subject_eng, subject_math, _SessionLocal

    finally:
        sess.close()
        engine.dispose()
        os.unlink(db_path)


class TestHalfYearlyResultViewCascade:
    """Regression: Session → Class → Section → Subject cascade should
    populate each dropdown and enable combos in the Half Yearly Result view."""

    def test_session_selection_loads_classes(self, hy_view_app):
        """Selecting a session should load and enable the Class dropdown."""
        view, session_obj, cls, sec, SessionLocal = hy_view_app

        # After init, _load_sessions auto-selects the current session and
        # should call _on_session_changed(), so class_combo should be enabled
        # and populated.
        assert view._selected_session_id == session_obj.id, (
            "Session ID should be set after _load_sessions calls _on_session_changed"
        )
        assert view.class_combo.isEnabled() is True, (
            "Class dropdown should be enabled after session selection"
        )
        assert view.class_combo.count() >= 2, (
            "Class dropdown should have 'Select Class' + at least one class"
        )

    def test_class_selection_loads_sections(self, hy_view_app):
        """Selecting a class should refresh the Section dropdown."""
        view, session_obj, cls, sec, SessionLocal = hy_view_app

        # Session cascade should already have run during init
        assert view._selected_session_id == session_obj.id
        assert view.class_combo.isEnabled()

        # Select the actual class
        class_idx = view.class_combo.findData(cls.id)
        assert class_idx >= 1, "Actual class should be in dropdown after session selection"
        view.class_combo.setCurrentIndex(class_idx)

        # After selecting class, section combo should be enabled and populated
        assert view._selected_class_id == cls.id, (
            "Class ID should be stored after class selection"
        )
        assert view.section_combo.isEnabled() is True, (
            "Section dropdown should be enabled after class selection"
        )
        assert view.section_combo.count() >= 2, (
            "Section dropdown should have 'Select Section' + at least one section"
        )

    def test_class_selection_filters_sections_by_class(self, hy_two_class_app):
        """Selecting a class should show only sections belonging to that class."""
        view, session_obj, cls_A, cls_B, sec_A1, sec_A2, sec_B1, sec_B2 = hy_two_class_app

        assert view._selected_session_id == session_obj.id

        # Select Class A
        idx_A = view.class_combo.findData(cls_A.id)
        assert idx_A >= 1
        view.class_combo.setCurrentIndex(idx_A)

        # Sections should be only A1 and A2 (plus "Select Section")
        section_names = []
        for i in range(1, view.section_combo.count()):
            section_names.append(view.section_combo.itemText(i))
        assert set(section_names) == {"Section A1", "Section A2"}, (
            f"Expected only Class A sections, got {section_names}"
        )

        # Select Class B
        idx_B = view.class_combo.findData(cls_B.id)
        assert idx_B >= 1
        view.class_combo.setCurrentIndex(idx_B)

        # Sections should be only B1 and B2 (plus "Select Section")
        section_names = []
        for i in range(1, view.section_combo.count()):
            section_names.append(view.section_combo.itemText(i))
        assert set(section_names) == {"Section B1", "Section B2"}, (
            f"Expected only Class B sections, got {section_names}"
        )

    def test_section_selection_loads_subjects(self, hy_subjects_app):
        """Selecting a section should populate the Subject dropdown with
        subjects that have Half Yearly components."""
        view, session_obj, cls, sec, subject_eng, subject_math, SessionLocal = hy_subjects_app

        # Ensure session cascade runs
        view._load_sessions()

        # After init, _load_sessions auto-selects the current session and
        # should call _on_session_changed(), so class_combo should be enabled
        assert view._selected_session_id == session_obj.id, (
            "Session ID should be set after _load_sessions calls _on_session_changed"
        )
        assert view.class_combo.isEnabled(), (
            "Class dropdown should be enabled after session selection"
        )

        # Select class
        class_idx = view.class_combo.findData(cls.id)
        assert class_idx >= 1
        view.class_combo.setCurrentIndex(class_idx)

        # Select section
        section_idx = view.section_combo.findData(sec.id)
        assert section_idx >= 1
        view.section_combo.setCurrentIndex(section_idx)

        assert view._selected_section_id == sec.id, (
            "Section ID should be stored after section selection"
        )
        assert view.subject_combo.isEnabled() is True, (
            "Subject dropdown should be enabled after section selection"
        )
        assert view.subject_combo.count() >= 2, (
            "Subject dropdown should have 'Select Subject' + at least one subject"
        )

        subject_names = []
        for i in range(1, view.subject_combo.count()):
            subject_names.append(view.subject_combo.itemText(i))
        assert set(subject_names) == {"English", "Math"}, (
            f"Expected English and Math subjects with Half Yearly components, got {subject_names}"
        )