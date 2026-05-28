import sqlite3
import threading
from typing import List, Tuple


class Database:
    def __init__(self, path: str = 'chat.db'):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        self._init()

    def _init(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                name TEXT
            )
            ''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT,
                sender TEXT,
                ciphertext TEXT,
                ts TEXT
            )
            ''')
            self.conn.commit()

    def room_exists(self, room_id: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('SELECT 1 FROM rooms WHERE room_id = ?', (room_id,))
            return cur.fetchone() is not None

    def create_room(self, room_id: str, name: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('INSERT INTO rooms(room_id, name) VALUES(?, ?)', (room_id, name))
            self.conn.commit()

    def add_message(self, room_id: str, sender: str, ciphertext: str, ts: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('INSERT INTO messages(room_id, sender, ciphertext, ts) VALUES(?, ?, ?, ?)',
                        (room_id, sender, ciphertext, ts))
            self.conn.commit()

    def list_rooms(self) -> List[Tuple[str, str]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('SELECT room_id, name FROM rooms')
            return cur.fetchall()

    def close(self):
        with self.lock:
            try:
                self.conn.close()
            except Exception:
                pass
