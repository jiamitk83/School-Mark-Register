from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import AcademicSession, Class, Section, Student, Subject, SubjectClassMapping, SubjectSectionMapping, ExamType, Marks, MarksAuditLog, MarksDraft, User, UserClassSubjectMapping, ExamComponent, ComponentMarks


class SessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: AcademicSession) -> AcademicSession:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, session_id: int) -> Optional[AcademicSession]:
        return self.session.get(AcademicSession, session_id)

    def get_by_name(self, name: str) -> Optional[AcademicSession]:
        return self.session.query(AcademicSession).filter_by(name=name).first()

    def list_all(self) -> List[AcademicSession]:
        return self.session.query(AcademicSession).order_by(AcademicSession.name.asc()).all()

    def current(self) -> Optional[AcademicSession]:
        return self.session.query(AcademicSession).filter_by(is_current=True).first()

    def has_records(self, session_id: int) -> bool:
        from models import AcademicRecord

        return (
            self.session.query(AcademicRecord)
            .filter_by(session_id=session_id)
            .first()
            is not None
        )

    def delete(self, item: AcademicSession) -> None:
        self.session.delete(item)
        self.session.flush()


class ClassRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: Class) -> Class:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, class_id: int) -> Optional[Class]:
        return self.session.get(Class, class_id)

    def get_by_name(self, name: str) -> Optional[Class]:
        return self.session.query(Class).filter_by(name=name).first()

    def list_all(self) -> List[Class]:
        return self.session.query(Class).order_by(Class.display_order.asc(), Class.name.asc()).all()

    def list_active(self) -> List[Class]:
        return self.session.query(Class).filter_by(is_active=True).order_by(Class.display_order.asc(), Class.name.asc()).all()

    def get_max_display_order(self) -> int:
        from sqlalchemy import func
        result = self.session.query(func.max(Class.display_order)).scalar()
        return result or 0

    def exists_by_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(Class).filter_by(name=name)
        if exclude_id is not None:
            query = query.filter(Class.id != exclude_id)
        return query.first() is not None

    def delete(self, item: Class) -> None:
        self.session.delete(item)
        self.session.flush()


class SectionRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: Section) -> Section:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, section_id: int) -> Optional[Section]:
        return self.session.get(Section, section_id)

    def get_by_class_and_name(self, class_id: int, name: str, exclude_id: Optional[int] = None) -> Optional[Section]:
        """Case-insensitive lookup for section name within a class."""
        from sqlalchemy import func
        query = self.session.query(Section).filter(
            Section.class_id == class_id,
            func.lower(Section.name) == func.lower(name)
        )
        if exclude_id is not None:
            query = query.filter(Section.id != exclude_id)
        return query.first()

    def list_by_class(self, class_id: int) -> List[Section]:
        return self.session.query(Section).filter_by(class_id=class_id).order_by(Section.display_order.asc(), Section.name.asc()).all()

    def list_active_by_class(self, class_id: int) -> List[Section]:
        return self.session.query(Section).filter_by(class_id=class_id, is_active=True).order_by(Section.display_order.asc(), Section.name.asc()).all()

    def get_max_display_order(self, class_id: int) -> int:
        result = self.session.query(func.max(Section.display_order)).filter_by(class_id=class_id).scalar()
        return result or 0

    def has_records(self, section_id: int) -> bool:
        from models import AcademicRecord
        return (
            self.session.query(AcademicRecord)
            .filter_by(section_id=section_id)
            .first()
            is not None
        )

    def delete(self, item: Section) -> None:
        self.session.delete(item)
        self.session.flush()


class SubjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: Subject) -> Subject:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, subject_id: int) -> Optional[Subject]:
        return self.session.get(Subject, subject_id)

    def get_by_name(self, name: str) -> Optional[Subject]:
        return self.session.query(Subject).filter_by(name=name).first()

    def get_by_code(self, code: str) -> Optional[Subject]:
        return self.session.query(Subject).filter_by(code=code).first()

    def exists_by_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(Subject).filter_by(name=name)
        if exclude_id is not None:
            query = query.filter(Subject.id != exclude_id)
        return query.first() is not None

    def exists_by_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(Subject).filter_by(code=code)
        if exclude_id is not None:
            query = query.filter(Subject.id != exclude_id)
        return query.first() is not None

    def list_all(self) -> List[Subject]:
        return self.session.query(Subject).order_by(Subject.name.asc()).all()

    def list_active(self) -> List[Subject]:
        return self.session.query(Subject).filter_by(is_active=True).order_by(Subject.name.asc()).all()

    def delete(self, item: Subject) -> None:
        self.session.delete(item)
        self.session.flush()

    # SubjectClassMapping methods
    def add_class_mapping(self, item: SubjectClassMapping) -> SubjectClassMapping:
        self.session.add(item)
        self.session.flush()
        return item

    def get_class_mapping(self, mapping_id: int) -> Optional[SubjectClassMapping]:
        return self.session.get(SubjectClassMapping, mapping_id)

    def get_class_mapping_by_subject_class(self, subject_id: int, class_id: int) -> Optional[SubjectClassMapping]:
        return self.session.query(SubjectClassMapping).filter_by(
            subject_id=subject_id, class_id=class_id
        ).first()

    def list_class_mappings_by_subject(self, subject_id: int) -> List[SubjectClassMapping]:
        return self.session.query(SubjectClassMapping).filter_by(subject_id=subject_id).all()

    def list_active_class_mappings_by_subject(self, subject_id: int) -> List[SubjectClassMapping]:
        return self.session.query(SubjectClassMapping).filter_by(
            subject_id=subject_id, is_active=True
        ).all()

    def delete_class_mapping(self, item: SubjectClassMapping) -> None:
        self.session.delete(item)
        self.session.flush()

    # SubjectSectionMapping methods
    def add_section_mapping(self, item: SubjectSectionMapping) -> SubjectSectionMapping:
        self.session.add(item)
        self.session.flush()
        return item

    def get_section_mapping(self, mapping_id: int) -> Optional[SubjectSectionMapping]:
        return self.session.get(SubjectSectionMapping, mapping_id)

    def get_section_mapping_by_subject_section(self, subject_id: int, section_id: int) -> Optional[SubjectSectionMapping]:
        return self.session.query(SubjectSectionMapping).filter_by(
            subject_id=subject_id, section_id=section_id
        ).first()

    def list_section_mappings_by_subject(self, subject_id: int) -> List[SubjectSectionMapping]:
        return self.session.query(SubjectSectionMapping).filter_by(subject_id=subject_id).all()

    def list_active_section_mappings_by_subject(self, subject_id: int) -> List[SubjectSectionMapping]:
        return self.session.query(SubjectSectionMapping).filter_by(
            subject_id=subject_id, is_active=True
        ).all()

    def list_section_mappings_by_class(self, class_id: int) -> List[SubjectSectionMapping]:
        return (
            self.session.query(SubjectSectionMapping)
            .options(joinedload(SubjectSectionMapping.subject))
            .filter_by(class_id=class_id)
            .all()
        )

    def list_section_mappings_by_class_section(self, class_id: int, section_id: int) -> List[SubjectSectionMapping]:
        return (
            self.session.query(SubjectSectionMapping)
            .options(joinedload(SubjectSectionMapping.subject))
            .filter_by(class_id=class_id, section_id=section_id, is_active=True)
            .all()
        )

    def delete_section_mapping(self, item: SubjectSectionMapping) -> None:
        self.session.delete(item)
        self.session.flush()


class StudentRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: Student) -> Student:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, student_id: int) -> Optional[Student]:
        return self.session.get(Student, student_id)

    def get_by_admission_number(self, admission_number: str) -> Optional[Student]:
        return self.session.query(Student).filter_by(admission_number=admission_number).first()

    def get_by_roll_number(self, session_id: int, class_id: int, section_id: int, roll_number: str) -> Optional[Student]:
        return self.session.query(Student).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            roll_number=roll_number
        ).first()

    def list_by_section(self, session_id: int, class_id: int, section_id: int) -> List[Student]:
        return self.session.query(Student).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id
        ).order_by(Student.roll_number.asc(), Student.name.asc()).all()

    def list_active_by_section(self, session_id: int, class_id: int, section_id: int) -> List[Student]:
        return self.session.query(Student).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            is_active=True
        ).order_by(Student.roll_number.asc(), Student.name.asc()).all()

    def list_all(self) -> List[Student]:
        return self.session.query(Student).order_by(Student.admission_number.asc()).all()

    def list_active(self) -> List[Student]:
        return self.session.query(Student).filter_by(is_active=True).order_by(Student.admission_number.asc()).all()

    def search(self, query: str, session_id: int | None = None, class_id: int | None = None, section_id: int | None = None) -> List[Student]:
        q = self.session.query(Student)
        if session_id is not None:
            q = q.filter_by(session_id=session_id)
        if class_id is not None:
            q = q.filter_by(class_id=class_id)
        if section_id is not None:
            q = q.filter_by(section_id=section_id)
        search_term = f"%{query}%"
        return q.filter(
            (Student.name.ilike(search_term)) |
            (Student.roll_number.ilike(search_term)) |
            (Student.admission_number.ilike(search_term))
        ).order_by(Student.admission_number.asc()).all()

    def exists_by_admission_number(self, admission_number: str, exclude_id: Optional[int] = None) -> bool:
        q = self.session.query(Student).filter_by(admission_number=admission_number)
        if exclude_id is not None:
            q = q.filter(Student.id != exclude_id)
        return q.first() is not None

    def exists_by_roll_number(self, session_id: int, class_id: int, section_id: int, roll_number: str, exclude_id: Optional[int] = None) -> bool:
        q = self.session.query(Student).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            roll_number=roll_number
        )
        if exclude_id is not None:
            q = q.filter(Student.id != exclude_id)
        return q.first() is not None

    def get_next_admission_number(self) -> str:
        from sqlalchemy import func
        result = self.session.query(func.max(Student.id)).scalar()
        next_id = (result or 0) + 1
        return f"STU{next_id:06d}"

    def delete(self, item: Student) -> None:
        self.session.delete(item)
        self.session.flush()


class ExamTypeRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: ExamType) -> ExamType:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, exam_type_id: int) -> Optional[ExamType]:
        return self.session.get(ExamType, exam_type_id)

    def get_by_name(self, name: str) -> Optional[ExamType]:
        return self.session.query(ExamType).filter_by(name=name).first()

    def get_by_code(self, code: str) -> Optional[ExamType]:
        return self.session.query(ExamType).filter_by(code=code).first()

    def exists_by_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(ExamType).filter_by(name=name)
        if exclude_id is not None:
            query = query.filter(ExamType.id != exclude_id)
        return query.first() is not None

    def exists_by_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(ExamType).filter_by(code=code)
        if exclude_id is not None:
            query = query.filter(ExamType.id != exclude_id)
        return query.first() is not None

    def list_all(self) -> List[ExamType]:
        return self.session.query(ExamType).order_by(ExamType.display_order.asc(), ExamType.name.asc()).all()

    def list_active(self) -> List[ExamType]:
        return self.session.query(ExamType).filter_by(is_active=True).order_by(ExamType.display_order.asc(), ExamType.name.asc()).all()

    def get_max_display_order(self) -> int:
        result = self.session.query(func.max(ExamType.display_order)).scalar()
        return result or 0

    def delete(self, item: ExamType) -> None:
        self.session.delete(item)
        self.session.flush()


class MarksRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: Marks) -> Marks:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, marks_id: int) -> Optional[Marks]:
        return self.session.get(Marks, marks_id)

    def get_by_student_subject_exam(self, student_id: int, subject_id: int, exam_type_id: int) -> Optional[Marks]:
        return self.session.query(Marks).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            exam_type_id=exam_type_id
        ).first()

    def list_by_section_exam(self, session_id: int, class_id: int, section_id: int, exam_type_id: int) -> List[Marks]:
        return self.session.query(Marks).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            exam_type_id=exam_type_id
        ).order_by(Marks.student_id).all()

    def list_by_section_exam_subject(self, session_id: int, class_id: int, section_id: int, exam_type_id: int, subject_id: int) -> List[Marks]:
        return self.session.query(Marks).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            exam_type_id=exam_type_id,
            subject_id=subject_id
        ).order_by(Marks.student_id).all()

    def list_by_student(self, student_id: int) -> List[Marks]:
        return self.session.query(Marks).filter_by(student_id=student_id).all()

    def list_by_student_exam(self, student_id: int, exam_type_id: int) -> List[Marks]:
        return self.session.query(Marks).filter_by(
            student_id=student_id,
            exam_type_id=exam_type_id
        ).all()

    def exists_by_student_subject_exam(self, student_id: int, subject_id: int, exam_type_id: int, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(Marks).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            exam_type_id=exam_type_id
        )
        if exclude_id is not None:
            query = query.filter(Marks.id != exclude_id)
        return query.first() is not None

    def delete(self, item: Marks) -> None:
        self.session.delete(item)
        self.session.flush()

    def bulk_create_or_update(self, marks_list: List[Marks]) -> List[Marks]:
        """Create or update multiple marks entries."""
        created = []
        for marks in marks_list:
            existing = self.get_by_student_subject_exam(marks.student_id, marks.subject_id, marks.exam_type_id)
            if existing:
                existing.marks_obtained = marks.marks_obtained
                existing.max_marks = marks.max_marks
                existing.status = marks.status
                created.append(existing)
            else:
                self.add(marks)
                created.append(marks)
        self.session.flush()
        return created


class MarksAuditLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: MarksAuditLog) -> MarksAuditLog:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, audit_log_id: int) -> Optional[MarksAuditLog]:
        return self.session.get(MarksAuditLog, audit_log_id)

    def list_by_marks(self, marks_id: int) -> List[MarksAuditLog]:
        return self.session.query(MarksAuditLog).filter_by(marks_id=marks_id).order_by(MarksAuditLog.created_at.desc()).all()

    def list_by_student(self, student_id: int) -> List[MarksAuditLog]:
        return self.session.query(MarksAuditLog).filter_by(student_id=student_id).order_by(MarksAuditLog.created_at.desc()).all()

    def list_by_student_exam(self, student_id: int, exam_type_id: int) -> List[MarksAuditLog]:
        return self.session.query(MarksAuditLog).filter_by(student_id=student_id, exam_type_id=exam_type_id).order_by(MarksAuditLog.created_at.desc()).all()

    def list_by_user(self, user_id: int) -> List[MarksAuditLog]:
        return self.session.query(MarksAuditLog).filter_by(user_id=user_id).order_by(MarksAuditLog.created_at.desc()).all()

    def list_all(self) -> List[MarksAuditLog]:
        return self.session.query(MarksAuditLog).order_by(MarksAuditLog.created_at.desc()).all()

    def list_recent(self, limit: int = 100) -> List[MarksAuditLog]:
        return self.session.query(MarksAuditLog).order_by(MarksAuditLog.created_at.desc()).limit(limit).all()

    # Prevent ordinary users from editing/deleting audit entries
    # Only admins should use these methods with explicit permission checks
    def delete(self, item: MarksAuditLog) -> None:
        """Delete audit log entry - restricted to admin only."""
        self.session.delete(item)
        self.session.flush()


class MarksDraftRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: MarksDraft) -> MarksDraft:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, draft_id: int) -> Optional[MarksDraft]:
        return self.session.get(MarksDraft, draft_id)

    def get_by_student_subject_exam(self, student_id: int, subject_id: int, exam_type_id: int) -> Optional[MarksDraft]:
        return self.session.query(MarksDraft).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            exam_type_id=exam_type_id
        ).first()

    def list_by_section_exam(self, session_id: int, class_id: int, section_id: int, exam_type_id: int) -> List[MarksDraft]:
        return self.session.query(MarksDraft).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            exam_type_id=exam_type_id
        ).all()

    def list_by_section_exam_subject(self, session_id: int, class_id: int, section_id: int, exam_type_id: int, subject_id: int) -> List[MarksDraft]:
        return self.session.query(MarksDraft).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            exam_type_id=exam_type_id,
            subject_id=subject_id
        ).all()

    def list_by_student(self, student_id: int) -> List[MarksDraft]:
        return self.session.query(MarksDraft).filter_by(student_id=student_id).all()

    def delete(self, item: MarksDraft) -> None:
        self.session.delete(item)
        self.session.flush()

    def delete_by_student_subject_exam(self, student_id: int, subject_id: int, exam_type_id: int) -> int:
        """Delete draft for a specific student-subject-exam combination. Returns count deleted."""
        count = self.session.query(MarksDraft).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            exam_type_id=exam_type_id
        ).delete()
        self.session.flush()
        return count

    def clear_all(self) -> int:
        """Clear all drafts. Returns count deleted."""
        count = self.session.query(MarksDraft).delete()
        self.session.flush()
        return count


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: User) -> User:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        return self.session.query(User).filter_by(username=username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter_by(email=email).first()

    def exists_by_username(self, username: str, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(User).filter_by(username=username)
        if exclude_id is not None:
            query = query.filter(User.id != exclude_id)
        return query.first() is not None

    def list_all(self) -> List[User]:
        return self.session.query(User).order_by(User.username.asc()).all()

    def list_active(self) -> List[User]:
        return self.session.query(User).filter_by(is_active=True).order_by(User.username.asc()).all()

    def list_by_role(self, role: str) -> List[User]:
        return self.session.query(User).filter_by(role=role).order_by(User.username.asc()).all()

    def delete(self, item: User) -> None:
        self.session.delete(item)
        self.session.flush()


class UserClassSubjectMappingRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: UserClassSubjectMapping) -> UserClassSubjectMapping:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, mapping_id: int) -> Optional[UserClassSubjectMapping]:
        return self.session.get(UserClassSubjectMapping, mapping_id)

    def get_by_user_class_subject(self, user_id: int, class_id: int, subject_id: int, session_id: int, section_id: Optional[int] = None) -> Optional[UserClassSubjectMapping]:
        query = self.session.query(UserClassSubjectMapping).filter_by(
            user_id=user_id,
            class_id=class_id,
            subject_id=subject_id,
            session_id=session_id,
        )
        if section_id is not None:
            query = query.filter_by(section_id=section_id)
        else:
            query = query.filter(UserClassSubjectMapping.section_id.is_(None))
        return query.first()

    def list_by_user(self, user_id: int) -> List[UserClassSubjectMapping]:
        return self.session.query(UserClassSubjectMapping).filter_by(user_id=user_id).all()

    def list_by_user_session(self, user_id: int, session_id: int) -> List[UserClassSubjectMapping]:
        return self.session.query(UserClassSubjectMapping).filter_by(
            user_id=user_id,
            session_id=session_id
        ).all()

    def list_by_class_subject(self, class_id: int, subject_id: int, session_id: int) -> List[UserClassSubjectMapping]:
        return self.session.query(UserClassSubjectMapping).filter_by(
            class_id=class_id,
            subject_id=subject_id,
            session_id=session_id
        ).all()

    def list_teachers_for_class(self, class_id: int, session_id: int) -> List[UserClassSubjectMapping]:
        return self.session.query(UserClassSubjectMapping).filter_by(
            class_id=class_id,
            session_id=session_id
        ).all()

    def exists_for_user(self, user_id: int, class_id: int, subject_id: int, session_id: int, section_id: Optional[int] = None) -> bool:
        query = self.session.query(UserClassSubjectMapping).filter_by(
            user_id=user_id,
            class_id=class_id,
            subject_id=subject_id,
            session_id=session_id,
        )
        if section_id is not None:
            query = query.filter_by(section_id=section_id)
        else:
            query = query.filter(UserClassSubjectMapping.section_id.is_(None))
        return query.first() is not None

    def delete(self, item: UserClassSubjectMapping) -> None:
        self.session.delete(item)
        self.session.flush()

    def delete_by_user(self, user_id: int) -> int:
        count = self.session.query(UserClassSubjectMapping).filter_by(user_id=user_id).delete()
        self.session.flush()
        return count


class ExamComponentRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: ExamComponent) -> ExamComponent:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, component_id: int) -> Optional[ExamComponent]:
        return self.session.get(ExamComponent, component_id)

    def get_by_exam_type(self, exam_type_id: int) -> List[ExamComponent]:
        return self.session.query(ExamComponent).filter_by(
            exam_type_id=exam_type_id, is_active=True
        ).order_by(ExamComponent.display_order.asc()).all()

    def get_by_exam_type_and_subject(self, exam_type_id: int, subject_id: int | None) -> List[ExamComponent]:
        query = self.session.query(ExamComponent).filter_by(
            exam_type_id=exam_type_id, is_active=True
        )
        if subject_id is not None:
            query = query.filter(
                (ExamComponent.subject_id == subject_id) | (ExamComponent.subject_id.is_(None))
            )
        else:
            query = query.filter(ExamComponent.subject_id.is_(None))
        return query.order_by(ExamComponent.display_order.asc()).all()

    def exists_by_name(self, exam_type_id: int, name: str, subject_id: int | None, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(ExamComponent).filter_by(
            exam_type_id=exam_type_id, name=name
        )
        if subject_id is not None:
            query = query.filter(
                (ExamComponent.subject_id == subject_id) | (ExamComponent.subject_id.is_(None))
            )
        else:
            query = query.filter(ExamComponent.subject_id.is_(None))
        if exclude_id is not None:
            query = query.filter(ExamComponent.id != exclude_id)
        return query.first() is not None

    def list_all(self) -> List[ExamComponent]:
        return self.session.query(ExamComponent).order_by(
            ExamComponent.exam_type_id, ExamComponent.display_order
        ).all()

    def delete(self, item: ExamComponent) -> None:
        self.session.delete(item)
        self.session.flush()


class ComponentMarksRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, item: ComponentMarks) -> ComponentMarks:
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, component_marks_id: int) -> Optional[ComponentMarks]:
        return self.session.get(ComponentMarks, component_marks_id)

    def get_by_student_component(self, student_id: int, component_id: int) -> Optional[ComponentMarks]:
        return self.session.query(ComponentMarks).filter_by(
            student_id=student_id,
            component_id=component_id
        ).first()

    def list_by_section_exam(self, session_id: int, class_id: int, section_id: int, exam_type_id: int) -> List[ComponentMarks]:
        return self.session.query(ComponentMarks).filter_by(
            session_id=session_id,
            class_id=class_id,
            section_id=section_id,
            exam_type_id=exam_type_id
        ).order_by(ComponentMarks.student_id, ComponentMarks.component_id).all()

    def list_by_student(self, student_id: int) -> List[ComponentMarks]:
        return self.session.query(ComponentMarks).filter_by(student_id=student_id).all()

    def list_by_student_exam(self, student_id: int, exam_type_id: int) -> List[ComponentMarks]:
        return self.session.query(ComponentMarks).filter_by(
            student_id=student_id,
            exam_type_id=exam_type_id
        ).all()

    def exists_by_student_component(self, student_id: int, component_id: int, exclude_id: Optional[int] = None) -> bool:
        query = self.session.query(ComponentMarks).filter_by(
            student_id=student_id,
            component_id=component_id
        )
        if exclude_id is not None:
            query = query.filter(ComponentMarks.id != exclude_id)
        return query.first() is not None

    def delete(self, item: ComponentMarks) -> None:
        self.session.delete(item)
        self.session.flush()

    def bulk_create_or_update(self, marks_list: List[ComponentMarks]) -> List[ComponentMarks]:
        created = []
        for marks in marks_list:
            existing = self.get_by_student_component(marks.student_id, marks.component_id)
            if existing:
                existing.marks_obtained = marks.marks_obtained
                existing.max_marks = marks.max_marks
                existing.status = marks.status
                created.append(existing)
            else:
                self.add(marks)
                created.append(marks)
        self.session.flush()
        return created