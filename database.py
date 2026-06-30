"""
database.py — Тамоми амалиёти пойгоҳи додаҳо (SQLite)

Ҳар корбар як сатр дорад, ки дар он мо нигоҳ медорем:
- статуси тасдиқ (pending / approved / rejected)
- забони интихобшуда
- дарси ҷорӣ ва модули ҷорӣ
- интизории тасдиқи админ пас аз тест
"""

import sqlite3
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Сохтани ҷадвалҳо агар вуҷуд надошта бошанд."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'pending',     -- pending, approved, rejected
            language TEXT,
            current_module INTEGER DEFAULT 1,
            lessons_done_in_module INTEGER DEFAULT 0,
            total_lessons_done INTEGER DEFAULT 0,
            last_score INTEGER DEFAULT 0,
            last_total INTEGER DEFAULT 0,
            waiting_admin_review INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def add_user(user_id, username, full_name):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
        (user_id, username, full_name),
    )
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def set_status(user_id, status):
    conn = get_conn()
    conn.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()


def set_language(user_id, language):
    conn = get_conn()
    conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
    conn.commit()
    conn.close()


def increment_lesson(user_id):
    """Пас аз як дарс, шумора зам мешавад."""
    conn = get_conn()
    conn.execute(
        """UPDATE users SET
            lessons_done_in_module = lessons_done_in_module + 1,
            total_lessons_done = total_lessons_done + 1
           WHERE user_id = ?""",
        (user_id,),
    )
    conn.commit()
    conn.close()


def save_test_result(user_id, score, total):
    conn = get_conn()
    conn.execute(
        """UPDATE users SET
            last_score = ?, last_total = ?, waiting_admin_review = 1
           WHERE user_id = ?""",
        (score, total, user_id),
    )
    conn.commit()
    conn.close()


def advance_to_next_module(user_id):
    """Админ тасдиқ кард — рафтан ба модули нав."""
    conn = get_conn()
    conn.execute(
        """UPDATE users SET
            current_module = current_module + 1,
            lessons_done_in_module = 0,
            waiting_admin_review = 0
           WHERE user_id = ?""",
        (user_id,),
    )
    conn.commit()
    conn.close()


def repeat_current_module(user_id):
    """Админ гуфт 'не' — модулро такрор кунад."""
    conn = get_conn()
    conn.execute(
        """UPDATE users SET
            lessons_done_in_module = 0,
            waiting_admin_review = 0
           WHERE user_id = ?""",
        (user_id,),
    )
    conn.commit()
    conn.close()