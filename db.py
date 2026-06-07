import sqlite3
import threading
from typing import List, Optional, Tuple


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
            cur.execute("PRAGMA table_info(rooms)")
            cols = {row[1] for row in cur.fetchall()}
            if 'admin' not in cols:
                cur.execute('ALTER TABLE rooms ADD COLUMN admin TEXT')
            if 'require_approval' not in cols:
                cur.execute('ALTER TABLE rooms ADD COLUMN require_approval INTEGER DEFAULT 1')
            self.conn.commit()

    def room_exists(self, room_id: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('SELECT 1 FROM rooms WHERE room_id = ?', (room_id,))
            return cur.fetchone() is not None

    def create_room(self, room_id: str, name: str, admin: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                'INSERT INTO rooms(room_id, name, admin, require_approval) VALUES(?, ?, ?, 1)',
                (room_id, name, admin),
            )
            self.conn.commit()

    def get_room(self, room_id: str) -> Optional[Tuple[str, str, str, int]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                'SELECT room_id, name, admin, require_approval FROM rooms WHERE room_id = ?',
                (room_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return row[0], row[1], row[2], int(row[3] or 0)

    def set_require_approval(self, room_id: str, require_approval: bool):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                'UPDATE rooms SET require_approval = ? WHERE room_id = ?',
                (1 if require_approval else 0, room_id),
            )
            self.conn.commit()

    def set_admin(self, room_id: str, admin: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute('UPDATE rooms SET admin = ? WHERE room_id = ?', (admin, room_id))
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
