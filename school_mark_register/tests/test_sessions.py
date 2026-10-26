from __future__ import annotations

import os
import tempfile
import time
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, SchemaVersion, SCHEMA_VERSION, backup_database, migrate_to_latest
from models import AcademicRecord, AcademicSession
from repositories import SessionRepository
from services import ClassService, SessionService


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


def test_add_and_list_session(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    session_obj = service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30), "active", True)
    assert session_obj.id is not None
    sessions = service.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].is_current is True


def test_unique_session_name(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))
    with pytest.raises(ValueError, match="already exists"):
        service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))


def test_only_one_current_session(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("2025/2026", date(2025, 9, 1), date(2026, 6, 30), is_current=True)
    s2 = service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30), is_current=True)
    sess.expire_all()
    assert service.repo.current().id == s2.id
    assert service.get_session(s1.id).is_current is False


def test_date_validation(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    with pytest.raises(ValueError):
        service.add_session("Bad", date(2027, 1, 1), date(2026, 1, 1))


def test_invalid_status(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    with pytest.raises(ValueError):
        service.add_session("X", date(2026, 9, 1), date(2027, 6, 30), status="weird")


def test_delete_blocked_when_records_exist(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    session_obj = service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))
    # Need class_id for AcademicRecord
    class_service = ClassService(sess)
    class_obj = class_service.add_class("Class 1")
    sess.add(AcademicRecord(session_id=session_obj.id, class_id=class_obj.id, student_name="Alice", subject="Math", score=85))
    sess.commit()
    with pytest.raises(ValueError, match="referenced by academic records"):
        service.delete_session(session_obj.id)
    assert service.get_session(session_obj.id) is not None


def test_delete_allowed_when_no_records(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    session_obj = service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))
    service.delete_session(session_obj.id)
    assert service.get_session(session_obj.id) is None


def test_archive_current_blocked(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    session_obj = service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30), is_current=True)
    with pytest.raises(ValueError, match="current session"):
        service.archive_session(session_obj.id)


def test_session_switching(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("2025/2026", date(2025, 9, 1), date(2026, 6, 30), is_current=True)
    s2 = service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))
    service.set_current(s2.id)
    assert service.repo.current().id == s2.id
    assert service.get_session(s1.id).is_current is False


def test_data_persistence_across_sessions(db_session):
    sess, engine = db_session
    service = SessionService(sess)
    service.add_session("2026/2027", date(2026, 9, 1), date(2027, 6, 30))
    sess.close()
    new_sess = sessionmaker(bind=engine)()
    try:
        rows = new_sess.query(AcademicSession).all()
        assert len(rows) == 1
        assert rows[0].name == "2026/2027"
    finally:
        new_sess.close()


def test_repository_session_repository(db_session):
    sess, _ = db_session
    repo = SessionRepository(sess)
    assert repo.list_all() == []
    assert repo.current() is None


def test_always_exactly_one_current_when_sessions_exist(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("A", date(2026, 9, 1), date(2027, 6, 30), is_current=False)
    assert service.repo.current().id == s1.id


def test_delete_current_promotes_another(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("A", date(2026, 9, 1), date(2027, 6, 30), is_current=True)
    s2 = service.add_session("B", date(2026, 9, 1), date(2027, 6, 30))
    service.delete_session(s1.id)
    assert service.repo.current().id == s2.id
    assert len(service.list_sessions()) == 1


def test_failed_add_rolls_back(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    service.add_session("A", date(2026, 9, 1), date(2027, 6, 30), is_current=True)
    with pytest.raises(ValueError, match="already exists"):
        service.add_session("A", date(2026, 9, 1), date(2027, 6, 30))
    sessions = service.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "A"
    assert service.repo.current() is not None


def test_update_duplicate_name_blocked_and_unchanged(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("A", date(2026, 9, 1), date(2027, 6, 30))
    service.add_session("B", date(2026, 9, 1), date(2027, 6, 30))
    with pytest.raises(ValueError, match="already exists"):
        service.update_session(s1.id, name="B")
    assert service.get_session(s1.id).name == "A"


def test_update_end_before_start_blocked_and_unchanged(db_session):
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("A", date(2026, 9, 1), date(2027, 6, 30))
    with pytest.raises(ValueError):
        service.update_session(s1.id, start_date=date(2028, 1, 1))
    assert service.get_session(s1.id).start_date == date(2026, 9, 1)


def test_db_level_foreign_key_blocks_deletion(db_session):
    # FK protection is enforced by AcademicRecord.session_id (ondelete=RESTRICT)
    # plus PRAGMA foreign_keys=ON in database.py. The service-level rule is
    # covered by test_delete_blocked_when_records_exist.
    sess, _ = db_session
    service = SessionService(sess)
    s1 = service.add_session("A", date(2026, 9, 1), date(2027, 6, 30))
    class_service = ClassService(sess)
    class_obj = class_service.add_class("Class 1")
    sess.add(AcademicRecord(session_id=s1.id, class_id=class_obj.id, student_name="Alice", subject="Math", score=85))
    sess.commit()
    with pytest.raises(ValueError, match="referenced by academic records"):
        service.delete_session(s1.id)
    assert service.get_session(s1.id) is not None


def test_schema_version_can_be_recorded(db_session):
    sess, _ = db_session
    sess.add(SchemaVersion(version=SCHEMA_VERSION))
    sess.commit()
    row = sess.get(SchemaVersion, SCHEMA_VERSION)
    assert row is not None
    assert row.version == SCHEMA_VERSION


def test_backup_creates_unique_files_and_restore_rejects_missing(tmp_path):
    import database

    real_dir = database.DATA_DIR
    real_db = database.DB_PATH
    test_dir = tmp_path / "data"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_db = test_dir / "test.db"
    test_engine = create_engine(f"sqlite:///{test_db}")
    database.DATA_DIR = test_dir
    database.DB_PATH = test_db
    try:
        import models  # noqa: F401  register models on Base
        Base.metadata.create_all(test_engine)
        test_session = sessionmaker(
            bind=test_engine, autoflush=False, autocommit=False
        )()
        test_session.add(SchemaVersion(version=SCHEMA_VERSION))
        test_session.commit()
        test_session.close()
        b1 = database.backup_database()
        time.sleep(1.5)
        b2 = database.backup_database()
        assert b1 is not None and b2 is not None
        assert b1.exists() and b2.exists()
        assert b1 != b2
        with pytest.raises(FileNotFoundError):
            database.restore_database(test_dir / "nonexistent.db.bak")
    finally:
        test_engine.dispose()
        for p in database.DATA_DIR.glob("*.db.bak"):
            p.unlink(missing_ok=True)
        database.DATA_DIR = real_dir
        database.DB_PATH = real_db
