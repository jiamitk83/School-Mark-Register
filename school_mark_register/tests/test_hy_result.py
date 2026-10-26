"""Tests for Half Yearly Result module."""
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
def hy_db_session():
    """Create an in-memory SQLite database for Half Yearly Result testing."""
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
def hy_setup(hy_db_session):
    """Create full dataset for Half Yearly Result testing."""
    sess, SessionLocal, engine = hy_db_session

    # Create session, class, section, students
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

    # Add students
    from services import StudentService
    student_svc = StudentService(sess)

    student1 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Alice Johnson", "R001")
    student2 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Bob Smith", "R002")
    student3 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Charlie Brown", "R003")

    # Create subjects with Half Yearly components
    subject_eng = Subject(name="English", code="ENG", is_active=True)
    sess.add(subject_eng)
    sess.flush()

    mapping_eng = SubjectSectionMapping(
        subject_id=subject_eng.id, class_id=cls.id, section_id=sec.id, is_active=True
    )
    sess.add(mapping_eng)
    sess.flush()

    subject_comp = Subject(name="Computer", code="COMP", is_active=True)
    sess.add(subject_comp)
    sess.flush()

    mapping_comp = SubjectSectionMapping(
        subject_id=subject_comp.id, class_id=cls.id, section_id=sec.id, is_active=True
    )
    sess.add(mapping_comp)
    sess.flush()

    # Create Half Yearly exam type
    hy_exam = ExamType(name="Half Yearly", code="HY", description="Half Yearly Examination",
                       max_marks=100, weightage=0.5, display_order=3, is_active=True)
    sess.add(hy_exam)
    sess.flush()

    # Create components for Half Yearly (based on approved design)
    from services import ExamComponentService
    component_svc = ExamComponentService(sess)

    # English: PT1 (5), MA (5), SE (5), PF (5), WE (80)
    eng_comp1 = component_svc.add_component(
        hy_exam.id, "Periodic Test 1", "PT1", 5, subject_id=subject_eng.id, display_order=1
    )
    eng_comp2 = component_svc.add_component(
        hy_exam.id, "Multiple Assessment", "MA", 5, subject_id=subject_eng.id, display_order=2
    )
    eng_comp3 = component_svc.add_component(
        hy_exam.id, "Subject Enrichment", "SE", 5, subject_id=subject_eng.id, display_order=3
    )
    eng_comp4 = component_svc.add_component(
        hy_exam.id, "Portfolio", "PF", 5, subject_id=subject_eng.id, display_order=4
    )
    eng_comp5 = component_svc.add_component(
        hy_exam.id, "Written Exam", "WE", 80, subject_id=subject_eng.id, display_order=5
    )

    # Computer Science: PT1 (5), PRAC (30), THEORY (50), MA (5), ENR (5), PF (5)
    comp_comp1 = component_svc.add_component(
        hy_exam.id, "Periodic Test 1", "PT1", 5, subject_id=subject_comp.id, display_order=1
    )
    comp_comp2 = component_svc.add_component(
        hy_exam.id, "Practical", "PRAC", 30, subject_id=subject_comp.id, display_order=2
    )
    comp_comp3 = component_svc.add_component(
        hy_exam.id, "Theory", "THEORY", 50, subject_id=subject_comp.id, display_order=3
    )
    comp_comp4 = component_svc.add_component(
        hy_exam.id, "Multiple Assessment", "MA", 5, subject_id=subject_comp.id, display_order=4
    )
    comp_comp5 = component_svc.add_component(
        hy_exam.id, "Enrichment", "ENR", 5, subject_id=subject_comp.id, display_order=5
    )
    comp_comp6 = component_svc.add_component(
        hy_exam.id, "Portfolio", "PF", 5, subject_id=subject_comp.id, display_order=6
    )

    # Add component marks for students
    # Alice: All components scored
    # Bob: Some components scored
    # Charlie: Absent

    hy_components = [eng_comp1, eng_comp2, eng_comp3, eng_comp4, eng_comp5,
                     comp_comp1, comp_comp2, comp_comp3, comp_comp4, comp_comp5, comp_comp6]

    # Alice: English - PT1: 4/5, MA: 3/5, SE: 5/5, PF: 4/5, WE: 75/80
    # Alice: Computer - PT1: 3/5, PRAC: 28/30, THEORY: 48/50, MA: 4/5, ENR: 5/5, PF: 3/5
    alice_marks = [
        ComponentMarks(
            student_id=student1.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp1.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=4, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp2.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=3, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp3.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=5, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp4.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=4, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp5.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=75, max_marks=80, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp1.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=3, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp2.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=28, max_marks=30, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp3.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=48, max_marks=50, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp4.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=4, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp5.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=5, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student1.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp6.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=3, max_marks=5, status="saved",
        ),
    ]

    # Bob: English - PT1: 3/5, MA: 5/5, SE: None (pending), PF: 5/5, WE: 80/80
    # Bob: Computer - PT1: 4/5, PRAC: 25/30 (absent), THEORY: 45/50, MA: None, ENR: 5/5, PF: 5/5
    bob_marks = [
        ComponentMarks(
            student_id=student2.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp1.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=3, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp2.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=5, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp3.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="pending",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp4.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=5, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp5.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=80, max_marks=80, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp1.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=4, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp2.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=30, status="absent",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp3.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=45, max_marks=50, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp4.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="pending",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp5.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=5, max_marks=5, status="saved",
        ),
        ComponentMarks(
            student_id=student2.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp6.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=5, max_marks=5, status="saved",
        ),
    ]

    # Charlie: All absent
    charlie_marks = [
        ComponentMarks(
            student_id=student3.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp1.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp2.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp3.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp4.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_eng.id, exam_type_id=hy_exam.id,
            component_id=eng_comp5.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=80, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp1.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp2.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=30, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp3.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=50, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp4.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp5.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
        ComponentMarks(
            student_id=student3.id, subject_id=subject_comp.id, exam_type_id=hy_exam.id,
            component_id=comp_comp6.id, session_id=session_obj.id, class_id=cls.id,
            section_id=sec.id, marks_obtained=None, max_marks=5, status="absent",
        ),
    ]

    # Add all marks to the session
    sess.add_all(alice_marks)
    sess.add_all(bob_marks)
    sess.add_all(charlie_marks)
    sess.commit()

    return {
        "session": session_obj,
        "class": cls,
        "section": sec,
        "student1": student1,
        "student2": student2,
        "student3": student3,
        "subject_eng": subject_eng,
        "subject_comp": subject_comp,
        "hy_exam": hy_exam,
        "SessionLocal": SessionLocal,
    }
