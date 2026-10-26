from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, SchemaVersion, SCHEMA_VERSION
from models import Class, STANDARD_CLASSES
from repositories import ClassRepository
from services import ClassService


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


def test_add_and_list_class(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    cls = service.add_class("Class 1")
    assert cls.id is not None
    assert cls.name == "Class 1"
    assert cls.display_order == 1
    assert cls.is_active is True
    classes = service.list_classes()
    assert len(classes) == 1


def test_unique_class_name(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    service.add_class("Class 1")
    with pytest.raises(ValueError, match="already exists"):
        service.add_class("Class 1")


def test_auto_display_order(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    c1 = service.add_class("Class 1")
    c2 = service.add_class("Class 2")
    c3 = service.add_class("Class 3")
    assert c1.display_order == 1
    assert c2.display_order == 2
    assert c3.display_order == 3


def test_manual_display_order(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    c1 = service.add_class("Class 1", display_order=10)
    c2 = service.add_class("Class 2", display_order=5)
    c3 = service.add_class("Class 3")  # auto: max(10,5)+1 = 11
    assert c1.display_order == 10
    assert c2.display_order == 5
    assert c3.display_order == 11


def test_display_order_non_negative(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    with pytest.raises(ValueError, match="non-negative"):
        service.add_class("Bad", display_order=-1)
    with pytest.raises(ValueError, match="non-negative"):
        service.add_class("Good", display_order=0)
        service.update_class(1, display_order=-1)


def test_update_class(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    cls = service.add_class("Class 1")
    updated = service.update_class(cls.id, name="Class 1A", display_order=5, is_active=False)
    assert updated.name == "Class 1A"
    assert updated.display_order == 5
    assert updated.is_active is False


def test_update_duplicate_name_blocked(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    c1 = service.add_class("Class 1")
    service.add_class("Class 2")
    with pytest.raises(ValueError, match="already exists"):
        service.update_class(c1.id, name="Class 2")
    assert service.get_class(c1.id).name == "Class 1"


def test_deactivate_activate_class(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    cls = service.add_class("Class 1")
    assert cls.is_active is True
    service.deactivate_class(cls.id)
    assert service.get_class(cls.id).is_active is False
    service.activate_class(cls.id)
    assert service.get_class(cls.id).is_active is True


def test_reorder_classes(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    c1 = service.add_class("Class 1")  # order 1
    c2 = service.add_class("Class 2")  # order 2
    c3 = service.add_class("Class 3")  # order 3
    # Reorder: c3 first, then c1, then c2
    service.reorder_classes([(c3.id, 1), (c1.id, 2), (c2.id, 3)])
    classes = service.list_classes()
    assert classes[0].id == c3.id
    assert classes[1].id == c1.id
    assert classes[2].id == c2.id


def test_reorder_invalid_order(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    c1 = service.add_class("Class 1")
    with pytest.raises(ValueError, match="non-negative"):
        service.reorder_classes([(c1.id, -1)])


def test_bulk_import(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    names = ["Nursery", "LKG", "UKG", "Class 1", "Class 2"]
    created, errors = service.bulk_import(names)
    assert len(created) == 5
    assert len(errors) == 0
    classes = service.list_classes()
    assert len(classes) == 5


def test_bulk_import_skip_duplicates(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    service.add_class("Class 1")
    names = ["Class 1", "Class 2", "Class 3"]
    created, errors = service.bulk_import(names, skip_duplicates=True)
    assert len(created) == 2
    assert any("Duplicate skipped" in e for e in errors)


def test_bulk_import_reject_duplicates(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    service.add_class("Class 1")
    names = ["Class 1", "Class 2"]
    created, errors = service.bulk_import(names, skip_duplicates=False)
    assert len(created) == 1
    assert any("Duplicate:" in e for e in errors)


def test_bulk_import_empty_names(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    names = ["Class 1", "", "   ", "Class 2"]
    created, errors = service.bulk_import(names)
    assert len(created) == 2
    assert any("Empty name skipped" in e for e in errors)


def test_list_active_only(db_session):
    sess, _ = db_session
    service = ClassService(sess)
    service.add_class("Class 1")
    c2 = service.add_class("Class 2")
    service.deactivate_class(c2.id)
    active = service.list_active_classes()
    assert len(active) == 1
    assert active[0].name == "Class 1"


def test_data_persistence_across_sessions(db_session):
    sess, engine = db_session
    service = ClassService(sess)
    service.add_class("Class 1")
    sess.close()
    new_sess = sessionmaker(bind=engine)()
    try:
        rows = new_sess.query(Class).all()
        assert len(rows) == 1
        assert rows[0].name == "Class 1"
    finally:
        new_sess.close()


def test_standard_classes_list(db_session):
    # Just verify the list exists and contains expected items
    assert "Nursery" in STANDARD_CLASSES
    assert "LKG" in STANDARD_CLASSES
    assert "Class 1" in STANDARD_CLASSES
    assert "Class 12" in STANDARD_CLASSES
    assert len(STANDARD_CLASSES) == 15


def test_class_repository(db_session):
    sess, _ = db_session
    repo = ClassRepository(sess)
    assert repo.list_all() == []
    assert repo.list_active() == []
    assert repo.get_max_display_order() == 0
    assert not repo.exists_by_name("Class 1")