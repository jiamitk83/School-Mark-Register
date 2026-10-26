"""Migration to add missing subjects, PT2 exam type, and all approved component configurations."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/mark_register.db')
cursor = conn.cursor()

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ============================================================
# 1. ADD MISSING SUBJECTS
# ============================================================
print("=== Adding missing subjects ===")

subjects_to_add = [
    ("HINDI", "HIN", True),
    ("SCIENCE", "SCI", True),
    ("SOCIAL SCIENCE", "SS", True),
    ("COMPUTER", "COMP", True),
    ("FRENCH", "FR", True),
    ("GK", "GK", True),
]

for name, code, is_active in subjects_to_add:
    cursor.execute("SELECT id FROM subjects WHERE name = ?", (name,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO subjects (name, code, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, code, 1 if is_active else 0, now, now)
        )
        print(f"  Added subject: {name} ({code})")
    else:
        print(f"  Subject already exists: {name}")

# ============================================================
# 2. ADD PT2 EXAM TYPE
# ============================================================
print("\n=== Adding PT2 exam type ===")
cursor.execute("SELECT id FROM exam_types WHERE name = 'PT2'")
if not cursor.fetchone():
    cursor.execute("""
        INSERT INTO exam_types (name, code, description, max_marks, weightage, is_active, display_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("PT2", "PT2", "Periodic Test 2", 25, 1.0, 1, 4, now, now))
    print("  Added PT2 exam type")
else:
    print("  PT2 already exists")

# ============================================================
# 3. ADD COMPONENT CONFIGURATIONS FOR ALL SUBJECTS
# ============================================================
print("\n=== Adding component configurations ===")

# Get subject IDs
subject_ids = {}
cursor.execute("SELECT id, name FROM subjects")
for row in cursor.fetchall():
    subject_ids[row[1]] = row[0]

# Get exam type IDs
exam_type_ids = {}
cursor.execute("SELECT id, name FROM exam_types")
for row in cursor.fetchall():
    exam_type_ids[row[1]] = row[0]

# Helper function to add component
def add_component(exam_type_name, subject_name, name, code, max_marks, display_order):
    exam_type_id = exam_type_ids[exam_type_name]
    subject_id = subject_ids.get(subject_name)
    if not subject_id:
        print(f"  WARNING: Subject {subject_name} not found")
        return
    
    # Check if component already exists
    cursor.execute("""
        SELECT id FROM exam_components 
        WHERE exam_type_id = ? AND subject_id = ? AND name = ?
    """, (exam_type_id, subject_id, name))
    
    if cursor.fetchone():
        return  # Already exists
    
    cursor.execute("""
        INSERT INTO exam_components (exam_type_id, subject_id, name, code, max_marks, display_order, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (exam_type_id, subject_id, name, code, max_marks, display_order, now, now))

# Core subjects (English, Maths, Hindi, Science, Social Science)
core_subjects = ["ENGLISH", "MATHS", "HINDI", "SCIENCE", "SOCIAL SCIENCE"]

# Half Yearly components for core subjects
hy_core_components = [
    ("Periodic Test 1", "PT1", 5, 1),
    ("Multiple Assessment", "MA", 5, 2),
    ("Subject Enrichment", "SE", 5, 3),
    ("Portfolio", "PF", 5, 4),
    ("Written Exam", "WE", 80, 5),
]

# Annual components for core subjects
ann_core_components = [
    ("Periodic Test 2", "PT2", 5, 1),
    ("Multiple Assessment", "MA", 5, 2),
    ("Subject Enrichment", "SE", 5, 3),
    ("Portfolio", "PF", 5, 4),
    ("Written Exam", "WE", 80, 5),
]

# Computer subject components
hy_computer_components = [
    ("Periodic Test 1", "PT1", 5, 1),
    ("Practical", "PRAC", 30, 2),
    ("Theory", "THEORY", 50, 3),
    ("Multiple Assessment", "MA", 5, 4),
    ("Enrichment", "ENR", 5, 5),
    ("Portfolio", "PF", 5, 6),
]

ann_computer_components = [
    ("Periodic Test 2", "PT2", 5, 1),
    ("Practical", "PRAC", 30, 2),
    ("Theory", "THEORY", 50, 3),
    ("Multiple Assessment", "MA", 5, 4),
    ("Enrichment", "ENR", 5, 5),
    ("Portfolio", "PF", 5, 6),
]

# French subject components
hy_french_components = [
    ("Periodic Test 1", "PT1", 5, 1),
    ("Written Exam", "WE", 80, 2),  # 40 converted to 80
    ("Multiple Assessment", "MA", 5, 3),
    ("Enrichment", "ENR", 5, 4),
    ("Portfolio", "PF", 5, 5),
]

ann_french_components = [
    ("Periodic Test 2", "PT2", 5, 1),
    ("Written Exam", "WE", 80, 2),  # 40 converted to 80
    ("Multiple Assessment", "MA", 5, 3),
    ("Enrichment", "ENR", 5, 4),
    ("Portfolio", "PF", 5, 5),
]

# GK components
hy_gk_components = [
    ("PT Paper", "PT", 25, 1),
    ("Term Paper", "TP", 40, 2),
]

ann_gk_components = [
    ("PT Paper", "PT", 25, 1),
    ("Term Paper", "TP", 40, 2),
]

# Add components for all core subjects
for subject in core_subjects:
    for name, code, max_marks, order in hy_core_components:
        add_component("Half Yearly", subject, name, code, max_marks, order)
    for name, code, max_marks, order in ann_core_components:
        add_component("Annual", subject, name, code, max_marks, order)

# Add Computer components
for name, code, max_marks, order in hy_computer_components:
    add_component("Half Yearly", "COMPUTER", name, code, max_marks, order)
for name, code, max_marks, order in ann_computer_components:
    add_component("Annual", "COMPUTER", name, code, max_marks, order)

# Add French components
for name, code, max_marks, order in hy_french_components:
    add_component("Half Yearly", "FRENCH", name, code, max_marks, order)
for name, code, max_marks, order in ann_french_components:
    add_component("Annual", "FRENCH", name, code, max_marks, order)

# Add GK components
for name, code, max_marks, order in hy_gk_components:
    add_component("Half Yearly", "GK", name, code, max_marks, order)
for name, code, max_marks, order in ann_gk_components:
    add_component("Annual", "GK", name, code, max_marks, order)

conn.commit()
print("\n=== Migration completed successfully ===")

# Verify
cursor.execute("SELECT name FROM subjects ORDER BY id")
print("\nSubjects:")
for row in cursor.fetchall():
    print(f"  {row[0]}")

cursor.execute("SELECT name FROM exam_types ORDER BY display_order")
print("\nExam Types:")
for row in cursor.fetchall():
    print(f"  {row[0]}")

cursor.execute("""
    SELECT et.name, s.name, ec.name, ec.code, ec.max_marks, ec.display_order
    FROM exam_components ec
    JOIN exam_types et ON ec.exam_type_id = et.id
    JOIN subjects s ON ec.subject_id = s.id
    ORDER BY et.display_order, s.name, ec.display_order
""")
print("\nAll Components:")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}: {row[2]} ({row[3]}) = {row[4]} marks (order={row[5]})")

conn.close()