with open('services.py', 'r') as f:
    content = f.read()

old = '''marks_lookup = {}
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
                status = "pending"'''

new = '''marks_lookup = {}
        for m in marks_list:
            if m.component_id in [c.id for c in components]:
                marks_lookup[(m.student_id, m.component_id)] = m

        result = []
        for student in students:
            max_marks = sum(c.max_marks for c in components)
            obtained_total = 0
            has_all_marks = True
            any_absent = False

            for comp in components:
                marks = marks_lookup.get((student.id, comp.id))
                if marks:
                    if marks.status == "absent":
                        any_absent = True
                        has_all_marks = False
                    elif marks.marks_obtained is not None:
                        obtained_total += marks.marks_obtained
                    else:
                        has_all_marks = False
                else:
                    has_all_marks = False

            if any_absent:
                obtained = None
                percentage = None
                grade = None
                status = "absent"
            elif not has_all_marks:
                obtained = None
                percentage = None
                grade = None
                status = "pending"'''

count = content.count(old)
print(f'Found {count} matches')
if count == 1:
    content = content.replace(old, new)
    with open('services.py', 'w') as f:
        f.write(content)
    print('Replacement successful')
else:
    print('Not replacing - need unique match')