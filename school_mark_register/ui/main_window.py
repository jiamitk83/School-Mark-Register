from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from ui.half_yearly_result_view import HalfYearlyResultView
from ui.class_view import ClassView
from ui.exam_view import ExamView
from ui.marks_view import MarksView
from ui.pt1_report_card import Pt1ReportCard
from ui.pt1_result_view import Pt1ResultView
from ui.half_yearly_report_card import HalfYearlyReportCard  # NEW
from ui.section_view import SectionView
from ui.session_view import SessionView
from ui.student_view import StudentView
from ui.subject_view import SubjectView

from ui.styles import apply_global_style


class MainWindow(QMainWindow):
    def __init__(self, session_factory):
        super().__init__()
        self.setWindowTitle("Mark Register")
        self.resize(1200, 800)

        # Apply global styles
        apply_global_style(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.nav = QListWidget()
        self.nav.setFixedWidth(260)
        self.nav.addItem("Academic Sessions")
        self.nav.addItem("Class Master")
        self.nav.addItem("Section Master")
        self.nav.addItem("Subject Master")
        self.nav.addItem("Exam Configuration")
        self.nav.addItem("Marks Entry")
        self.nav.addItem("PT1 Report Card")
        self.nav.addItem("PT1 Results")
        self.nav.addItem("Half Yearly Results")
        self.nav.addItem("Half Yearly Report Card")  # NEW
        self.nav.addItem("Student Master")
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        # Stacked views
        self.stack = QStackedWidget()
        self.session_view = SessionView(session_factory)
        self.class_view = ClassView(session_factory)
        self.section_view = SectionView(session_factory)
        self.subject_view = SubjectView(session_factory)
        self.exam_view = ExamView(session_factory)
        self.marks_view = MarksView(session_factory)
        self.pt1_report_card = Pt1ReportCard(session_factory)
        self.pt1_result_view = Pt1ResultView(session_factory)
        self.half_yearly_result_view = HalfYearlyResultView(session_factory)
        self.student_view = StudentView(session_factory)
        self.half_yearly_report_card = HalfYearlyReportCard(session_factory)  # NEW
        self.stack.addWidget(self.session_view)
        self.stack.addWidget(self.class_view)
        self.stack.addWidget(self.section_view)
        self.stack.addWidget(self.subject_view)
        self.stack.addWidget(self.exam_view)
        self.stack.addWidget(self.marks_view)
        self.stack.addWidget(self.pt1_report_card)
        self.stack.addWidget(self.pt1_result_view)
        self.stack.addWidget(self.half_yearly_result_view)
        self.stack.addWidget(self.half_yearly_report_card)  # NEW
        self.stack.addWidget(self.student_view)

        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)

    def _on_nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
