from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, SchemaVersion, SCHEMA_VERSION
from models import Class, Section
from repositories import ClassRepository, SectionRepository
from services import ClassService, SectionService


@pytest.fixture
def db_session():
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
def class_service(db_session):
    sess, _ = db_session
    return ClassService(sess)


@pytest.fixture
def section_service(db_session, class_service):
    sess, _ = db_session
    cls = class_service.add_class("Class 1")
    return SectionService(sess), cls.id


def test_add_and_list_section(section_service):
    service, class_id = section_service
    sec = service.add_section(class_id, "Section A")
    assert sec.id is not None
    assert sec.name == "Section A"
    assert sec.class_id == class_id
    assert sec.display_order == 1
    assert sec.is_active is True
    sections = service.list_sections(class_id)
    assert len(sections) == 1


def test_unique_section_name_per_class(section_service):
    service, class_id = section_service
    service.add_section(class_id, "Section A")
    with pytest.raises(ValueError, match="already exists"):
        service.add_section(class_id, "Section A")
    # Different class should be allowed
    from services import ClassService
    class_service = ClassService(service.session)
    class2 = class_service.add_class("Class 2")
    sec = service.add_section(class2.id, "Section A")
    assert sec.id is not None


def test_case_insensitive_unique_name(section_service):
    service, class_id = section_service
    service.add_section(class_id, "Section A")
    with pytest.raises(ValueError, match="already exists"):
        service.add_section(class_id, "section a")
    with pytest.raises(ValueError, match="already exists"):
        service.add_section(class_id, "SECTION A")


def test_auto_display_order(section_service):
    service, class_id = section_service
    s1 = service.add_section(class_id, "Section A")
    s2 = service.add_section(class_id, "Section B")
    s3 = service.add_section(class_id, "Section C")
    assert s1.display_order == 1
    assert s2.display_order == 2
    assert s3.display_order == 3


def test_manual_display_order(section_service):
    service, class_id = section_service
    s1 = service.add_section(class_id, "Section A", display_order=10)
    s2 = service.add_section(class_id, "Section B", display_order=5)
    s3 = service.add_section(class_id, "Section C")  # auto: max(10,5)+1 = 11
    assert s1.display_order == 10
    assert s2.display_order == 5
    assert s3.display_order == 11


def test_display_order_non_negative(section_service):
    service, class_id = section_service
    with pytest.raises(ValueError, match="non-negative"):
        service.add_section(class_id, "Bad", display_order=-1)
    with pytest.raises(ValueError, match="non-negative"):
        service.add_section(class_id, "Good", display_order=0)
        service.update_section(1, display_order=-1)


def test_update_section(section_service):
    service, class_id = section_service
    sec = service.add_section(class_id, "Section A")
    updated = service.update_section(sec.id, name="Section A1", display_order=5, is_active=False)
    assert updated.name == "Section A1"
    assert updated.display_order == 5
    assert updated.is_active is False


def test_update_duplicate_name_blocked(section_service):
    service, class_id = section_service
    s1 = service.add_section(class_id, "Section A")
    service.add_section(class_id, "Section B")
    with pytest.raises(ValueError, match="already exists"):
        service.update_section(s1.id, name="Section B")
    assert service.get_section(s1.id).name == "Section A"


def test_deactivate_activate_section(section_service):
    service, class_id = section_service
    sec = service.add_section(class_id, "Section A")
    assert sec.is_active is True
    service.deactivate_section(sec.id)
    assert service.get_section(sec.id).is_active is False
    service.activate_section(sec.id)
    assert service.get_section(sec.id).is_active is True


def test_reorder_sections(section_service):
    service, class_id = section_service
    s1 = service.add_section(class_id, "Section A")  # order 1
    s2 = service.add_section(class_id, "Section B")  # order 2
    s3 = service.add_section(class_id, "Section C")  # order 3
    # Reorder: s3 first, then s1, then s2
    service.reorder_sections(class_id, [(s3.id, 1), (s1.id, 2), (s2.id, 3)])
    sections = service.list_sections(class_id)
    assert sections[0].id == s3.id
    assert sections[1].id == s1.id
    assert sections[2].id == s2.id


def test_reorder_invalid_order(section_service):
    service, class_id = section_service
    s1 = service.add_section(class_id, "Section A")
    with pytest.raises(ValueError, match="non-negative"):
        service.reorder_sections(class_id, [(s1.id, -1)])


def test_bulk_import(section_service):
    service, class_id = section_service
    names = ["Section A", "Section B", "Section C"]
    created, errors = service.bulk_import(class_id, names)
    assert len(created) == 3
    assert len(errors) == 0
    sections = service.list_sections(class_id)
    assert len(sections) == 3


def test_bulk_import_skip_duplicates(section_service):
    service, class_id = section_service
    service.add_section(class_id, "Section A")
    names = ["Section A", "Section B", "Section C"]
    created, errors = service.bulk_import(class_id, names, skip_duplicates=True)
    assert len(created) == 2
    assert any("Duplicate skipped" in e for e in errors)


def test_bulk_import_reject_duplicates(section_service):
    service, class_id = section_service
    service.add_section(class_id, "Section A")
    names = ["Section A", "Section B"]
    created, errors = service.bulk_import(class_id, names, skip_duplicates=False)
    assert len(created) == 1
    assert any("Duplicate:" in e for e in errors)


def test_bulk_import_empty_names(section_service):
    service, class_id = section_service
    names = ["Section A", "", "   ", "Section B"]
    created, errors = service.bulk_import(class_id, names)
    assert len(created) == 2
    assert any("Empty name skipped" in e for e in errors)


def test_bulk_import_csv(section_service):
    service, class_id = section_service
    csv_content = "Section A,1\nSection B,2\nSection C,3\n"
    created, errors = service.bulk_import_from_csv(class_id, csv_content)
    assert len(created) == 3
    assert len(errors) == 0
    sections = service.list_sections(class_id)
    assert len(sections) == 3


def test_bulk_import_csv_invalid_display_order(section_service):
    service, class_id = section_service
    csv_content = "Section A,invalid\nSection B,2\n"
    created, errors = service.bulk_import_from_csv(class_id, csv_content)
    assert len(created) == 1
    assert any("Invalid display order" in e for e in errors)


def test_bulk_import_csv_negative_display_order(section_service):
    service, class_id = section_service
    csv_content = "Section A,-1\nSection B,2\n"
    created, errors = service.bulk_import_from_csv(class_id, csv_content)
    assert len(created) == 1
    assert any("non-negative" in e for e in errors)


def test_list_active_only(section_service):
    service, class_id = section_service
    service.add_section(class_id, "Section A")
    s2 = service.add_section(class_id, "Section B")
    service.deactivate_section(s2.id)
    active = service.list_active_sections(class_id)
    assert len(active) == 1
    assert active[0].name == "Section A"


def test_deactivation_blocked_when_records_exist(section_service):
    service, class_id = section_service
    sec = service.add_section(class_id, "Section A")
    # Add a record referencing this section
    from models import AcademicRecord
    # Need a session_id as well
    from services import SessionService
    session_service = SessionService(service.session)
    session_obj = session_service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))
    service.session.add(AcademicRecord(
        session_id=session_obj.id,
        class_id=class_id,
        section_id=sec.id,
        student_name="Alice",
        subject="Math",
        score=85
    ))
    service.session.commit()
    with pytest.raises(ValueError, match="referenced by academic records"):
        service.deactivate_section(sec.id)
    assert service.get_section(sec.id).is_active is True


def test_class_deactivation_blocked_when_sections_active(section_service):
    service, class_id = section_service
    # Add sections
    sec1 = service.add_section(class_id, "Section A")
    sec2 = service.add_section(class_id, "Section B")
    # Try to deactivate class - should fail if sections are active
    from services import ClassService
    class_service = ClassService(service.session)
    with pytest.raises(ValueError, match="active section"):
        class_service.deactivate_class(class_id)


def test_data_persistence_across_sessions(section_service):
    service, class_id = section_service
    service.add_section(class_id, "Section A")
    engine = service.session.get_bind()
    service.session.close()
    new_sess = sessionmaker(bind=engine)()
    try:
        rows = new_sess.query(Section).all()
        assert len(rows) == 1
        assert rows[0].name == "Section A"
    finally:
        new_sess.close()


def test_section_repository(db_session):
    sess, _ = db_session
    repo = SectionRepository(sess)
    assert repo.list_by_class(1) == []
    assert repo.list_active_by_class(1) == []
    assert repo.get_max_display_order(1) == 0
    assert not repo.get_by_class_and_name(1, "Section A")