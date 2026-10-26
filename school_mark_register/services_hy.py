"""Simple Half Yearly Result service methods implementation."""
from __future__ import annotations

from typing import List, Optional

from models import Subject


class SimpleComponentMarksService:
    """Simplified ComponentMarksService for Half Yearly Result methods."""
    
    def __init__(self, session):
        self.session = session
    
    def get_half_yearly_result_summary(
        self,
        session_id: int,
        class_id: int,
        section_id: int,
        subject_id: int,
    ) -> List[dict]:
        """Get Half Yearly result summary for all active students in a section for a subject.

        Returns one dict per student with:
        - roll_number, admission_number, name
        - max_marks, obtained_marks, percentage (2 decimals), grade, status
        - Pending marks stay blank (None); Absent is preserved as a status.
        """
        # For now, return empty list - this would need proper implementation
        # that follows the PT1 pattern but for Half Yearly exam type
        return []

    def export_half_yearly_results_to_csv(
        self,
        session_id: int,
        class_id: int,
        section_id: int,
        subject_id: int,
    ) -> str:
        """Export Half Yearly result summary to CSV format."""
        import csv
        from io import StringIO
        
        # For now, return empty CSV - this would need proper implementation
        results = self.get_half_yearly_result_summary(
            session_id, class_id, section_id, subject_id
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Roll Number", "Admission Number", "Student Name",
            "Max Marks", "Obtained Marks", "Percentage", "Grade", "Status"
        ])
        
        return output.getvalue()

    def get_half_yearly_subjects_for_class_section(
        self, class_id: int, section_id: int
    ) -> List[Subject]:
        """Get subjects that have Half Yearly components for a class+section."""
        # For now, return empty list - this would need proper implementation
        # that follows the PT1 pattern but for Half Yearly exam type
        return []
