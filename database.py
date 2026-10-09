import sqlite3

DB_NAME = "users.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT,
        total_points INTEGER DEFAULT 0,
        current_points INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    user = cur.fetchone()

    conn.close()

    return user


def create_user(user_id, name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO users
    (user_id, name, total_points, current_points, used_count)
    VALUES (?, ?, 0, 0, 0)
    """, (user_id, name))

    conn.commit()
    conn.close()


def update_name(user_id, name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    UPDATE users
    SET name=?
    WHERE user_id=?
    """, (name, user_id))

    conn.commit()
    conn.close()


def update_points(
    user_id,
    total_points,
    current_points,
    used_count
):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    UPDATE users
    SET
        total_points=?,
        current_points=?,
        used_count=?
    WHERE user_id=?
    """, (
        total_points,
        current_points,
        used_count,
        user_id
    ))

    conn.commit()
    conn.close()


def get_ranking():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT
        name,
        total_points
    FROM users
    ORDER BY total_points DESC
    LIMIT 10
    """)

    ranking = cur.fetchall()

    conn.close()

    return ranking
