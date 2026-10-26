import sqlite3
conn = sqlite3.connect(r'data\mark_register_backup_pre_audit_20261025_162550.db')
cursor = conn.execute('SELECT COUNT(*) FROM component_marks')
print(f'Backup component_marks records: {cursor.fetchone()[0]}')
cursor = conn.execute('SELECT * FROM component_marks LIMIT 5')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')
conn.close()
