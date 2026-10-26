from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import ExamType
from repositories import ExamTypeRepository
from services import ExamTypeService


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
def exam_service(db_session):
    sess, _ = db_session
    return ExamTypeService(sess)


@pytest.fixture
def exam_repo(db_session):
    sess, _ = db_session
    return ExamTypeRepository(sess)


def test_add_and_list_exam_type(exam_service):
    et = exam_service.add_exam_type("Mid-term", "MT", "Mid-term Examination", 100, 0.5)
    assert et.id is not None
    assert et.name == "Mid-term"
    assert et.code == "MT"
    assert et.description == "Mid-term Examination"
    assert et.max_marks == 100
    assert et.weightage == 0.5
    assert et.is_active is True
    exam_types = exam_service.list_exam_types()
    assert len(exam_types) == 1


def test_unique_exam_type_name(exam_service):
    exam_service.add_exam_type("Mid-term", "MT")
    with pytest.raises(ValueError, match="already exists"):
        exam_service.add_exam_type("Mid-term", "MT2")


def test_unique_exam_type_code(exam_service):
    exam_service.add_exam_type("Mid-term", "MT")
    with pytest.raises(ValueError, match="code.*already exists"):
        exam_service.add_exam_type("Final", "MT")


def test_update_exam_type(exam_service):
    et = exam_service.add_exam_type("Mid-term", "MT")
    updated = exam_service.update_exam_type(
        et.id,
        name="Mid-term Exam",
        code="MTE",
        description="Updated description",
        max_marks=150,
        weightage=0.75,
        is_active=False,
    )
    assert updated.name == "Mid-term Exam"
    assert updated.code == "MTE"
    assert updated.description == "Updated description"
    assert updated.max_marks == 150
    assert updated.weightage == 0.75
    assert updated.is_active is False


def test_deactivate_activate_exam_type(exam_service):
    et = exam_service.add_exam_type("Mid-term", "MT")
    assert et.is_active is True
    exam_service.deactivate_exam_type(et.id)
    assert exam_service.get_exam_type(et.id).is_active is False
    exam_service.activate_exam_type(et.id)
    assert exam_service.get_exam_type(et.id).is_active is True


def test_auto_display_order(exam_service):
    et1 = exam_service.add_exam_type("Mid-term", "MT")
    et2 = exam_service.add_exam_type("Final", "FIN")
    et3 = exam_service.add_exam_type("Unit Test", "UT")
    assert et1.display_order == 1
    assert et2.display_order == 2
    assert et3.display_order == 3


def test_manual_display_order(exam_service):
    et1 = exam_service.add_exam_type("Mid-term", "MT", display_order=10)
    et2 = exam_service.add_exam_type("Final", "FIN", display_order=5)
    et3 = exam_service.add_exam_type("Unit Test", "UT", display_order=1)
    assert et1.display_order == 10
    assert et2.display_order == 5
    assert et3.display_order == 1


def test_display_order_non_negative(exam_service):
    with pytest.raises(ValueError, match="must be non-negative"):
        exam_service.add_exam_type("Test", "T", display_order=-1)


def test_max_marks_validation(exam_service):
    with pytest.raises(ValueError, match="must be positive"):
        exam_service.add_exam_type("Test", "T", max_marks=0)
    with pytest.raises(ValueError, match="must be positive"):
        exam_service.add_exam_type("Test", "T", max_marks=-10)


def test_weightage_validation(exam_service):
    with pytest.raises(ValueError, match="cannot be negative"):
        exam_service.add_exam_type("Test", "T", weightage=-0.5)


def test_reorder_exam_types(exam_service):
    et1 = exam_service.add_exam_type("Mid-term", "MT")
    et2 = exam_service.add_exam_type("Final", "FIN")
    et3 = exam_service.add_exam_type("Unit Test", "UT")

    exam_service.reorder_exam_types([(et1.id, 3), (et2.id, 1), (et3.id, 2)])

    updated = exam_service.list_exam_types()
    order_map = {et.name: et.display_order for et in updated}
    assert order_map == {"Final": 1, "Unit Test": 2, "Mid-term": 3}


def test_reorder_invalid_order(exam_service):
    et = exam_service.add_exam_type("Mid-term", "MT")
    with pytest.raises(ValueError, match="must be non-negative"):
        exam_service.reorder_exam_types([(et.id, -1)])


def test_bulk_import_exam_types(exam_service):
    exam_types = [
        {"name": "Mid-term", "code": "MT", "description": "Mid-term Examination", "max_marks": 100, "weightage": 0.5, "is_active": True},
        {"name": "Final", "code": "FIN", "description": "Final Examination", "max_marks": 100, "weightage": 1.0, "is_active": True},
        {"name": "Unit Test", "code": "UT", "description": "Unit Test", "max_marks": 50, "weightage": 0.25, "is_active": True},
    ]
    created, errors = exam_service.bulk_import(exam_types)
    assert len(created) == 3
    assert len(errors) == 0
    exam_types_list = exam_service.list_exam_types()
    assert len(exam_types_list) == 3


def test_bulk_import_skip_duplicates(exam_service):
    exam_service.add_exam_type("Mid-term", "MT")
    exam_types = [
        {"name": "Mid-term", "code": "MT", "is_active": True},
        {"name": "Final", "code": "FIN", "is_active": True},
    ]
    created, errors = exam_service.bulk_import(exam_types, skip_duplicates=True)
    assert len(created) == 1
    assert any("Duplicate skipped" in e for e in errors)


def test_bulk_import_reject_duplicates(exam_service):
    exam_service.add_exam_type("Mid-term", "MT")
    exam_types = [
        {"name": "Mid-term", "code": "MT"},
        {"name": "Final", "code": "FIN"},
    ]
    created, errors = exam_service.bulk_import(exam_types, skip_duplicates=False)
    assert len(created) == 1
    assert any("Duplicate" in e for e in errors)


def test_export_exam_types_csv(exam_service):
    exam_service.add_exam_type("Mid-term", "MT", "Mid-term Examination", 100, 0.5, True)
    exam_service.add_exam_type("Final", "FIN", "Final Examination", 100, 1.0, False)
    csv_content = exam_service.export_exam_types_to_csv()
    assert "Mid-term" in csv_content
    assert "MT" in csv_content
    assert "Final" in csv_content
    assert "FIN" in csv_content
    assert "100" in csv_content
    assert "0.5" in csv_content


def test_data_persistence_across_sessions(exam_service):
    exam_service.add_exam_type("Mid-term", "MT")
    engine = exam_service.session.get_bind()
    exam_service.session.close()
    new_sess = sessionmaker(bind=engine)()
    try:
        rows = new_sess.query(ExamType).all()
        assert len(rows) == 1
        assert rows[0].name == "Mid-term"
        assert rows[0].code == "MT"
    finally:
        new_sess.close()


def test_exam_type_repository(db_session):
    sess, _ = db_session
    repo = ExamTypeRepository(sess)
    assert repo.list_all() == []
    assert repo.list_active() == []
    assert not repo.exists_by_name("Mid-term")
    assert not repo.exists_by_code("MT")


def test_schema_version_is_12():
    from database import SCHEMA_VERSION
    assert SCHEMA_VERSION == 12


def test_exam_type_table_created(db_session):
    sess, engine = db_session
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "exam_types" in tables