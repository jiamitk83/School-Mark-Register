"""Filter the grid based on student search text and status filter."""
        search_text = self.student_search.text().lower().strip()
        status_filter = self.status_filter.currentText()

        for row in range(self.marks_table.rowCount()):
            show_row = True

            # Student search filter
            if search_text:
                student_name_item = self.marks_table.item(row, 1)
                roll_no_item = self.marks_table.item(row, 0)
                student_name = student_name_item.text().lower() if student_name_item else ""
                roll_no = roll_no_item.text().lower() if roll_no_item else ""
                if search_text not in student_name and search_text not in roll_no:
                    show_row = False

            # Status filter
            if show_row and status_filter != "All":
                subject_item = self.marks_table.item(row, 1)
                if subject_item:
                    key = subject_item.data(Qt.ItemDataRole.UserRole)
                    if key:
                        status = self._component_marks_data.get(key, {}).get("status", "pending")
                        if status_filter != status.capitalize():
                            show_row = False

            self.marks_table.setRowHidden(row, not show_row)

    def refresh(self) -> None:
        self._clear_error()
        if self._selected_session_id and self._selected_class_id and self._selected_section_id and self._selected_exam_type_id and self._selected_subject_id:
            self._load_component_grid()