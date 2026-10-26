from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "mark_register.db"
DB_URI = f"sqlite:///{DB_PATH}"

Base = declarative_base()

SCHEMA_VERSION = 12


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


engine = create_engine(DB_URI, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def backup_database() -> Path | None:
    """Back up the existing database before any schema change. Never overwrites."""
    if not DB_PATH.exists():
        return None
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = DATA_DIR / f"mark_register_{stamp}.db.bak"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def restore_database(backup_path: Path | str) -> None:
    """Restore the live database from a backup file. Explicit, never automatic."""
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, DB_PATH)


def _ensure_pt1_pt2_components(session: Session) -> int:
    """Idempotent: create missing PT1/PT2 exam components for all active subjects.

    PT1 and PT2 exam types originally had no component configurations,
    which prevented students from loading in the Marks Entry grid.
    This migration adds the missing components without touching any
    student records, marks, drafts, or audit history.

    Returns the number of components created.
    """
    from models import ExamComponent, ExamType, Subject

    pt1 = session.query(ExamType).filter_by(name="PT1").first()
    pt2 = session.query(ExamType).filter_by(name="PT2").first()
    if not pt1 or not pt2:
        return 0

    core_subjects = {"ENGLISH", "MATHS", "HINDI", "SCIENCE", "SOCIAL SCIENCE"}
    computer_subjects = {"COMPUTER", "COMPUTER SCIENCE"}
    french_subjects = {"FRENCH"}
    gk_subjects = {"GK", "GENERAL KNOWLEDGE"}

    subjects = session.query(Subject).filter_by(is_active=True).all()
    created = 0

    for subject in subjects:
        name = subject.name.upper()
        if name in gk_subjects:
            pt1_config = [("PT Paper", "PT", 25, 1)]
            pt2_config = [("PT Paper", "PT", 25, 1)]
        elif name in french_subjects:
            pt1_config = [("Periodic Test 1", "PT1", 25, 1)]
            pt2_config = [("Periodic Test 2", "PT2", 25, 1)]
        elif name in computer_subjects:
            pt1_config = [("Periodic Test 1", "PT1", 25, 1)]
            pt2_config = [("Periodic Test 2", "PT2", 25, 1)]
        else:
            pt1_config = [("Periodic Test 1", "PT1", 25, 1)]
            pt2_config = [("Periodic Test 2", "PT2", 25, 1)]

        for exam_type, config in ((pt1, pt1_config), (pt2, pt2_config)):
            for comp_name, comp_code, comp_max, comp_order in config:
                existing = session.query(ExamComponent).filter_by(
                    exam_type_id=exam_type.id,
                    subject_id=subject.id,
                    name=comp_name,
                ).first()
                if not existing:
                    session.add(ExamComponent(
                        exam_type_id=exam_type.id,
                        subject_id=subject.id,
                        name=comp_name,
                        code=comp_code,
                        max_marks=comp_max,
                        display_order=comp_order,
                        is_active=True,
                    ))
                    created += 1

    session.commit()
    return created


def _migrate_component_marks_status() -> None:
    """Migrate component_marks table to accept 'converted' status.

    SQLite does not support ALTER TABLE to modify constraints.
    Uses the standard table-rebuild pattern to update the CheckConstraint
    while preserving all existing data (marks, drafts, audit history).
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        # Check if the constraint already allows 'converted'
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='component_marks'"
        )).fetchone()
        if row and "converted" in (row[0] or ""):
            return  # Already migrated

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1. Drop user-defined indexes (skip auto-indexes from UNIQUE/PK constraints)
            indexes = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='component_marks'"
            )).fetchall()
            for idx in indexes:
                idx_name = idx[0]
                if not idx_name.startswith("sqlite_autoindex_"):
                    conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))

            # 2. Rename old table
            conn.execute(text("ALTER TABLE component_marks RENAME TO component_marks_old"))
            # 3. Recreate component_marks with updated constraint (via create_all on this connection)
            trans.commit()
            trans = conn.begin()
            # Create via raw SQL matching the model
            conn.execute(text(
                "CREATE TABLE component_marks ("
                "id INTEGER NOT NULL, student_id INTEGER NOT NULL, "
                "subject_id INTEGER NOT NULL, exam_type_id INTEGER NOT NULL, "
                "component_id INTEGER NOT NULL, session_id INTEGER NOT NULL, "
                "class_id INTEGER NOT NULL, section_id INTEGER NOT NULL, "
                "marks_obtained INTEGER, max_marks INTEGER NOT NULL, "
                "status VARCHAR(20) NOT NULL DEFAULT 'pending', "
                "created_at TIMESTAMP, updated_at TIMESTAMP, "
                "PRIMARY KEY (id), "
                "CONSTRAINT uq_component_marks_student_component "
                "UNIQUE (student_id, component_id), "
                "CONSTRAINT ck_comp_marks_max_marks CHECK (max_marks > 0), "
                "CONSTRAINT ck_comp_marks_range "
                "CHECK (marks_obtained IS NULL OR (marks_obtained >= 0 AND marks_obtained <= max_marks)), "
                "CONSTRAINT ck_comp_marks_status "
                "CHECK (status IN ('pending', 'absent', 'saved', 'locked', 'converted')), "
                "FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE, "
                "FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE, "
                "FOREIGN KEY (exam_type_id) REFERENCES exam_types(id) ON DELETE CASCADE, "
                "FOREIGN KEY (component_id) REFERENCES exam_components(id) ON DELETE CASCADE, "
                "FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT, "
                "FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE RESTRICT, "
                "FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE RESTRICT"
                ")"
            ))
            # 4. Copy data
            conn.execute(text(
                "INSERT INTO component_marks "
                "(id, student_id, subject_id, exam_type_id, component_id, "
                " session_id, class_id, section_id, marks_obtained, max_marks, "
                " status, created_at, updated_at) "
                "SELECT id, student_id, subject_id, exam_type_id, component_id, "
                "session_id, class_id, section_id, marks_obtained, max_marks, "
                "status, created_at, updated_at FROM component_marks_old"
            ))
            # 5. Drop old table
            conn.execute(text("DROP TABLE component_marks_old"))
            trans.commit()
        except Exception:
            trans.rollback()
            raise


def migrate_to_latest() -> int:
    """Idempotent schema initialization / migration.

    create_all() only creates missing tables (never drops or resets data).
    Records the current schema version for future incremental migrations.
    Returns the applied schema version.
    """
    import models  # noqa: F401  register all SQLAlchemy models on Base

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    backup_database()
    Base.metadata.create_all(engine)
    _migrate_component_marks_status()

    with SessionLocal() as session:
        # Ensure PT1/PT2 components exist for all active subjects (idempotent migration)
        _ensure_pt1_pt2_components(session)

        # Find any existing schema version row and update it, or create new
        row = session.query(SchemaVersion).first()
        if row is None:
            session.add(SchemaVersion(version=SCHEMA_VERSION))
        else:
            row.version = SCHEMA_VERSION
        session.commit()
    return SCHEMA_VERSION


def init_database() -> None:
    """Safely initialize the schema. Never resets or deletes existing data."""
    migrate_to_latest()


def get_session() -> Session:
    return SessionLocal()
