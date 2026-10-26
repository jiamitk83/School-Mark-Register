from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Standard class names for convenience (not enforced at DB level)
STANDARD_CLASSES = [
    "Nursery", "LKG", "UKG",
    "Class 1", "Class 2", "Class 3", "Class 4", "Class 5",
    "Class 6", "Class 7", "Class 8", "Class 9", "Class 10",
    "Class 11", "Class 12",
]


class AcademicSession(Base):
    __tablename__ = "academic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    records: Mapped[list["AcademicRecord"]] = relationship(
        "AcademicRecord", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_session_dates"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_session_status"),
    )


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    __table_args__ = (
        CheckConstraint("display_order >= 0", name="ck_class_display_order"),
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    __table_args__ = (
        CheckConstraint("display_order >= 0", name="ck_section_display_order"),
        # Case-insensitive unique constraint on (class_id, name)
        # SQLite doesn't support case-insensitive unique constraints directly,
        # so we'll enforce at application level
    )


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    class_mappings: Mapped[list["SubjectClassMapping"]] = relationship(
        "SubjectClassMapping", back_populates="subject", cascade="all, delete-orphan"
    )
    section_mappings: Mapped[list["SubjectSectionMapping"]] = relationship(
        "SubjectSectionMapping", back_populates="subject", cascade="all, delete-orphan"
    )


class SubjectClassMapping(Base):
    __tablename__ = "subject_class_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="class_mappings")
    class_: Mapped["Class"] = relationship("Class")

    __table_args__ = (
        UniqueConstraint("subject_id", "class_id", name="uq_subject_class"),
    )


class SubjectSectionMapping(Base):
    __tablename__ = "subject_section_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="section_mappings")
    class_: Mapped["Class"] = relationship("Class")
    section: Mapped["Section"] = relationship("Section")

    __table_args__ = (
        UniqueConstraint("subject_id", "section_id", name="uq_subject_section"),
    )


class AcademicRecord(Base):
    __tablename__ = "academic_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    student_name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    session: Mapped["AcademicSession"] = relationship("AcademicSession", back_populates="records")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    roll_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    father_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("session_id", "class_id", "section_id", "roll_number", name="uq_student_roll"),
    )


class ExamType(Base):
    __tablename__ = "exam_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    weightage: Mapped[float] = mapped_column(default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    components: Mapped[list["ExamComponent"]] = relationship(
        "ExamComponent", back_populates="exam_type", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_exam_max_marks"),
        CheckConstraint("weightage >= 0", name="ck_exam_weightage"),
        CheckConstraint("display_order >= 0", name="ck_exam_display_order"),
    )


class ExamComponent(Base):
    __tablename__ = "exam_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_type_id: Mapped[int] = mapped_column(
        ForeignKey("exam_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    exam_type: Mapped["ExamType"] = relationship("ExamType", back_populates="components")
    subject: Mapped["Subject | None"] = relationship("Subject")

    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_component_max_marks"),
        CheckConstraint("display_order >= 0", name="ck_component_display_order"),
    )


class ComponentMarks(Base):
    __tablename__ = "component_marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_type_id: Mapped[int] = mapped_column(
        ForeignKey("exam_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_id: Mapped[int] = mapped_column(
        ForeignKey("exam_components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    marks_obtained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")
    exam_type: Mapped["ExamType"] = relationship("ExamType")
    component: Mapped["ExamComponent"] = relationship("ExamComponent")

    __table_args__ = (
        UniqueConstraint("student_id", "component_id", name="uq_component_marks_student_component"),
        CheckConstraint("max_marks > 0", name="ck_comp_marks_max_marks"),
        CheckConstraint("marks_obtained IS NULL OR (marks_obtained >= 0 AND marks_obtained <= max_marks)", name="ck_comp_marks_range"),
        CheckConstraint("status IN ('pending', 'absent', 'saved', 'locked', 'converted')", name="ck_comp_marks_status"),
    )


class Marks(Base):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_type_id: Mapped[int] = mapped_column(
        ForeignKey("exam_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    marks_obtained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")
    exam_type: Mapped["ExamType"] = relationship("ExamType")

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "exam_type_id", name="uq_marks_student_subject_exam"),
        CheckConstraint("max_marks > 0", name="ck_marks_max_marks"),
        CheckConstraint("marks_obtained IS NULL OR (marks_obtained >= 0 AND marks_obtained <= max_marks)", name="ck_marks_range"),
        CheckConstraint("status IN ('pending', 'absent', 'saved', 'locked')", name="ck_marks_status"),
    )


class MarksAuditLog(Base):
    __tablename__ = "marks_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marks_id: Mapped[int] = mapped_column(
        ForeignKey("marks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exam_type_id: Mapped[int] = mapped_column(
        ForeignKey("exam_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    field_changed: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    marks: Mapped["Marks"] = relationship("Marks")
    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")
    exam_type: Mapped["ExamType"] = relationship("ExamType")
    user: Mapped["User"] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        CheckConstraint("action IN ('insert', 'update', 'delete', 'lock', 'unlock', 'bulk_update')", name="ck_audit_action"),
    )


class MarksDraft(Base):
    __tablename__ = "marks_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_type_id: Mapped[int] = mapped_column(
        ForeignKey("exam_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    marks_obtained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    marks_id: Mapped[int | None] = mapped_column(
        ForeignKey("marks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")
    exam_type: Mapped["ExamType"] = relationship("ExamType")
    marks: Mapped["Marks"] = relationship("Marks")

    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_draft_max_marks"),
        CheckConstraint("marks_obtained IS NULL OR (marks_obtained >= 0 AND marks_obtained <= max_marks)", name="ck_draft_range"),
        CheckConstraint("status IN ('draft', 'pending', 'absent')", name="ck_draft_status"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="teacher", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    class_subject_mappings: Mapped[list["UserClassSubjectMapping"]] = relationship(
        "UserClassSubjectMapping", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["MarksAuditLog"]] = relationship("MarksAuditLog", back_populates="user")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher', 'principal')", name="ck_user_role"),
    )


class UserClassSubjectMapping(Base):
    __tablename__ = "user_class_subject_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_class_teacher: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    user: Mapped["User"] = relationship("User", back_populates="class_subject_mappings")
    class_: Mapped["Class"] = relationship("Class")
    subject: Mapped["Subject"] = relationship("Subject")
    section: Mapped["Section"] = relationship("Section")
    session: Mapped["AcademicSession"] = relationship("AcademicSession")

    __table_args__ = (
        UniqueConstraint("user_id", "class_id", "subject_id", "session_id", "section_id", name="uq_user_class_subject"),
    )


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exam_type_id: Mapped[int] = mapped_column(
        ForeignKey("exam_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    component_marks_obtained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    component_max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    component_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_obtained: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percentage: Mapped[float | None] = mapped_column(nullable=True)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_gk_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    french_equivalent_80: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gk_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    student: Mapped["Student"] = relationship("Student")
    session: Mapped["AcademicSession"] = relationship("AcademicSession")
    class_: Mapped["Class"] = relationship("Class", foreign_keys=[class_id])
    section: Mapped["Section"] = relationship("Section")
    exam_type: Mapped["ExamType"] = relationship("ExamType")
    subject: Mapped["Subject"] = relationship("Subject")

    __table_args__ = (
        UniqueConstraint("student_id", "session_id", "exam_type_id", "subject_id", name="uq_result_student_exam_subject"),
        CheckConstraint("component_max_marks > 0", name="ck_result_component_max"),
        CheckConstraint("total_max >= 0", name="ck_result_total_max"),
        CheckConstraint("percentage IS NULL OR (percentage >= 0 AND percentage <= 100)", name="ck_result_percentage"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    report_data: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    generated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    student: Mapped["Student"] = relationship("Student")
    session: Mapped["AcademicSession"] = relationship("AcademicSession")
    class_: Mapped["Class"] = relationship("Class")
    section: Mapped["Section"] = relationship("Section")
    generator: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("student_id", "session_id", "report_type", name="uq_report_student_session_type"),
    )
