"""Regression tests for Half Yearly Results student loading and result summaries."""
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
)


@pytest.fixture
def hy_result_db():
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
        bob = student_svc.add_student(
            session_obj.id, cls.id, sec.id, "Bob Smith", "R002"
        )
        charlie = student_svc.add_student(
            session_obj.id, cls.id, sec.id, "Charlie Brown", "R003"
        )
        sess.flush()

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

        # Get the exam types created by session initialization
        hy_exam = exam_svc.repo.get_by_name("Half Yearly")
        pt1_exam = exam_svc.repo.get_by_name("PT1")

        # Add Half Yearly components for English and Maths
        for subj in [english, maths]:
            # PT1 component (25 max) - source for auto-population
            comp_svc.add_component(
                pt1_exam.id, "Periodic Test 1", "PT1", 25,
                subject_id=subj.id, display_order=1
            )
            # Half Yearly components (PT1=5, MA=5, SE=5, PF=5, WE=80)
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
            "bob": bob,
            "charlie": charlie,
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


class TestHalfYearlyResultsStudentLoading:
    """Tests for Half Yearly Results student loading and result summaries."""

    def test_all_students_load_even_with_pending_marks(self, hy_result_db):
        """All students in section must appear in results, even if all Half Yearly marks are pending."""
        d = hy_result_db
        SessionLocal = d["SessionLocal"]
        sess = SessionLocal()
        svc = ComponentMarksService(sess)
        try:
            results = svc.get_half_yearly_result_summary(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )

            assert len(results) == 3, "All 3 students should appear"
            names = {r["name"] for r in results}
            assert names == {"Alice Johnson", "Bob Smith", "Charlie Brown"}

            # All should have pending status since no marks entered
            for r in results:
                assert r["status"] == "pending"
                assert r["obtained_marks"] is None
                assert r["percentage"] is None
                assert r["grade"] is None
                assert r["max_marks"] == 100  # 5+5+5+5+80
        finally:
            sess.close()

    def test_students_with_saved_marks_show_correct_results(self, hy_result_db):
        """Students with saved Half Yearly marks should show correct totals and grades."""
        d = hy_result_db
        SessionLocal = d["SessionLocal"]
        sess = SessionLocal()
        svc = ComponentMarksService(sess)
        try:
            # Get Half Yearly components for English
            hy_comps = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["english"].id
            )
            hy_comps_by_code = {c.code: c for c in hy_comps}

            # Add saved marks for Alice in English (all components)
            alice_marks = {
                "PT1": 4, "MA": 5, "SE": 5, "PF": 5, "WE": 60
            }  # Total: 79/100 = 79% -> B1
            for code, marks in alice_marks.items():
                comp = hy_comps_by_code[code]
                cm = ComponentMarks(
                    student_id=d["alice"].id,
                    subject_id=d["english"].id,
                    exam_type_id=d["hy_exam"].id,
                    component_id=comp.id,
                    session_id=d["session"].id,
                    class_id=d["class"].id,
                    section_id=d["section"].id,
                    marks_obtained=marks,
                    max_marks=comp.max_marks,
                    status="saved",
                )
                svc.repo.add(cm)
            sess.commit()

            # Bob: only partial marks (pending overall)
            bob_marks = {
                "PT1": 3, "MA": 4
            }
            for code, marks in bob_marks.items():
                comp = hy_comps_by_code[code]
                cm = ComponentMarks(
                    student_id=d["bob"].id,
                    subject_id=d["english"].id,
                    exam_type_id=d["hy_exam"].id,
                    component_id=comp.id,
                    session_id=d["session"].id,
                    class_id=d["class"].id,
                    section_id=d["section"].id,
                    marks_obtained=marks,
                    max_marks=comp.max_marks,
                    status="saved",
                )
                svc.repo.add(cm)
            sess.commit()

            results = svc.get_half_yearly_result_summary(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )

            assert len(results) == 3

            # Alice: all marks saved -> should show total
            alice_result = next(r for r in results if r["name"] == "Alice Johnson")
            assert alice_result["status"] == "saved"
            assert alice_result["obtained_marks"] == 79
            assert alice_result["max_marks"] == 100
            assert alice_result["percentage"] == 79.0
            assert alice_result["grade"] == "B1"

            # Bob: partial marks -> pending
            bob_result = next(r for r in results if r["name"] == "Bob Smith")
            assert bob_result["status"] == "pending"
            assert bob_result["obtained_marks"] is None
            assert bob_result["percentage"] is None

            # Charlie: no marks -> pending
            charlie_result = next(r for r in results if r["name"] == "Charlie Brown")
            assert charlie_result["status"] == "pending"
            assert charlie_result["obtained_marks"] is None
        finally:
            sess.close()

    def test_absent_status_preserved(self, hy_result_db):
        """Students marked absent in any component should show absent status."""
        d = hy_result_db
        SessionLocal = d["SessionLocal"]
        sess = SessionLocal()
        svc = ComponentMarksService(sess)
        try:
            hy_comps = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["english"].id
            )
            hy_comps_by_code = {c.code: c for c in hy_comps}

            # Mark Bob absent in Written Exam
            comp = hy_comps_by_code["WE"]
            cm = ComponentMarks(
                student_id=d["bob"].id,
                subject_id=d["english"].id,
                exam_type_id=d["hy_exam"].id,
                component_id=comp.id,
                session_id=d["session"].id,
                class_id=d["class"].id,
                section_id=d["section"].id,
                marks_obtained=None,
                max_marks=comp.max_marks,
                status="absent",
            )
            svc.repo.add(cm)
            sess.commit()

            results = svc.get_half_yearly_result_summary(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )

            bob_result = next(r for r in results if r["name"] == "Bob Smith")
            assert bob_result["status"] == "absent"
            assert bob_result["obtained_marks"] is None
            assert bob_result["percentage"] is None
            assert bob_result["grade"] is None
        finally:
            sess.close()

    def test_csv_export_includes_all_students(self, hy_result_db):
        """CSV export must include all students even with pending marks."""
        d = hy_result_db
        SessionLocal = d["SessionLocal"]
        sess = SessionLocal()
        svc = ComponentMarksService(sess)
        try:
            csv_content = svc.export_half_yearly_results_to_csv(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )

            lines = csv_content.strip().split("\n")
            assert len(lines) == 4  # header + 3 students
            assert "Roll Number" in lines[0]
            assert "Alice Johnson" in lines[1]
            assert "Bob Smith" in lines[2]
            assert "Charlie Brown" in lines[3]
            # All should show pending
            assert "pending" in lines[1] and "pending" in lines[2] and "pending" in lines[3]
        finally:
            sess.close()

    def test_multiple_subjects_work_independently(self, hy_result_db):
        """Results for English and Maths should be independent."""
        d = hy_result_db
        SessionLocal = d["SessionLocal"]
        sess = SessionLocal()
        svc = ComponentMarksService(sess)
        try:
            hy_comps_eng = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["english"].id
            )
            hy_comps_maths = svc.component_repo.get_by_exam_type_and_subject(
                d["hy_exam"].id, d["maths"].id
            )
            hy_comps_eng_by_code = {c.code: c for c in hy_comps_eng}

            # Add saved marks for Alice in English only
            alice_marks_eng = {
                "PT1": 4, "MA": 5, "SE": 5, "PF": 5, "WE": 60
            }
            for code, marks in alice_marks_eng.items():
                comp = hy_comps_eng_by_code[code]
                cm = ComponentMarks(
                    student_id=d["alice"].id,
                    subject_id=d["english"].id,
                    exam_type_id=d["hy_exam"].id,
                    component_id=comp.id,
                    session_id=d["session"].id,
                    class_id=d["class"].id,
                    section_id=d["section"].id,
                    marks_obtained=marks,
                    max_marks=comp.max_marks,
                    status="saved",
                )
                svc.repo.add(cm)
            sess.commit()

            # English should show Alice as saved
            eng_results = svc.get_half_yearly_result_summary(
                d["session"].id, d["class"].id, d["section"].id, d["english"].id
            )
            alice_eng = next(r for r in eng_results if r["name"] == "Alice Johnson")
            assert alice_eng["status"] == "saved"
            assert alice_eng["obtained_marks"] == 79

            # Maths should show Alice as pending (no marks entered)
            maths_results = svc.get_half_yearly_result_summary(
                d["session"].id, d["class"].id, d["section"].id, d["maths"].id
            )
            alice_maths = next(r for r in maths_results if r["name"] == "Alice Johnson")
            assert alice_maths["status"] == "pending"
            assert alice_maths["obtained_marks"] is None
        finally:
            sess.close()
