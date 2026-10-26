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
        hy_exam_type = self.exam_type_repo.get_by_name("Half Yearly")
        if not hy_exam_type:
            return []

        students = self.student_repo.list_active_by_section(
            session_id, class_id, section_id
        )
        components = self.component_repo.get_by_exam_type_and_subject(
            hy_exam_type.id, subject_id
        )
        if not components:
            return []

        marks_list = self.repo.list_by_section_exam(
            session_id, class_id, section_id, hy_exam_type.id
        )
        marks_lookup = {(m.student_id, m.component_id): m for m in marks_list}

        result = []
        for student in students:
            max_marks = sum(c.max_marks for c in components)
            obtained_total = 0
            has_all_marks = True
            student_status = "pending"

            for comp in components:
                marks = marks_lookup.get((student.id, comp.id))
                if marks:
                    if marks.status == "absent":
                        student_status = "absent"
                        has_all_marks = False
                        break
                    if marks.marks_obtained is not None:
                        obtained_total += marks.marks_obtained
                    else:
                        has_all_marks = False
                else:
                    has_all_marks = False

            if student_status == "absent":
                obtained = None
                percentage = None
                grade = None
            elif not has_all_marks:
                obtained = None
                percentage = None
                grade = None
            else:
                obtained = obtained_total
                percentage = round((obtained / max_marks) * 100, 2) if max_marks > 0 else 0.0
                grade = self._calculate_grade(percentage)
                if student_status == "pending":
                    student_status = "saved"

            result.append({
                "student_id": student.id,
                "roll_number": student.roll_number,
                "admission_number": student.admission_number,
                "name": student.name,
                "max_marks": max_marks,
                "obtained_marks": obtained,
                "percentage": percentage,
                "grade": grade,
                "status": student_status,
            })

        return result

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

        results = self.get_half_yearly_result_summary(
            session_id, class_id, section_id, subject_id
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Roll Number", "Admission Number", "Student Name",
            "Max Marks", "Obtained Marks", "Percentage", "Grade", "Status"
        ])
        for r in results:
            writer.writerow([
                r["roll_number"],
                r["admission_number"],
                r["name"],
                r["max_marks"],
                r["obtained_marks"] if r["obtained_marks"] is not None else "",
                f"{r['percentage']:.2f}" if r["percentage"] is not None else "",
                r["grade"] if r["grade"] else "",
                r["status"],
            ])

        return output.getvalue()

    def get_half_yearly_subjects_for_class_section(
        self, class_id: int, section_id: int
    ) -> List[Subject]:
        """Get subjects that have Half Yearly components for a class+section."""
        hy_exam_type = self.exam_type_repo.get_by_name("Half Yearly")
        if not hy_exam_type:
            return []

        subjects = self.subject_repo.list_active()
        result = []
        for subj in subjects:
            comps = self.component_repo.get_by_exam_type_and_subject(
                hy_exam_type.id, subj.id
            )
            if comps:
                result.append(subj)
        return result

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
        hy_exam_type = self.exam_type_repo.get_by_name("Half Yearly")
        if not hy_exam_type:
            return []

        students = self.student_repo.list_active_by_section(
            session_id, class_id, section_id
        )
        components = self.component_repo.get_by_exam_type_and_subject(
            hy_exam_type.id, subject_id
        )
        if not components:
            return []

        marks_list = self.repo.list_by_section_exam(
            session_id, class_id, section_id, hy_exam_type.id
        )
        marks_lookup = {}
        for m in marks_list:
            if m.component_id in [c.id for c in components]:
                marks_lookup[(m.student_id, m.component_id)] = m

        result = []
        for student in students:
            max_marks = sum(c.max_marks for c in components)
            obtained_total = 0
            has_all_marks = True

            for comp in components:
                marks = marks_lookup.get((student.id, comp.id))
                if marks:
                    if marks.status == "absent":
                        has_all_marks = False
                    elif marks.marks_obtained is not None:
                        obtained_total += marks.marks_obtained
                    else:
                        has_all_marks = False
                else:
                    has_all_marks = False

            if not has_all_marks:
                obtained = None
                percentage = None
                grade = None
                status = "pending"
            else:
                obtained = obtained_total
                percentage = round((obtained / max_marks) * 100, 2) if max_marks > 0 else 0.0
                grade = self._calculate_grade(percentage)
                status = "saved"

            result.append({
                "student_id": student.id,
                "roll_number": student.roll_number,
                "admission_number": student.admission_number,
                "name": student.name,
                "max_marks": max_marks,
                "obtained_marks": obtained,
                "percentage": percentage,
                "grade": grade,
                "status": status,
            })

        return result

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

        results = self.get_half_yearly_result_summary(
            session_id, class_id, section_id, subject_id
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Roll Number", "Admission Number", "Student Name",
            "Max Marks", "Obtained Marks", "Percentage", "Grade", "Status"
        ])
        for r in results:
            writer.writerow([
                r["roll_number"],
                r["admission_number"],
                r["name"],
                r["max_marks"],
                r["obtained_marks"] if r["obtained_marks"] is not None else "",
                f"{r['percentage']:.2f}" if r["percentage"] is not None else "",
                r["grade"] if r["grade"] else "",
                r["status"],
            ])

        return output.getvalue()

    def get_half_yearly_subjects_for_class_section(
        self, class_id: int, section_id: int
    ) -> List:
        """Get subjects that have Half Yearly components for a class+section."""
        hy_exam_type = self.exam_type_repo.get_by_name("Half Yearly")
        if not hy_exam_type:
            return []

        subjects = self.subject_repo.list_active()
        result = []
        for subj in subjects:
            comps = self.component_repo.get_by_exam_type_and_subject(
                hy_exam_type.id, subj.id
            )
            if comps:
                result.append(subj)
        return result
