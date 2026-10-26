from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import AcademicSession, Class, Section, Student
from repositories import StudentRepository
from services import ClassService, SectionService, SessionService, StudentService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    import os
    import tempfile
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sess = SessionLocal()
    yield sess, engine
    sess.close()
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def session_service(db_session):
    sess, _ = db_session
    return SessionService(sess)


@pytest.fixture
def class_service(db_session):
    sess, _ = db_session
    return ClassService(sess)


@pytest.fixture
def section_service(db_session):
    sess, _ = db_session
    return SectionService(sess)


@pytest.fixture
def student_service(db_session, session_service, class_service, section_service):
    """Create a StudentService with prerequisite session, class, and section."""
    sess, _ = db_session
    session_obj = session_service.add_session("2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True)
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    return StudentService(sess), session_obj, cls, sec


@pytest.fixture
def student_repo(db_session):
    sess, _ = db_session
    return StudentRepository(sess), sess


def create_student_data(name="Alice Johnson", roll="R001", **kwargs):
    """Helper to create student kwargs dict."""
    data = {
        "name": name,
        "roll_number": roll,
    }
    data.update(kwargs)
    return data


# ========== Add and List Tests ==========

def test_add_and_list_student(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(
        sess_obj.id, cls.id, sec.id,
        name="Alice Johnson", roll_number="R001",
        father_name="John Johnson", mother_name="Mary Johnson",
        gender="Female", phone="1234567890",
    )
    assert student.id is not None
    assert student.admission_number.startswith("STU")
    assert student.name == "Alice Johnson"
    assert student.roll_number == "R001"
    assert student.gender == "Female"
    assert student.is_active is True

    students = service.list_students(sess_obj.id, cls.id, sec.id)
    assert len(students) == 1
    assert students[0].name == "Alice Johnson"


def test_add_student_auto_admission_number(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002")
    assert student.admission_number == "STU000001"


def test_add_student_second_auto_admission_number(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    student2 = service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002")
    assert student2.admission_number == "STU000002"


def test_add_student_missing_name(student_service):
    service, sess_obj, cls, sec = student_service
    with pytest.raises(ValueError, match="name is required"):
        service.add_student(sess_obj.id, cls.id, sec.id, "", "R001")


def test_add_student_missing_roll(student_service):
    service, sess_obj, cls, sec = student_service
    with pytest.raises(ValueError, match="(?i)roll number is required"):
        service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "")


def test_add_student_invalid_session(student_service):
    service, _, cls, sec = student_service
    with pytest.raises(ValueError, match="session not found"):
        service.add_student(999, cls.id, sec.id, "Alice", "R001")


def test_add_student_invalid_class(student_service):
    service, sess_obj, _, sec = student_service
    with pytest.raises(ValueError, match="(?i)class not found"):
        service.add_student(sess_obj.id, 999, sec.id, "Alice", "R001")


def test_add_student_invalid_section(student_service):
    service, sess_obj, cls, _ = student_service
    with pytest.raises(ValueError, match="(?i)section not found"):
        service.add_student(sess_obj.id, cls.id, 999, "Alice", "R001")


def test_add_student_section_belonging_to_other_class(db_session):
    sess, _ = db_session
    session_obj = SessionService(sess).add_session("2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True)
    cls1 = ClassService(sess).add_class("Class 1")
    cls2 = ClassService(sess).add_class("Class 2")
    sec = SectionService(sess).add_section(cls1.id, "Section A")
    service = StudentService(sess)
    with pytest.raises(ValueError, match="does not belong"):
        service.add_student(session_obj.id, cls2.id, sec.id, "Alice", "R001")


# ========== Roll Number Uniqueness Tests ==========

def test_duplicate_roll_number_blocked(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    with pytest.raises(ValueError, match="already exists"):
        service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R001")


def test_roll_number_unique_across_sections(student_service):
    service, sess_obj, cls, _ = student_service
    sec1 = SectionService(service.session).add_section(cls.id, "Section B")
    sec2 = SectionService(service.session).add_section(cls.id, "Section C")
    service.add_student(sess_obj.id, cls.id, sec1.id, "Alice", "R001")
    # Same roll in different section should be allowed
    student2 = service.add_student(sess_obj.id, cls.id, sec2.id, "Bob", "R001")
    assert student2.roll_number == "R001"


def test_admission_number_unique(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002")
    students = service.list_students(sess_obj.id, cls.id, sec.id)
    admission_numbers = {s.admission_number for s in students}
    assert len(admission_numbers) == 2


# ========== Update Tests ==========

def test_update_student_name(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    updated = service.update_student(student.id, name="Alice Smith")
    assert updated.name == "Alice Smith"


def test_update_student_roll_number(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002")
    updated = service.update_student(student.id, roll_number="R010")
    assert updated.roll_number == "R010"


def test_update_student_roll_conflict_blocked(student_service):
    service, sess_obj, cls, sec = student_service
    student1 = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    student2 = service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002")
    with pytest.raises(ValueError, match="already exists"):
        service.update_student(student2.id, roll_number="R001")


def test_update_student_not_found(student_service):
    service = student_service[0]
    with pytest.raises(ValueError, match="not found"):
        service.update_student(999, name="Test")


def test_update_student_optional_fields(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    dob = date(2010, 5, 15)
    updated = service.update_student(
        student.id,
        father_name="Robert", mother_name="Susan",
        dob=dob, gender="Female",
        phone="9999999999", email="alice@example.com",
        address="123 Main St",
    )
    assert updated.father_name == "Robert"
    assert updated.mother_name == "Susan"
    assert updated.dob == dob
    assert updated.gender == "Female"
    assert updated.phone == "9999999999"
    assert updated.email == "alice@example.com"
    assert updated.address == "123 Main St"


# ========== Activate/Deactivate Tests ==========

def test_deactivate_activate_student(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    assert student.is_active is True
    service.deactivate_student(student.id)
    assert service.get_student(student.id).is_active is False
    service.activate_student(student.id)
    assert service.get_student(student.id).is_active is True


def test_deactivate_nonexistent_student(student_service):
    service = student_service[0]
    with pytest.raises(ValueError, match="not found"):
        service.deactivate_student(999)


def test_activate_nonexistent_student(student_service):
    service = student_service[0]
    with pytest.raises(ValueError, match="not found"):
        service.activate_student(999)


def test_deactivate_already_inactive(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001", is_active=False)
    service.deactivate_student(student.id)  # Should not raise


def test_list_active_students(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001", is_active=True)
    service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002", is_active=False)
    active = service.list_active_students(sess_obj.id, cls.id, sec.id)
    assert len(active) == 1
    assert active[0].name == "Alice"


# ========== Bulk Import Tests ==========

def test_bulk_import_students(student_service):
    service, sess_obj, cls, sec = student_service
    students = [
        {"name": "Alice", "roll_number": "R001"},
        {"name": "Bob", "roll_number": "R002"},
        {"name": "Charlie", "roll_number": "R003"},
    ]
    created, errors = service.bulk_import(sess_obj.id, cls.id, sec.id, students)
    assert len(created) == 3
    assert len(errors) == 0
    assert len(service.list_students(sess_obj.id, cls.id, sec.id)) == 3


def test_bulk_import_skip_duplicates(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    students = [
        {"name": "Alice Duplicate", "roll_number": "R001"},
        {"name": "Bob", "roll_number": "R002"},
    ]
    created, errors = service.bulk_import(sess_obj.id, cls.id, sec.id, students, skip_duplicates=True)
    assert len(created) == 1
    assert any("Duplicate" in e for e in errors)


def test_bulk_import_reject_duplicates(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    students = [
        {"name": "Alice Duplicate", "roll_number": "R001"},
        {"name": "Bob", "roll_number": "R002"},
    ]
    created, errors = service.bulk_import(sess_obj.id, cls.id, sec.id, students, skip_duplicates=False)
    assert len(created) == 1
    assert any("Duplicate" in e for e in errors)


def test_bulk_import_empty_names(student_service):
    service, sess_obj, cls, sec = student_service
    students = [
        {"name": "", "roll_number": "R001"},
        {"name": "Bob", "roll_number": ""},
        {"name": "Charlie", "roll_number": "R003"},
    ]
    created, errors = service.bulk_import(sess_obj.id, cls.id, sec.id, students)
    assert len(created) == 1
    assert len(errors) == 2


def test_bulk_import_invalid_session(student_service):
    service, _, cls, sec = student_service
    students = [{"name": "Alice", "roll_number": "R001"}]
    with pytest.raises(ValueError, match="session not found"):
        service.bulk_import(999, cls.id, sec.id, students)


# ========== Search Tests ==========

def test_search_students_by_name(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice Johnson", "R001")
    service.add_student(sess_obj.id, cls.id, sec.id, "Bob Smith", "R002")
    results = service.search_students("Alice")
    assert len(results) == 1
    assert results[0].name == "Alice Johnson"


def test_search_students_by_admission(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    results = service.search_students(student.admission_number)
    assert len(results) == 1
    assert results[0].name == "Alice"


def test_search_students_by_roll(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002")
    results = service.search_students("R002")
    assert len(results) == 1
    assert results[0].name == "Bob"


def test_search_students_with_filters(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    results = service.search_students("Alice", session_id=sess_obj.id)
    assert len(results) == 1


# ========== Export Tests ==========

def test_export_students_to_csv(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001", father_name="John", phone="12345")
    service.add_student(sess_obj.id, cls.id, sec.id, "Bob", "R002", gender="Male")
    csv_content = service.export_students_to_csv(sess_obj.id, cls.id, sec.id)
    assert "Alice" in csv_content
    assert "R001" in csv_content
    assert "Bob" in csv_content
    assert "R002" in csv_content
    assert "Father's Name" in csv_content or "Father" in csv_content
    assert "Admission Number" in csv_content


# ========== Repository Tests ==========

def test_student_repository(db_session):
    sess, _ = db_session
    repo = StudentRepository(sess)
    assert repo.list_all() == []
    assert repo.list_active() == []
    assert not repo.exists_by_admission_number("STU00001")


def test_student_repository_get_by_admission(db_session):
    sess, engine = db_session
    session_obj = SessionService(sess).add_session("2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True)
    cls = ClassService(sess).add_class("Class 1")
    sec = SectionService(sess).add_section(cls.id, "Section A")
    student = StudentService(sess).add_student(session_obj.id, cls.id, sec.id, "Alice", "R001")
    repo = StudentRepository(sess)
    found = repo.get_by_admission_number(student.admission_number)
    assert found is not None
    assert found.name == "Alice"


def test_student_repository_next_admission_number(db_session):
    sess, _ = db_session
    repo = StudentRepository(sess)
    next_num = repo.get_next_admission_number()
    assert next_num == "STU000001"


# ========== Persistence Tests ==========

def test_student_data_persistence(student_service):
    service, sess_obj, cls, sec = student_service
    service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    engine = service.session.get_bind()
    student_id = service.list_students(sess_obj.id, cls.id, sec.id)[0].id
    service.session.close()

    new_sess = sessionmaker(bind=engine)()
    try:
        new_service = StudentService(new_sess)
        students = new_service.list_students(sess_obj.id, cls.id, sec.id)
        assert len(students) == 1
        assert students[0].name == "Alice"
        assert students[0].admission_number.startswith("STU")
    finally:
        new_sess.close()


def test_student_service_get_student_by_admission(student_service):
    service, sess_obj, cls, sec = student_service
    student = service.add_student(sess_obj.id, cls.id, sec.id, "Alice", "R001")
    found = service.get_student_by_admission(student.admission_number)
    assert found is not None
    assert found.name == "Alice"


# ========== Schema Version Tests ==========

def test_schema_version_is_12():
    from database import SCHEMA_VERSION
    assert SCHEMA_VERSION == 12


def test_student_table_created(db_session):
    sess, engine = db_session
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "students" in tables
