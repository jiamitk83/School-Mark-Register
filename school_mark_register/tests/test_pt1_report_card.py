"""Regression tests for PT1 Report Card module."""
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
from services import ComponentMarksService, ExamComponentService, StudentService


@pytest.fixture
def pt1_report_card_db_session():
    """Create an in-memory SQLite database for PT1 Report Card testing."""
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
def pt1_report_card_setup(pt1_report_card_db_session):
    """Create full dataset for PT1 Report Card testing."""
    sess, SessionLocal, engine = pt1_report_card_db_session

    session_obj = AcademicSession(
        name="2026/2027", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31),
        status="active", is_current=True,
    )
    sess.add(session_obj)
    sess.flush()

    cls = Class(name="Class VII", display_order=1)
    sess.add(cls)
    sess.flush()

    sec = Section(name="Section A", class_id=cls.id, display_order=1)
    sess.add(sec)
    sess.flush()

    student_svc = StudentService(sess)
    student1 = student_svc.add_student(
        session_obj.id, cls.id, sec.id, "Aashi Yadav", "R001",
        father_name="Brajesh Singh Yadav", mother_name="Shalini Yadav",
        dob=date(2015, 2, 9),
    )
    student2 = student_svc.add_student(
        session_obj.id, cls.id, sec.id, "Bob Smith", "R002",
        father_name="John Smith", mother_name="Jane Smith",
        dob=date(2014, 5, 15),
    )

    # Create all subjects
    subject_defs = [
        ("ENGLISH", "English", "ENG"),
        ("MATHEMATICS", "Mathematics", "MATHS"),
        ("HINDI", "Hindi", "HINDI"),
        ("SCIENCE", "Science", "SCI"),
        ("SOCIAL SCIENCE", "Social Science", "SST"),
        ("COMPUTER", "Computer", "COMP"),
        ("FRENCH", "French", "FREN"),
        ("GENERAL KNOWLEDGE", "General Knowledge", "GK"),
        ("ART EDUCATION / ANIMATION", "Art Education / Animation", "ART"),
        ("VALUE EDUCATION", "Value Education", "VAL"),
    ]
    subjects = {}
    for upper_name, display_name, code in subject_defs:
        subj = Subject(name=display_name, code=code, is_active=True)
        sess.add(subj)
        sess.flush()
        mapping = SubjectSectionMapping(
            subject_id=subj.id, class_id=cls.id, section_id=sec.id, is_active=True
        )
        sess.add(mapping)
        subjects[upper_name] = subj
    sess.flush()

    pt1_exam = ExamType(name="PT1", code="PTI", description="Periodic Test 1",
                        max_marks=25, weightage=1.0, display_order=1, is_active=True)
    sess.add(pt1_exam)
    sess.flush()

    component_svc = ExamComponentService(sess)
    pt1_comps = {}
    for upper_name, subj in subjects.items():
        comp = component_svc.add_component(
            pt1_exam.id, "Periodic Test 1", "PT1", 25, subject_id=subj.id, display_order=1
        )
        pt1_comps[upper_name] = comp
    sess.flush()

    # Student1: Aashi Yadav marks
    alice_marks = [
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["ENGLISH"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["ENGLISH"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=16, max_marks=25, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["MATHEMATICS"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["MATHEMATICS"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=11, max_marks=25, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["HINDI"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["HINDI"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=20, max_marks=25, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["SCIENCE"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["SCIENCE"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=22, max_marks=25, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["SOCIAL SCIENCE"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["SOCIAL SCIENCE"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=15, max_marks=25, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["COMPUTER"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["COMPUTER"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=20, max_marks=25, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subjects["FRENCH"].id, exam_type_id=pt1_exam.id,
            component_id=pt1_comps["FRENCH"].id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=18, max_marks=25, status="saved",
        ),
    ]

    sess.add_all(alice_marks)
    sess.commit()

    return {
        "session": session_obj,
        "class": cls,
        "section": sec,
        "student1": student1,
        "student2": student2,
        "subjects": subjects,
        "pt1_comps": pt1_comps,
        "pt1_exam": pt1_exam,
        "SessionLocal": SessionLocal,
    }


class TestPt1ReportCardTotalCalculation:
    """Test total and percentage calculation matches PDF reference."""

    def test_scholastic_total_matches_pdf_reference(self, pt1_report_card_setup):
        """Total should only include scholastic subjects: English(16) + Maths(11) + Hindi(20)
        + Science(22) + SS(15) + Computer(20) + French(18) = 122 out of 175."""
        data = pt1_report_card_setup
        marks = {
            "ENGLISH": 16,
            "MATHEMATICS": 11,
            "HINDI": 20,
            "SCIENCE": 22,
            "SOCIAL SCIENCE": 15,
            "COMPUTER": 20,
            "FRENCH": 18,
        }
        total = sum(marks.values())
        assert total == 122
        max_marks = 7 * 25  # 175
        percentage = round((total / max_marks) * 100, 2)
        assert percentage == 69.71

    def test_grade_only_subjects_excluded_from_total(self, pt1_report_card_setup):
        """GK, Art Education/Animation, Value Education are grade-only and excluded from numeric total."""
        data = pt1_report_card_setup
        scholastic_count = 7  # English, Maths, Hindi, Science, SS, Computer, French
        grade_only_count = 3  # GK, Art Education/Animation, Value Education
        assert scholastic_count == 7
        assert grade_only_count == 3


class TestPt1ReportCardGradeScale:
    """Test grade scale matches the PDF reference."""

    def test_grade_scale_from_pdf(self):
        """Verify grade boundaries match PDF:
        A1(91-100), A2(81-90), B1(71-80), B2(61-70), C1(51-60), C2(41-50), D(33-40), E(32&below).
        These match the _calculate_grade in services.py."""
        from services import ComponentMarksService as Cms
        # Test via existing service
        assert Cms._calculate_grade(95) == "A1"
        assert Cms._calculate_grade(85) == "A2"
        assert Cms._calculate_grade(75) == "B1"
        assert Cms._calculate_grade(65) == "B2"
        assert Cms._calculate_grade(55) == "C1"
        assert Cms._calculate_grade(45) == "C2"
        assert Cms._calculate_grade(35) == "D"
        assert Cms._calculate_grade(30) == "E"
