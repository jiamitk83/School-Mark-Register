from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Class, ExamType, Marks, MarksAuditLog, MarksDraft, Section, Student, Subject
from repositories import MarksRepository, MarksAuditLogRepository, MarksDraftRepository
from services import ClassService, ExamTypeService, MarksService, SectionService, StudentService


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
def setup_data(db_session):
    """Create session, class, section, student, subject, exam_type for testing."""
    sess, _ = db_session
    from services import SessionService
    session_svc = SessionService(sess)
    session_obj = session_svc.add_session("2026/2027", date(2026, 4, 1), date(2027, 3, 31), "active", True)
    
    from services import ClassService
    class_svc = ClassService(sess)
    cls = class_svc.add_class("Class 1")
    
    from services import SectionService
    section_svc = SectionService(sess)
    sec = section_svc.add_section(cls.id, "Section A")
    
    from services import StudentService
    student_svc = StudentService(sess)
    student = student_svc.add_student(session_obj.id, cls.id, sec.id, "Alice Johnson", "R001")
    student2 = student_svc.add_student(session_obj.id, cls.id, sec.id, "Bob Smith", "R002")
    
    subject = Subject(name="English", code="ENG", is_active=True)
    sess.add(subject)
    sess.flush()
    
    subject2 = Subject(name="Mathematics", code="MATH", is_active=True)
    sess.add(subject2)
    sess.flush()
    
    from services import ExamTypeService
    exam_type_svc = ExamTypeService(sess)
    exam_type = exam_type_svc.add_exam_type("Mid-term", "MT", max_marks=100, weightage=0.5)
    
    return {
        "session": session_obj,
        "class": cls,
        "section": sec,
        "student": student,
        "student2": student2,
        "subject": subject,
        "subject2": subject2,
        "exam_type": exam_type,
        "session_svc": session_svc,
        "class_svc": class_svc,
        "section_svc": section_svc,
        "student_svc": student_svc,
        "exam_type_svc": exam_type_svc,
    }


@pytest.fixture
def marks_service(db_session, setup_data):
    sess, _ = db_session
    return MarksService(sess)


@pytest.fixture
def marks_repo(db_session):
    sess, _ = db_session
    return MarksRepository(sess)


def test_add_and_list_marks(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=85,
        status="saved",
    )
    assert marks.id is not None
    assert marks.student_id == data["student"].id
    assert marks.subject_id == data["subject"].id
    assert marks.exam_type_id == data["exam_type"].id
    assert marks.marks_obtained == 85
    assert marks.max_marks == 100
    assert marks.status == "saved"
    assert marks.session_id == data["session"].id
    assert marks.class_id == data["class"].id
    assert marks.section_id == data["section"].id

    marks_list = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(marks_list) == 1


def test_save_marks_absent(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=None,
        status="absent",
    )
    assert marks.marks_obtained is None
    assert marks.status == "absent"


def test_save_marks_pending(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=None,
        status="pending",
    )
    assert marks.marks_obtained is None
    assert marks.status == "pending"


def test_marks_validation_max_marks(marks_service, setup_data):
    data = setup_data
    with pytest.raises(ValueError, match="between 0 and 100"):
        marks_service.save_marks(
            data["student"].id,
            data["subject"].id,
            data["exam_type"].id,
            marks_obtained=150,
        )
    with pytest.raises(ValueError, match="between 0 and 100"):
        marks_service.save_marks(
            data["student"].id,
            data["subject"].id,
            data["exam_type"].id,
            marks_obtained=-5,
        )


def test_update_existing_marks(marks_service, setup_data):
    data = setup_data
    # First save
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    # Update
    marks = marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    assert marks.marks_obtained == 85


def test_cannot_modify_locked_marks(marks_service, setup_data):
    data = setup_data
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "locked")
    with pytest.raises(ValueError, match="Cannot modify locked marks"):
        marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 85, "saved")


def test_invalid_status(marks_service, setup_data):
    data = setup_data
    with pytest.raises(ValueError, match="Invalid status"):
        marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 50, "invalid")


def test_invalid_student(marks_service, setup_data):
    data = setup_data
    with pytest.raises(ValueError, match="Student not found"):
        marks_service.save_marks(999, data["subject"].id, data["exam_type"].id, 50)


def test_bulk_save_marks(marks_service, setup_data):
    data = setup_data
    marks_data = [
        {"student_id": data["student"].id, "subject_id": data["subject"].id, "marks_obtained": 85, "status": "saved"},
        {"student_id": data["student2"].id, "subject_id": data["subject"].id, "marks_obtained": 90, "status": "saved"},
    ]
    created, errors = marks_service.bulk_save_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, marks_data
    )
    assert len(created) == 2
    assert len(errors) == 0


def test_bulk_save_marks_with_absent(marks_service, setup_data):
    data = setup_data
    marks_data = [
        {"student_id": data["student"].id, "subject_id": data["subject"].id, "marks_obtained": 85, "status": "saved"},
        {"student_id": data["student2"].id, "subject_id": data["subject"].id, "marks_obtained": None, "status": "absent"},
    ]
    created, errors = marks_service.bulk_save_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, marks_data
    )
    assert len(created) == 2


def test_bulk_save_invalid_student(marks_service, setup_data):
    data = setup_data
    marks_data = [
        {"student_id": 999, "subject_id": data["subject"].id, "marks_obtained": 85, "status": "saved"},
    ]
    created, errors = marks_service.bulk_save_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, marks_data
    )
    assert len(created) == 0
    assert len(errors) == 1


def test_lock_marks(marks_service, setup_data):
    data = setup_data
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_service.save_marks(data["student2"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    
    count = marks_service.lock_marks(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    assert count == 2
    
    # Verify locked
    marks_list = marks_service.list_marks_for_entry(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    for m in marks_list:
        assert m.status == "locked"


def test_unlock_marks(marks_service, setup_data):
    data = setup_data
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "locked")
    marks_service.save_marks(data["student2"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    
    count = marks_service.unlock_marks(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    assert count == 1  # Only the locked one gets unlocked
    
    marks_list = marks_service.list_marks_for_entry(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    locked_count = sum(1 for m in marks_list if m.status == "locked")
    assert locked_count == 0


def test_get_subjects_for_class_section(marks_service, setup_data):
    data = setup_data
    # Map subject to class+section
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(data["subject"].id, data["class"].id, data["section"].id)
    subject_svc.add_section_mapping(data["subject2"].id, data["class"].id, data["section"].id)
    
    subjects = marks_service.get_subjects_for_class_section(data["class"].id, data["section"].id)
    assert len(subjects) == 2


def test_list_marks_by_student(marks_service, setup_data):
    data = setup_data
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_service.save_marks(data["student"].id, data["subject2"].id, data["exam_type"].id, 85, "saved")
    
    marks_list = marks_service.list_marks_by_student(data["student"].id)
    assert len(marks_list) == 2


def test_list_marks_by_student_exam(marks_service, setup_data):
    data = setup_data
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_service.save_marks(data["student2"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    
    marks_list = marks_service.list_marks_by_student_exam(data["student"].id, data["exam_type"].id)
    assert len(marks_list) == 1


def test_unique_constraint_student_subject_exam(marks_service, setup_data):
    data = setup_data
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    # Try to add duplicate
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    # Should update, not create duplicate
    marks_list = marks_service.list_marks_for_entry(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    assert len(marks_list) == 1
    assert marks_list[0].marks_obtained == 85


def test_marks_repository(db_session):
    sess, _ = db_session
    repo = MarksRepository(sess)
    assert repo.list_by_section_exam(1, 1, 1, 1) == []


def test_marks_repository_get_by_student_subject_exam(db_session):
    sess, _ = db_session
    repo = MarksRepository(sess)
    assert repo.get_by_student_subject_exam(1, 1, 1) is None


def test_schema_version_is_12():
    from database import SCHEMA_VERSION
    assert SCHEMA_VERSION == 12


def test_marks_table_created(db_session):
    sess, engine = db_session
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "marks" in tables


def test_audit_log_created_on_insert(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=85,
        status="saved",
    )
    # Check audit log was created
    sess = marks_service.session
    audit_logs = sess.query(MarksAuditLog).filter_by(marks_id=marks.id).all()
    assert len(audit_logs) == 1
    audit = audit_logs[0]
    assert audit.action == "insert"
    assert audit.field_changed == "marks_obtained,status"
    assert audit.old_value is None
    assert audit.new_value == "85"
    assert audit.old_status is None
    assert audit.new_status == "saved"
    assert audit.student_id == data["student"].id
    assert audit.subject_id == data["subject"].id
    assert audit.exam_type_id == data["exam_type"].id


def test_audit_log_created_on_update(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    
    sess = marks_service.session
    sess.expire_all()
    audit_logs = sess.query(MarksAuditLog).filter_by(marks_id=marks.id).order_by(MarksAuditLog.created_at.desc()).all()
    assert len(audit_logs) == 2
    
    # Most recent first (desc order)
    update_audit = audit_logs[0]
    assert update_audit.action == "update"
    assert update_audit.old_value == "75"
    assert update_audit.new_value == "85"
    assert update_audit.old_status == "saved"
    assert update_audit.new_status == "saved"
    
    # Older insert
    insert_audit = audit_logs[1]
    assert insert_audit.action == "insert"
    assert insert_audit.new_value == "75"
    assert insert_audit.new_status == "saved"


def test_audit_log_not_created_on_no_change(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    # Update with same values
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    
    sess = marks_service.session
    audit_logs = sess.query(MarksAuditLog).filter_by(marks_id=marks.id).all()
    # Should only have insert, no update since nothing changed
    assert len(audit_logs) == 1


def test_audit_log_created_on_lock(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_id = marks.id
    marks_service.lock_marks(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    
    sess = marks_service.session
    sess.expire_all()
    audit_logs = sess.query(MarksAuditLog).filter_by(marks_id=marks_id).order_by(MarksAuditLog.created_at.desc()).all()
    assert len(audit_logs) == 2
    
    lock_audit = audit_logs[0]
    assert lock_audit.action == "lock"
    assert lock_audit.old_status == "saved"
    assert lock_audit.new_status == "locked"


def test_audit_log_created_on_unlock(marks_service, setup_data):
    data = setup_data
    marks = marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "locked")
    marks_id = marks.id
    marks_service.unlock_marks(data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id)
    
    sess = marks_service.session
    sess.expire_all()
    audit_logs = sess.query(MarksAuditLog).filter_by(marks_id=marks_id).order_by(MarksAuditLog.created_at.desc()).all()
    assert len(audit_logs) == 2
    
    unlock_audit = audit_logs[0]
    assert unlock_audit.action == "unlock"
    assert unlock_audit.old_status == "locked"
    assert unlock_audit.new_status == "saved"


def test_audit_log_includes_user_info(marks_service, setup_data):
    data = setup_data
    # Create a user first
    from models import User
    import hashlib
    user = User(
        username="teacher_a",
        email="teacher@example.com",
        password_hash=hashlib.sha256("password".encode()).hexdigest(),
        full_name="Teacher A",
        role="teacher",
        is_active=True,
    )
    data["student_svc"].session.add(user)
    data["student_svc"].session.flush()
    
    # Assign teacher to class/subject
    from models import UserClassSubjectMapping
    mapping = UserClassSubjectMapping(
        user_id=user.id,
        class_id=data["class"].id,
        subject_id=data["subject"].id,
        session_id=data["session"].id,
        section_id=data["section"].id,
        is_class_teacher=False,
    )
    data["student_svc"].session.add(mapping)
    data["student_svc"].session.commit()
    
    marks = marks_service.save_marks(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=85,
        status="saved",
        user_id=user.id,
        user_name="Teacher A",
    )
    sess = marks_service.session
    audit_logs = sess.query(MarksAuditLog).filter_by(marks_id=marks.id).all()
    assert len(audit_logs) == 1
    audit = audit_logs[0]
    assert audit.user_id == user.id
    assert audit.user_name == "Teacher A"


def test_audit_log_repository(db_session):
    sess, _ = db_session
    repo = MarksAuditLogRepository(sess)
    assert repo.list_all() == []
    assert repo.list_recent() == []


def test_audit_log_table_created(db_session):
    sess, engine = db_session
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "marks_audit_log" in tables


def test_save_draft(marks_service, setup_data):
    data = setup_data
    draft = marks_service.save_draft(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=85,
        status="draft",
    )
    assert draft.id is not None
    assert draft.student_id == data["student"].id
    assert draft.subject_id == data["subject"].id
    assert draft.exam_type_id == data["exam_type"].id
    assert draft.marks_obtained == 85
    assert draft.max_marks == 100
    assert draft.status == "draft"
    assert draft.session_id == data["session"].id
    assert draft.class_id == data["class"].id
    assert draft.section_id == data["section"].id


def test_save_draft_absent(marks_service, setup_data):
    data = setup_data
    draft = marks_service.save_draft(
        data["student"].id,
        data["subject"].id,
        data["exam_type"].id,
        marks_obtained=None,
        status="absent",
    )
    assert draft.marks_obtained is None
    assert draft.status == "absent"


def test_update_existing_draft(marks_service, setup_data):
    data = setup_data
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    draft = marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 85, "draft")
    assert draft.marks_obtained == 85


def test_draft_validation_max_marks(marks_service, setup_data):
    data = setup_data
    with pytest.raises(ValueError, match="between 0 and 100"):
        marks_service.save_draft(
            data["student"].id,
            data["subject"].id,
            data["exam_type"].id,
            marks_obtained=150,
        )


def test_get_draft(marks_service, setup_data):
    data = setup_data
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    draft = marks_service.get_draft(data["student"].id, data["subject"].id, data["exam_type"].id)
    assert draft is not None
    assert draft.marks_obtained == 75


def test_get_nonexistent_draft(marks_service, setup_data):
    data = setup_data
    draft = marks_service.get_draft(999, data["subject"].id, data["exam_type"].id)
    assert draft is None


def test_list_drafts_for_entry(marks_service, setup_data):
    data = setup_data
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    marks_service.save_draft(data["student2"].id, data["subject"].id, data["exam_type"].id, 85, "pending")
    
    drafts = marks_service.list_drafts_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(drafts) == 2


def test_discard_draft(marks_service, setup_data):
    data = setup_data
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    result = marks_service.discard_draft(data["student"].id, data["subject"].id, data["exam_type"].id)
    assert result is True
    
    draft = marks_service.get_draft(data["student"].id, data["subject"].id, data["exam_type"].id)
    assert draft is None


def test_discard_nonexistent_draft(marks_service, setup_data):
    data = setup_data
    result = marks_service.discard_draft(999, data["subject"].id, data["exam_type"].id)
    assert result is False


def test_discard_all_drafts(marks_service, setup_data):
    data = setup_data
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    marks_service.save_draft(data["student2"].id, data["subject"].id, data["exam_type"].id, 85, "pending")
    
    count = marks_service.discard_all_drafts(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert count == 2
    
    drafts = marks_service.list_drafts_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(drafts) == 0


def test_promote_drafts_to_marks(marks_service, setup_data):
    data = setup_data
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    marks_service.save_draft(data["student2"].id, data["subject"].id, data["exam_type"].id, 85, "pending")
    
    created, errors = marks_service.promote_drafts_to_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(created) == 2
    assert len(errors) == 0
    
    # Verify drafts are cleared
    drafts = marks_service.list_drafts_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(drafts) == 0
    
    # Verify marks are created
    marks_list = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(marks_list) == 2


def test_promote_drafts_overwrites_existing_marks(marks_service, setup_data):
    data = setup_data
    # First save official marks
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 50, "saved")
    # Then save draft with different value
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 90, "draft")
    
    created, errors = marks_service.promote_drafts_to_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(created) == 1
    assert len(errors) == 0
    
    # Verify official marks updated to draft value
    marks_list = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(marks_list) == 1
    assert marks_list[0].marks_obtained == 90


def test_promote_drafts_empty(marks_service, setup_data):
    data = setup_data
    created, errors = marks_service.promote_drafts_to_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(created) == 0
    assert len(errors) == 1
    assert "No drafts" in errors[0]


def test_get_draft_vs_saved(marks_service, setup_data):
    data = setup_data
    # Only draft
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    result = marks_service.get_draft_vs_saved(data["student"].id, data["subject"].id, data["exam_type"].id)
    assert result["draft"] is not None
    assert result["draft"]["marks_obtained"] == 75
    assert result["saved"] is None
    
    # Only saved
    marks_service.discard_draft(data["student"].id, data["subject"].id, data["exam_type"].id)
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 85, "saved")
    result = marks_service.get_draft_vs_saved(data["student"].id, data["subject"].id, data["exam_type"].id)
    assert result["draft"] is None
    assert result["saved"] is not None
    assert result["saved"]["marks_obtained"] == 85
    
    # Both
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 95, "pending")
    result = marks_service.get_draft_vs_saved(data["student"].id, data["subject"].id, data["exam_type"].id)
    assert result["draft"] is not None
    assert result["draft"]["marks_obtained"] == 95
    assert result["saved"] is not None
    assert result["saved"]["marks_obtained"] == 85


def test_draft_repository(db_session):
    sess, _ = db_session
    repo = MarksDraftRepository(sess)
    assert repo.list_by_section_exam(1, 1, 1, 1) == []


def test_draft_repository_get_by_student_subject_exam(db_session):
    sess, _ = db_session
    repo = MarksDraftRepository(sess)
    assert repo.get_by_student_subject_exam(1, 1, 1) is None


def test_schema_version_is_12():
    from database import SCHEMA_VERSION
    assert SCHEMA_VERSION == 12


def test_draft_table_created(db_session):
    sess, engine = db_session
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "marks_drafts" in tables


# ========================================================================
# Subject filtering tests
# ========================================================================

def test_list_marks_for_entry_with_subject_filter(marks_service, setup_data):
    data = setup_data
    # Use subject2 from fixture
    subject2 = data["subject2"]
    
    # Map subject2 to class+section
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(subject2.id, data["class"].id, data["section"].id)
    
    # Save marks for both subjects
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_service.save_marks(data["student"].id, subject2.id, data["exam_type"].id, 85, "saved")
    
    # Get marks without filter
    all_marks = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(all_marks) == 2
    
    # Get marks with subject filter
    marks_subj1 = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, data["subject"].id
    )
    assert len(marks_subj1) == 1
    assert marks_subj1[0].subject_id == data["subject"].id
    assert marks_subj1[0].marks_obtained == 75
    
    marks_subj2 = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, subject2.id
    )
    assert len(marks_subj2) == 1
    assert marks_subj2[0].subject_id == subject2.id
    assert marks_subj2[0].marks_obtained == 85


def test_list_drafts_for_entry_with_subject_filter(marks_service, setup_data):
    data = setup_data
    # Use subject2 from fixture
    subject2 = data["subject2"]
    
    # Map subject2 to class+section
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(subject2.id, data["class"].id, data["section"].id)
    
    # Save drafts for both subjects
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    marks_service.save_draft(data["student"].id, subject2.id, data["exam_type"].id, 85, "draft")
    
    # Get drafts without filter
    all_drafts = marks_service.list_drafts_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(all_drafts) == 2
    
    # Get drafts with subject filter
    drafts_subj1 = marks_service.list_drafts_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, data["subject"].id
    )
    assert len(drafts_subj1) == 1
    assert drafts_subj1[0].subject_id == data["subject"].id
    assert drafts_subj1[0].marks_obtained == 75
    
    drafts_subj2 = marks_service.list_drafts_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, subject2.id
    )
    assert len(drafts_subj2) == 1
    assert drafts_subj2[0].subject_id == subject2.id
    assert drafts_subj2[0].marks_obtained == 85


def test_lock_marks_with_subject_filter(marks_service, setup_data):
    data = setup_data
    # Use subject2 from fixture
    subject2 = data["subject2"]
    
    # Map subject2 to class+section
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(subject2.id, data["class"].id, data["section"].id)
    
    # Save marks for both subjects
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "saved")
    marks_service.save_marks(data["student"].id, subject2.id, data["exam_type"].id, 85, "saved")
    
    # Lock only subject1
    count = marks_service.lock_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, data["subject"].id
    )
    assert count == 1
    
    # Verify only subject1 is locked
    marks_list = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    for m in marks_list:
        if m.subject_id == data["subject"].id:
            assert m.status == "locked"
        else:
            assert m.status == "saved"


def test_unlock_marks_with_subject_filter(marks_service, setup_data):
    data = setup_data
    # Use subject2 from fixture
    subject2 = data["subject2"]
    
    # Map subject2 to class+section
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(subject2.id, data["class"].id, data["section"].id)
    
    # Save marks for both subjects as locked
    marks_service.save_marks(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "locked")
    marks_service.save_marks(data["student"].id, subject2.id, data["exam_type"].id, 85, "locked")
    
    # Unlock only subject1
    count = marks_service.unlock_marks(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, data["subject"].id
    )
    assert count == 1
    
    # Verify only subject1 is unlocked
    marks_list = marks_service.list_marks_for_entry(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    for m in marks_list:
        if m.subject_id == data["subject"].id:
            assert m.status == "saved"
        else:
            assert m.status == "locked"


def test_repository_list_by_section_exam_subject(marks_repo, setup_data):
    data = setup_data
    # Use subject2 from fixture
    subject2 = data["subject2"]
    
    # Save marks for both subjects
    from models import Marks
    marks1 = Marks(
        student_id=data["student"].id,
        subject_id=data["subject"].id,
        exam_type_id=data["exam_type"].id,
        session_id=data["session"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        marks_obtained=75,
        max_marks=100,
        status="saved",
    )
    marks2 = Marks(
        student_id=data["student"].id,
        subject_id=subject2.id,
        exam_type_id=data["exam_type"].id,
        session_id=data["session"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        marks_obtained=85,
        max_marks=100,
        status="saved",
    )
    data["student_svc"].session.add_all([marks1, marks2])
    data["student_svc"].session.flush()
    
    # Get marks without filter
    all_marks = marks_repo.list_by_section_exam(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id
    )
    assert len(all_marks) == 2
    
    # Get marks with subject filter
    marks_subj1 = marks_repo.list_by_section_exam_subject(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, data["subject"].id
    )
    assert len(marks_subj1) == 1
    assert marks_subj1[0].subject_id == data["subject"].id
    
    marks_subj2 = marks_repo.list_by_section_exam_subject(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, subject2.id
    )
    assert len(marks_subj2) == 1
    assert marks_subj2[0].subject_id == subject2.id


def test_draft_repository_list_by_section_exam_subject(marks_service, setup_data):
    data = setup_data
    # Use subject2 from fixture
    subject2 = data["subject2"]
    
    # Save drafts for both subjects
    marks_service.save_draft(data["student"].id, data["subject"].id, data["exam_type"].id, 75, "draft")
    marks_service.save_draft(data["student"].id, subject2.id, data["exam_type"].id, 85, "draft")
    
    # Get drafts with subject filter
    drafts_subj1 = marks_service.draft_repo.list_by_section_exam_subject(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, data["subject"].id
    )
    assert len(drafts_subj1) == 1
    assert drafts_subj1[0].subject_id == data["subject"].id
    
    drafts_subj2 = marks_service.draft_repo.list_by_section_exam_subject(
        data["session"].id, data["class"].id, data["section"].id, data["exam_type"].id, subject2.id
    )
    assert len(drafts_subj2) == 1
    assert drafts_subj2[0].subject_id == subject2.id


def test_get_subjects_for_class_section_filters_by_section(marks_service, setup_data):
    data = setup_data
    # Map subject to class 1, section 1 (exists in fixture)
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(data["subject"].id, data["class"].id, data["section"].id)
    
    # Should return subject for correct section
    subjects = marks_service.get_subjects_for_class_section(data["class"].id, data["section"].id)
    assert len(subjects) == 1
    assert subjects[0].id == data["subject"].id


def test_get_subjects_for_class_section_returns_empty_for_wrong_section(marks_service, setup_data):
    data = setup_data
    # Create a second section
    from models import Section
    section2 = Section(name="Section B", class_id=data["class"].id, is_active=True)
    data["student_svc"].session.add(section2)
    data["student_svc"].session.flush()
    
    # Map subject to class 1, section 1 only
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(data["subject"].id, data["class"].id, data["section"].id)
    
    # Should return empty for section 2
    subjects = marks_service.get_subjects_for_class_section(data["class"].id, section2.id)
    assert len(subjects) == 0


def test_subject_population_dropdown(marks_service, setup_data):
    data = setup_data
    # Initially no subjects mapped
    subjects = marks_service.get_subjects_for_class_section(data["class"].id, data["section"].id)
    assert len(subjects) == 0
    
    # Map subject
    from services import SubjectService
    subject_svc = SubjectService(data["student_svc"].session)
    subject_svc.add_section_mapping(data["subject"].id, data["class"].id, data["section"].id)
    
    # Now should return the subject
    subjects = marks_service.get_subjects_for_class_section(data["class"].id, data["section"].id)
    assert len(subjects) == 1
    assert subjects[0].id == data["subject"].id