# Mark Register - Phase 1

Standalone desktop app for managing academic sessions.

## Stack

Python, PySide6, SQLite, SQLAlchemy, pytest

## Run

```
python main.py
```

## Tests

```
pytest
```

## Database

Stored at `data/mark_register.db` (absolute path under the project). A backup is
created under `data/` before any schema change. The database is never reset or
deleted automatically.

## Phase 1 features

- Professional desktop window with sidebar navigation
- Academic Sessions: add, list, edit, set current, archive, delete
- Fields: session name, start date, end date, status
- Unique session names; only one current session at a time
- Deletion blocked when academic records reference a session
- SQLAlchemy models, repository/service separation, transactions
