import sqlite3
from datetime import datetime

DB_NAME = "base.sqlite"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        topic TEXT NOT NULL,
        datetime TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def add_application(name: str, phone: str, topic: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
    INSERT INTO applications (name, phone, topic, datetime)
    VALUES (?, ?, ?, ?)
    """, (name, phone, topic, current_time))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"Database '{DB_NAME}' initialized and 'applications' table created if it didn't exist.") 