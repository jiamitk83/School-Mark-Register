from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, SchemaVersion, SCHEMA_VERSION
from models import Class, Section, Subject, SubjectClassMapping, SubjectSectionMapping
from repositories import ClassRepository, SectionRepository, SubjectRepository
from services import ClassService, SectionService, SubjectService


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
def section_service(db_session):
    sess, _ = db_session
    cls = ClassService(sess).add_class("Class 1 for Section")
    sec = SectionService(sess).add_section(cls.id, "Section A")
    return SectionService(sess), cls.id, sec.id


@pytest.fixture
def subject_service(db_session, class_service, section_service):
    sess, _ = db_session
    return SubjectService(sess), class_service, section_service[0]


def test_add_and_list_subject(subject_service):
    service, _, _ = subject_service
    subj = service.add_subject("English", "ENG", "English Language", True)
    assert subj.id is not None
    assert subj.name == "English"
    assert subj.code == "ENG"
    assert subj.description == "English Language"
    assert subj.is_active is True
    subjects = service.list_subjects()
    assert len(subjects) == 1


def test_unique_subject_name(subject_service):
    service, _, _ = subject_service
    service.add_subject("English", "ENG")
    with pytest.raises(ValueError, match="already exists"):
        service.add_subject("English", "ENG2")


def test_unique_subject_code(subject_service):
    service, _, _ = subject_service
    service.add_subject("English", "ENG")
    with pytest.raises(ValueError, match="code.*already exists"):
        service.add_subject("English Literature", "ENG")


def test_update_subject(subject_service):
    service, _, _ = subject_service
    subj = service.add_subject("English", "ENG")
    updated = service.update_subject(subj.id, name="English Literature", code="ENGL", description="Advanced English", is_active=False)
    assert updated.name == "English Literature"
    assert updated.code == "ENGL"
    assert updated.description == "Advanced English"
    assert updated.is_active is False


def test_deactivate_activate_subject(subject_service):
    service, _, _ = subject_service
    subj = service.add_subject("English", "ENG")
    assert subj.is_active is True
    service.deactivate_subject(subj.id)
    assert service.get_subject(subj.id).is_active is False
    service.activate_subject(subj.id)
    assert service.get_subject(subj.id).is_active is True


def test_add_class_mapping(subject_service):
    service, class_service, _ = subject_service
    subj = service.add_subject("English", "ENG")
    cls = class_service.add_class("Class 1")
    mapping = service.add_class_mapping(subj.id, cls.id)
    assert mapping.id is not None
    assert mapping.subject_id == subj.id
    assert mapping.class_id == cls.id
    assert mapping.is_active is True
    
    mappings = service.get_active_class_mappings(subj.id)
    assert len(mappings) == 1


def test_duplicate_class_mapping_blocked(subject_service):
    service, class_service, _ = subject_service
    subj = service.add_subject("English", "ENG")
    cls = class_service.add_class("Class 1")
    service.add_class_mapping(subj.id, cls.id)
    with pytest.raises(ValueError, match="already mapped"):
        service.add_class_mapping(subj.id, cls.id)


def test_remove_class_mapping(subject_service):
    service, class_service, _ = subject_service
    subj = service.add_subject("English", "ENG")
    cls = class_service.add_class("Class 1")
    mapping = service.add_class_mapping(subj.id, cls.id)
    service.remove_class_mapping(mapping.id)
    mappings = service.get_active_class_mappings(subj.id)
    assert len(mappings) == 0


def test_set_class_mappings(subject_service):
    service, class_service, _ = subject_service
    subj = service.add_subject("English", "ENG")
    cls1 = class_service.add_class("Class 1")
    cls2 = class_service.add_class("Class 2")
    cls3 = class_service.add_class("Class 3")
    
    service.set_class_mappings(subj.id, [cls1.id, cls2.id])
    mappings = service.get_active_class_mappings(subj.id)
    assert len(mappings) == 2
    class_ids = {m.class_id for m in mappings}
    assert class_ids == {cls1.id, cls2.id}
    
    # Replace with different set
    service.set_class_mappings(subj.id, [cls2.id, cls3.id])
    mappings = service.get_active_class_mappings(subj.id)
    assert len(mappings) == 2
    class_ids = {m.class_id for m in mappings}
    assert class_ids == {cls2.id, cls3.id}


def test_add_section_mapping(subject_service):
    service, class_service, section_service = subject_service
    subj = service.add_subject("English", "ENG")
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    mapping = service.add_section_mapping(subj.id, cls.id, sec.id)
    assert mapping.id is not None
    assert mapping.subject_id == subj.id
    assert mapping.class_id == cls.id
    assert mapping.section_id == sec.id
    assert mapping.is_active is True
    
    mappings = service.get_active_section_mappings(subj.id)
    assert len(mappings) == 1


def test_section_mapping_wrong_class_blocked(subject_service):
    service, class_service, section_service = subject_service
    subj = service.add_subject("English", "ENG")
    cls1 = class_service.add_class("Class 1")
    cls2 = class_service.add_class("Class 2")
    sec = section_service.add_section(cls1.id, "Section A")
    with pytest.raises(ValueError, match="does not belong"):
        service.add_section_mapping(subj.id, cls2.id, sec.id)


def test_set_section_mappings_for_class(subject_service):
    service, class_service, section_service = subject_service
    subj = service.add_subject("English", "ENG")
    cls = class_service.add_class("Class 1")
    sec1 = section_service.add_section(cls.id, "Section A")
    sec2 = section_service.add_section(cls.id, "Section B")
    sec3 = section_service.add_section(cls.id, "Section C")
    
    # Map to specific sections
    service.set_section_mappings_for_class(subj.id, cls.id, [sec1.id, sec2.id])
    mappings = service.get_active_section_mappings(subj.id)
    assert len(mappings) == 2
    section_ids = {m.section_id for m in mappings}
    assert section_ids == {sec1.id, sec2.id}
    
    # Map to all sections
    service.set_section_mappings_for_class(subj.id, cls.id, [], all_sections=True)
    mappings = service.get_active_section_mappings(subj.id)
    assert len(mappings) == 3


def test_copy_mappings(subject_service):
    service, class_service, section_service = subject_service
    subj1 = service.add_subject("English", "ENG")
    subj2 = service.add_subject("Mathematics", "MATH")
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    
    service.add_class_mapping(subj1.id, cls.id)
    service.add_section_mapping(subj1.id, cls.id, sec.id)
    
    service.copy_mappings_from_subject(subj1.id, subj2.id)
    
    class_mappings = service.get_active_class_mappings(subj2.id)
    section_mappings = service.get_active_section_mappings(subj2.id)
    assert len(class_mappings) == 1
    assert len(section_mappings) == 1


def test_bulk_import_subjects(subject_service):
    service, _, _ = subject_service
    subjects = [
        {"name": "English", "code": "ENG", "description": "English Language", "is_active": True},
        {"name": "Mathematics", "code": "MATH", "description": "Mathematics", "is_active": True},
        {"name": "Science", "code": "SCI", "description": "Science", "is_active": True},
    ]
    created, errors = service.bulk_import_subjects(subjects)
    assert len(created) == 3
    assert len(errors) == 0
    subjects_list = service.list_subjects()
    assert len(subjects_list) == 3


def test_bulk_import_skip_duplicates(subject_service):
    service, _, _ = subject_service
    service.add_subject("English", "ENG")
    subjects = [
        {"name": "English", "code": "ENG", "is_active": True},
        {"name": "Mathematics", "code": "MATH", "is_active": True},
    ]
    created, errors = service.bulk_import_subjects(subjects, skip_duplicates=True)
    assert len(created) == 1
    assert any("Duplicate skipped" in e for e in errors)


def test_bulk_import_reject_duplicates(subject_service):
    service, _, _ = subject_service
    service.add_subject("English", "ENG")
    subjects = [
        {"name": "English", "code": "ENG"},
        {"name": "Mathematics", "code": "MATH"},
    ]
    created, errors = service.bulk_import_subjects(subjects, skip_duplicates=False)
    assert len(created) == 1
    assert any("Duplicate" in e for e in errors)


def test_export_subjects_csv(subject_service):
    service, _, _ = subject_service
    service.add_subject("English", "ENG", "English Language", True)
    service.add_subject("Mathematics", "MATH", "Mathematics", False)
    csv_content = service.export_subjects_to_csv()
    assert "English" in csv_content
    assert "ENG" in csv_content
    assert "Mathematics" in csv_content
    assert "MATH" in csv_content


def test_export_mappings_csv(subject_service):
    service, class_service, section_service = subject_service
    subj = service.add_subject("English", "ENG")
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    service.add_class_mapping(subj.id, cls.id)
    service.add_section_mapping(subj.id, cls.id, sec.id)
    
    csv_content = service.export_mappings_to_csv()
    assert "English" in csv_content
    assert "ENG" in csv_content
    assert "Class 1" in csv_content
    assert "Section A" in csv_content


def test_data_persistence_across_sessions(subject_service):
    service, _, _ = subject_service
    service.add_subject("English", "ENG")
    engine = service.session.get_bind()
    service.session.close()
    new_sess = sessionmaker(bind=engine)()
    try:
        rows = new_sess.query(Subject).all()
        assert len(rows) == 1
        assert rows[0].name == "English"
        assert rows[0].code == "ENG"
    finally:
        new_sess.close()


def test_subject_repository(db_session):
    sess, _ = db_session
    repo = SubjectRepository(sess)
    assert repo.list_all() == []
    assert repo.list_active() == []
    assert not repo.exists_by_name("English")
    assert not repo.exists_by_code("ENG")


def test_section_mapping_invalid_class_blocked(subject_service):
    service, class_service, section_service = subject_service
    subj = service.add_subject("English", "ENG")
    cls1 = class_service.add_class("Class 1")
    cls2 = class_service.add_class("Class 2")
    sec = section_service.add_section(cls1.id, "Section A")
    with pytest.raises(ValueError, match="does not belong"):
        service.add_section_mapping(subj.id, cls2.id, sec.id)


def test_cascade_get_sections_for_class(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec1 = section_service.add_section(cls.id, "Section A")
    sec2 = section_service.add_section(cls.id, "Section B")
    
    sections = service.get_sections_for_class(cls.id)
    assert len(sections) == 2
    section_names = {s.name for s in sections}
    assert section_names == {"Section A", "Section B"}


def test_cascade_get_available_subjects_for_section(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec1 = section_service.add_section(cls.id, "Section A")
    sec2 = section_service.add_section(cls.id, "Section B")
    subj1 = service.add_subject("English", "ENG")
    subj2 = service.add_subject("Mathematics", "MATH")
    
    # Initially all subjects available
    available = service.get_available_subjects_for_section(cls.id, sec1.id)
    assert len(available) == 2
    
    # Map one subject
    service.assign_subject_to_section(subj1.id, cls.id, sec1.id)
    
    # Only one subject should be available now
    available = service.get_available_subjects_for_section(cls.id, sec1.id)
    assert len(available) == 1
    assert available[0].id == subj2.id
    
    # Other section still has both available
    available = service.get_available_subjects_for_section(cls.id, sec2.id)
    assert len(available) == 2


def test_cascade_assign_subject_to_section(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    subj = service.add_subject("English", "ENG")
    
    mapping = service.assign_subject_to_section(subj.id, cls.id, sec.id)
    assert mapping.id is not None
    assert mapping.subject_id == subj.id
    assert mapping.class_id == cls.id
    assert mapping.section_id == sec.id
    assert mapping.is_active is True


def test_cascade_duplicate_assignment_blocked(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    subj = service.add_subject("English", "ENG")
    
    service.assign_subject_to_section(subj.id, cls.id, sec.id)
    with pytest.raises(ValueError, match="already mapped"):
        service.assign_subject_to_section(subj.id, cls.id, sec.id)


def test_cascade_wrong_class_blocked(subject_service):
    service, class_service, section_service = subject_service
    cls1 = class_service.add_class("Class 1")
    cls2 = class_service.add_class("Class 2")
    sec = section_service.add_section(cls1.id, "Section A")
    subj = service.add_subject("English", "ENG")
    
    with pytest.raises(ValueError, match="does not belong"):
        service.assign_subject_to_section(subj.id, cls2.id, sec.id)


def test_cascade_remove_subject_from_section(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    subj = service.add_subject("English", "ENG")
    
    service.assign_subject_to_section(subj.id, cls.id, sec.id)
    service.remove_subject_from_section(subj.id, sec.id)
    
    # Verify mapping is removed
    assignments = service.get_assignments_for_class_section(cls.id, sec.id)
    assert len(assignments) == 0


def test_cascade_get_assignments_for_class_section(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec1 = section_service.add_section(cls.id, "Section A")
    sec2 = section_service.add_section(cls.id, "Section B")
    subj1 = service.add_subject("English", "ENG")
    subj2 = service.add_subject("Mathematics", "MATH")
    
    service.assign_subject_to_section(subj1.id, cls.id, sec1.id)
    service.assign_subject_to_section(subj2.id, cls.id, sec1.id)
    service.assign_subject_to_section(subj1.id, cls.id, sec2.id)
    
    # Check assignments for sec1
    assignments = service.get_assignments_for_class_section(cls.id, sec1.id)
    assert len(assignments) == 2
    subject_ids = {a.subject_id for a in assignments}
    assert subject_ids == {subj1.id, subj2.id}
    
    # Check assignments for sec2
    assignments = service.get_assignments_for_class_section(cls.id, sec2.id)
    assert len(assignments) == 1
    assert assignments[0].subject_id == subj1.id


def test_cascade_data_persistence_across_sessions(subject_service):
    service, class_service, section_service = subject_service
    cls = class_service.add_class("Class 1")
    sec = section_service.add_section(cls.id, "Section A")
    subj = service.add_subject("English", "ENG")
    service.assign_subject_to_section(subj.id, cls.id, sec.id)
    
    # Store IDs before closing session
    cls_id = cls.id
    sec_id = sec.id
    subj_id = subj.id
    
    engine = service.session.get_bind()
    service.session.close()
    new_sess = sessionmaker(bind=engine)()
    try:
        new_service = SubjectService(new_sess)
        assignments = new_service.get_assignments_for_class_section(cls_id, sec_id)
        assert len(assignments) == 1
        assert assignments[0].subject_id == subj_id
    finally:
        new_sess.close()