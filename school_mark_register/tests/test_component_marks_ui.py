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
from repositories import ComponentMarksRepository, ExamComponentRepository
from services import (
    ComponentMarksService,
    ExamComponentService,
    ExamTypeService,
    SubjectService,
)


@pytest.fixture
def ui_db_session():
    """Create an in-memory SQLite database for UI testing."""
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
def ui_setup_data(ui_db_session):
    """Create full dataset: session, class, section, students, subject, exam type, components."""
    sess, SessionLocal, engine = ui_db_session

    from services import SessionService, ClassService, SectionService, StudentService

    session_svc = SessionService(sess)
    session_obj = session_svc.add_session(
        "2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True
    )

    class_svc = ClassService(sess)
    cls = class_svc.add_class("Class 1")

    section_svc = SectionService(sess)
    sec = section_svc.add_section(cls.id, "Section A")

    student_svc = StudentService(sess)
    student = student_svc.add_student(
        session_obj.id, cls.id, sec.id, "Alice Johnson", "R001"
    )
    student2 = student_svc.add_student(
        session_obj.id, cls.id, sec.id, "Bob Smith", "R002"
    )

    subject = Subject(name="English", code="ENG", is_active=True)
    sess.add(subject)
    sess.flush()

    # Create subject-section mapping so SubjectService can find subjects for class+section
    mapping = SubjectSectionMapping(
        subject_id=subject.id, class_id=cls.id, section_id=sec.id, is_active=True
    )
    sess.add(mapping)
    sess.flush()

    exam_type_svc = ExamTypeService(sess)
    exam_type = exam_type_svc.add_exam_type(
        "Midterm", "MT", max_marks=100, weightage=0.5
    )

    # Create components for this exam type + subject
    component_svc = ExamComponentService(sess)
    comp1 = component_svc.add_component(
        exam_type.id, "Theory", "THEORY", 80, subject_id=subject.id, display_order=1
    )
    comp2 = component_svc.add_component(
        exam_type.id, "Practical", "PRAC", 20, subject_id=subject.id, display_order=2
    )

    return {
        "session": session_obj,
        "class": cls,
        "section": sec,
        "student": student,
        "student2": student2,
        "subject": subject,
        "exam_type": exam_type,
        "component1": comp1,
        "component2": comp2,
        "SessionLocal": SessionLocal,
    }


# ========================================================================
# Tests: get_subjects_for_class_section on SubjectService
# ========================================================================


class TestSubjectServiceGetSubjectsForClassSection:
    """Tests for SubjectService.get_subjects_for_class_section()."""

    def test_get_subjects_returns_mapped_subject(self, ui_setup_data):
        """SubjectService.get_subjects_for_class_section should return subjects mapped to class+section."""
        d = ui_setup_data
        sess2 = d["SessionLocal"]()
        svc = SubjectService(sess2)
        try:
            subjects = svc.get_subjects_for_class_section(d["class"].id, d["section"].id)
            assert len(subjects) == 1
            assert subjects[0].name == "English"
            assert subjects[0].code == "ENG"
        finally:
            sess2.close()

    def test_get_subjects_excludes_unmapped(self, ui_setup_data):
        """Subjects not mapped to the class+section should not be returned."""
        d = ui_setup_data

        # Add an unmapped subject using a fresh session
        sess2 = d["SessionLocal"]()
        svc = SubjectService(sess2)
        try:
            unmapped_subject = Subject(name="Physics", code="PHY", is_active=True)
            sess2.add(unmapped_subject)
            sess2.flush()

            subjects = svc.get_subjects_for_class_section(d["class"].id, d["section"].id)
            assert len(subjects) == 1
            assert subjects[0].name == "English"
        finally:
            sess2.close()


# ========================================================================
# Tests: ComponentMarksService.discard_component_marks
# ========================================================================


class TestComponentMarksServiceDiscardComponentMarks:
    """Tests for ComponentMarksService.discard_component_marks()."""

    def test_discard_existing_returns_true(self, ui_setup_data):
        """discard_component_marks should return True and delete the record."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # Create a component marks record
            marks = ComponentMarks(
                student_id=d["student"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component1"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=50,
                max_marks=d["component1"].max_marks,
                status="pending",
            )
            sess.add(marks)
            sess.flush()
            marks_id = marks.id

            result = svc.discard_component_marks(d["student"].id, d["component1"].id)
            assert result is True

            # Verify deleted
            deleted = sess.get(ComponentMarks, marks_id)
            assert deleted is None
        finally:
            sess.close()

    def test_discard_nonexistent_returns_false(self, ui_setup_data):
        """discard_component_marks should return False if no record exists."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            result = svc.discard_component_marks(d["student"].id, d["component1"].id)
            assert result is False
        finally:
            sess.close()


# ========================================================================
# Tests: ComponentMarksService.discard_all_drafts
# ========================================================================


class TestComponentMarksServiceDiscardAllDrafts:
    """Tests for ComponentMarksService.discard_all_drafts()."""

    def test_discard_all_pending_only(self, ui_setup_data):
        """discard_all_drafts should only delete records with status='pending'."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            # Create pending marks
            pending_marks1 = ComponentMarks(
                student_id=d["student"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component1"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=50,
                max_marks=80,
                status="pending",
            )
            pending_marks2 = ComponentMarks(
                student_id=d["student2"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component1"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=60,
                max_marks=80,
                status="pending",
            )
            # Create saved marks (should not be deleted)
            saved_marks = ComponentMarks(
                student_id=d["student"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component2"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=20,
                max_marks=20,
                status="saved",
            )
            sess.add_all([pending_marks1, pending_marks2, saved_marks])
            sess.flush()

            count = svc.discard_all_drafts(
                d["session"].id,
                d["class"].id,
                d["section"].id,
                d["exam_type"].id,
            )
            assert count == 2

            # Verify saved marks still exist
            remaining = sess.query(ComponentMarks).all()
            assert len(remaining) == 1
            assert remaining[0].status == "saved"
        finally:
            sess.close()

    def test_discard_all_no_drafts_returns_zero(self, ui_setup_data):
        """discard_all_drafts should return 0 if no pending records exist."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            count = svc.discard_all_drafts(
                d["session"].id,
                d["class"].id,
                d["section"].id,
                d["exam_type"].id,
            )
            assert count == 0
        finally:
            sess.close()


# ========================================================================
# Tests: ComponentMarksService.promote_drafts_to_marks
# ========================================================================


class TestComponentMarksServicePromoteDrafts:
    """Tests for ComponentMarksService.promote_drafts_to_marks()."""

    def test_promote_pending_to_saved(self, ui_setup_data):
        """promote_drafts_to_marks should change status from 'pending' to 'saved'."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            pending_marks = ComponentMarks(
                student_id=d["student"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component1"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=50,
                max_marks=80,
                status="pending",
            )
            sess.add(pending_marks)
            sess.flush()

            count = svc.promote_drafts_to_marks(
                d["session"].id,
                d["class"].id,
                d["section"].id,
                d["exam_type"].id,
            )
            assert count == 1
            assert pending_marks.status == "saved"
        finally:
            sess.close()

    def test_promote_skips_saved_and_locked(self, ui_setup_data):
        """promote_drafts_to_marks should only promote 'pending' records."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            pending = ComponentMarks(
                student_id=d["student"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component1"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=50,
                max_marks=80,
                status="pending",
            )
            saved = ComponentMarks(
                student_id=d["student2"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component1"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=40,
                max_marks=80,
                status="saved",
            )
            locked = ComponentMarks(
                student_id=d["student"].id,
                subject_id=d["subject"].id,
                exam_type_id=d["exam_type"].id,
                component_id=d["component2"].id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=10,
                max_marks=20,
                status="locked",
            )
            sess.add_all([pending, saved, locked])
            sess.flush()

            count = svc.promote_drafts_to_marks(
                d["session"].id,
                d["class"].id,
                d["section"].id,
                d["exam_type"].id,
            )
            assert count == 1
            assert pending.status == "saved"
            assert saved.status == "saved"  # unchanged
            assert locked.status == "locked"  # unchanged
        finally:
            sess.close()

    def test_promote_no_drafts_returns_zero(self, ui_setup_data):
        """promote_drafts_to_marks should return 0 if no pending records."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            count = svc.promote_drafts_to_marks(
                d["session"].id,
                d["class"].id,
                d["section"].id,
                d["exam_type"].id,
            )
            assert count == 0
        finally:
            sess.close()


# ========================================================================
# Tests: save_component_marks with "pending" status (not "draft")
# ========================================================================


class TestComponentMarksServiceSavePending:
    """Tests that ComponentMarksService.save_component_marks accepts 'pending' status but rejects 'draft'."""

    def test_save_with_pending_status(self, ui_setup_data):
        """save_component_marks should accept status='pending'."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            marks = svc.save_component_marks(
                d["student"].id,
                d["component1"].id,
                45,
                status="pending",
            )
            assert marks.status == "pending"
            assert marks.marks_obtained == 45
        finally:
            sess.close()

    def test_save_with_saved_status(self, ui_setup_data):
        """save_component_marks should accept status='saved'."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            marks = svc.save_component_marks(
                d["student"].id,
                d["component1"].id,
                75,
                status="saved",
            )
            assert marks.status == "saved"
            assert marks.marks_obtained == 75
        finally:
            sess.close()

    def test_save_with_absent_status(self, ui_setup_data):
        """save_component_marks should accept status='absent' with None marks."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            marks = svc.save_component_marks(
                d["student"].id,
                d["component1"].id,
                None,
                status="absent",
            )
            assert marks.status == "absent"
            assert marks.marks_obtained is None
        finally:
            sess.close()

    def test_save_rejects_draft_status(self, ui_setup_data):
        """save_component_marks should reject status='draft' (invalid for ComponentMarks)."""
        d = ui_setup_data
        sess = d["SessionLocal"]()
        svc = ComponentMarksService(sess)
        try:
            with pytest.raises(ValueError, match="Invalid status"):
                svc.save_component_marks(
                    d["student"].id,
                    d["component1"].id,
                    45,
                    status="draft",
                )
        finally:
            sess.close()


# ========================================================================
# Tests: MarksView app startup and grid loading
# ========================================================================


class TestMarksViewStartup:
    """Tests for MarksView UI startup and component grid loading."""

    def test_app_startup_with_marks_view(self, ui_setup_data):
        """Test that MainWindow with MarksView starts successfully."""
        import os
        import sys
        import tempfile

        from sqlalchemy.orm import sessionmaker
        from PySide6.QtWidgets import QApplication

        # Use offscreen platform to avoid display issues in CI
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)

        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        app = QApplication.instance() or QApplication(sys.argv)

        try:
            from ui.main_window import MainWindow

            win = MainWindow(SessionLocal)
            win.show()
            app.processEvents()

            # Verify marks_view was created
            assert win.marks_view is not None
            assert win.marks_view.save_all_btn is not None
            assert win.marks_view.save_draft_btn is not None
            assert win.marks_view.promote_btn is not None
            assert win.marks_view.recover_btn is not None
            assert win.marks_view.discard_all_btn is not None
        finally:
            win.deleteLater()
            app.processEvents()
            SessionLocal.close_all()
            engine.dispose()
            app.quit()
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_marks_view_has_no_duplicate_filter_students(self, ui_setup_data):
        """Verify that _filter_students is defined only once."""
        from ui.marks_view import MarksView
        import inspect

        methods = list(inspect.getmembers(MarksView, predicate=inspect.isfunction))
        filter_methods = [m for m in methods if m[0] == "_filter_students"]
        assert len(filter_methods) == 1

    def test_marks_view_has_refresh_method(self, ui_setup_data):
        """Verify that the refresh method exists."""
        from ui.marks_view import MarksView

        assert hasattr(MarksView, "refresh")
        assert callable(getattr(MarksView, "refresh"))


# ========================================================================
# Tests: Marks Entry cascade loading (Session → Class → Section → Exam Type → Subject)
# ========================================================================


class TestMarksEntryCascadeLoading:
    """Regression tests: students must load after selecting the full cascade."""

    def test_subjects_load_after_exam_type_selection(self, ui_setup_data):
        """get_subjects_for_class_section must return subjects for the selected class+section.

        This is the root cause: SubjectService was missing get_subjects_for_class_section,
        preventing subjects (and then students) from loading.
        """
        d = ui_setup_data
        sess2 = d["SessionLocal"]()
        svc = SubjectService(sess2)
        try:
            subjects = svc.get_subjects_for_class_section(d["class"].id, d["section"].id)
            assert len(subjects) >= 1
            assert d["subject"].name in [s.name for s in subjects]
        finally:
            sess2.close()

    def test_students_load_after_subject_selection(self, ui_setup_data):
        """Students must be returned by list_active_by_section for the selected class+section."""
        d = ui_setup_data
        sess2 = d["SessionLocal"]()
        svc = ComponentMarksService(sess2)
        try:
            students = svc.student_repo.list_active_by_section(
                d["session"].id, d["class"].id, d["section"].id
            )
            assert len(students) == 2  # Alice and Bob
            names = [s.name for s in students]
            assert "Alice Johnson" in names
            assert "Bob Smith" in names
        finally:
            sess2.close()

    def test_students_with_no_marks_still_load(self, ui_setup_data):
        """Students with no existing component marks should still appear in the grid."""
        d = ui_setup_data
        sess2 = d["SessionLocal"]()
        svc = ComponentMarksService(sess2)
        try:
            students = svc.student_repo.list_active_by_section(
                d["session"].id, d["class"].id, d["section"].id
            )
            # Bob Smith has no marks - should still be listed
            student_ids = [s.id for s in students]
            assert d["student"].id in student_ids
            assert d["student2"].id in student_ids

            # Verify no marks exist for student2 yet
            existing = svc.repo.list_by_section_exam(
                d["session"].id, d["class"].id, d["section"].id, d["exam_type"].id
            )
            assert all(m.student_id == d["student"].id for m in existing)
        finally:
            sess2.close()

    def test_component_grid_loads_all_students_with_components(self, ui_setup_data):
        """The component grid should load all students and all components for the selected subject."""
        d = ui_setup_data
        sess2 = d["SessionLocal"]()
        svc = ComponentMarksService(sess2)
        try:
            students = svc.student_repo.list_active_by_section(
                d["session"].id, d["class"].id, d["section"].id
            )
            components = svc.component_repo.get_by_exam_type_and_subject(
                d["exam_type"].id, d["subject"].id
            )
            assert len(students) == 2
            assert len(components) == 2  # Theory + Practical
            assert components[0].name == "Theory"
            assert components[1].name == "Practical"
        finally:
            sess2.close()

    def test_on_cell_changed_does_not_raise_keyerror(self, ui_setup_data):
        """_on_cell_changed must not raise KeyError when itemChanged fires during grid population.

        This is a regression test for the bug where setItem triggered itemChanged
        before _component_marks_data was populated, causing KeyError.
        """
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        import sys
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication(sys.argv)

        d = ui_setup_data
        SessionLocal = d["SessionLocal"]

        from ui.marks_view import MarksView
        mv = MarksView(SessionLocal)

        # Directly set the selection state and call _load_component_grid
        mv._selected_session_id = d["session"].id
        mv._selected_class_id = d["class"].id
        mv._selected_section_id = d["section"].id
        mv._selected_exam_type_id = d["exam_type"].id
        mv._selected_subject_id = d["subject"].id
        mv._load_component_grid()

        # The grid should have loaded with component marks data
        assert len(mv._component_marks_data) > 0

        # Trigger cell change on an existing cell - should NOT raise KeyError
        first_key = list(mv._component_marks_data.keys())[0]
        for col in range(2, mv.marks_table.columnCount()):
            item = mv.marks_table.item(0, col)
            if item and item.data(Qt.ItemDataRole.UserRole) == first_key:
                # Set empty text (triggers the "not text" path)
                mv.marks_table.blockSignals(False)
                item.setText("")
                # _on_cell_changed should handle this gracefully
                mv._on_cell_changed(item)

                # Set valid text
                item.setText("42")
                mv._on_cell_changed(item)
                break


# ========================================================================
# Tests: PT1 component configuration (regression for students-not-loading bug)
# ========================================================================


class TestPT1ComponentConfig:
    """Regression tests: PT1 exam type must have components for all subject categories."""

    def test_pt1_has_components_for_core_subjects(self, ui_setup_data):
        """PT1 exam type must have a component configured for core subjects."""
        from repositories import ExamComponentRepository
        from database import _ensure_pt1_pt2_components
        d = ui_setup_data
        sess2 = d["SessionLocal"]()
        # Run migration to create PT1/PT2 components
        _ensure_pt1_pt2_components(sess2)
        comp_repo = ExamComponentRepository(sess2)
        try:
            # Get PT1 exam type
            pt1 = sess2.query(ExamType).filter_by(name="PT1").first()
            assert pt1 is not None
            assert pt1.max_marks == 25

            comps = comp_repo.get_by_exam_type_and_subject(pt1.id, d["subject"].id)
            assert len(comps) == 1
            assert comps[0].name == "Periodic Test 1"
            assert comps[0].code == "PT1"
            assert comps[0].max_marks == 25
        finally:
            sess2.close()

    def test_pt1_has_components_after_migration(self, ui_setup_data):
        """After init_database() migration, PT1 must have components for all subjects."""
        import os, tempfile
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, init_database, _ensure_pt1_pt2_components

        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        SessionLocal2 = sessionmaker(bind=engine)

        try:
            sess = SessionLocal2()
            # Create session, subjects
            from services import SessionService
            sess_svc = SessionService(sess)
            sess_svc.add_session("2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True)

            subjects = [
                Subject(name="English", code="ENG"),
                Subject(name="Computer", code="COMP"),
                Subject(name="French", code="FR"),
                Subject(name="GK", code="GK"),
            ]
            for s in subjects:
                sess.add(s)
            sess.flush()
            sess.commit()

            # Run the migration
            created = _ensure_pt1_pt2_components(sess)
            assert created > 0

            # Verify PT1 has components for each subject
            pt1 = sess.query(ExamType).filter_by(name="PT1").first()
            pt2 = sess.query(ExamType).filter_by(name="PT2").first()
            comp_repo = ExamComponentRepository(sess)

            for subj in subjects:
                pt1_comps = comp_repo.get_by_exam_type_and_subject(pt1.id, subj.id)
                pt2_comps = comp_repo.get_by_exam_type_and_subject(pt2.id, subj.id)
                assert len(pt1_comps) >= 1, f"PT1 has no components for {subj.name}"
                assert len(pt2_comps) >= 1, f"PT2 has no components for {subj.name}"
        finally:
            sess.close()
            engine.dispose()
            os.unlink(db_path)

    def test_pt1_migration_is_idempotent(self, ui_setup_data):
        """Running the migration twice should not create duplicate components."""
        import os, tempfile
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, _ensure_pt1_pt2_components

        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        SessionLocal2 = sessionmaker(bind=engine)

        try:
            sess = SessionLocal2()
            from services import SessionService
            sess_svc = SessionService(sess)
            sess_svc.add_session("2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True)

            subject = Subject(name="English", code="ENG", is_active=True)
            sess.add(subject)
            sess.flush()
            sess.commit()

            # Run migration twice
            created1 = _ensure_pt1_pt2_components(sess)
            created2 = _ensure_pt1_pt2_components(sess)

            assert created1 > 0
            assert created2 == 0  # second run should create nothing
        finally:
            sess.close()
            engine.dispose()
            os.unlink(db_path)



