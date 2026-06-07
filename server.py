import asyncio
import json
import sqlite3
import os
import uuid


# Start every server run with a fresh DB so room state matches the live socket map.
if os.path.exists('chat.db'):
    os.remove('chat.db')
    print("Removed old database to start fresh")


class Server:
    def __init__(self):
        self.conn = sqlite3.connect('chat.db', check_same_thread=False)
        self.init_db()
        self.rooms = {}          # room_id -> list of writers
        self.clients = {}        # writer -> {'room_id': str, 'name': str}
        self.room_messages = {}  # room_id -> {msg_id: sender_name}, for ownership checks

    def init_db(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                room_name TEXT,
                password_hash TEXT,
                admin TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS room_members (
                room_id TEXT,
                username TEXT,
                PRIMARY KEY (room_id, username)
            )
        ''')
        self.conn.commit()
        print("Database initialized")

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"Client connected: {addr}")

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    msg = json.loads(data.decode())
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                    continue

                cmd = msg.get('cmd')
                print(f"Received: {cmd} from {addr}")

                try:
                    if cmd == 'create_room':
                        await self.create_room(writer, msg)
                    elif cmd == 'join_room':
                        await self.join_room(writer, msg)
                    elif cmd == 'send_message':
                        await self.send_message(writer, msg)
                    elif cmd == 'leave_room':
                        await self.leave_room(writer, msg)
                    elif cmd == 'kick_user':
                        await self.kick_user(writer, msg)
                    elif cmd == 'delete_message':
                        await self.delete_message(writer, msg)
                    elif cmd == 'edit_message':
                        await self.edit_message(writer, msg)
                    elif cmd == 'transfer_admin':
                        await self.transfer_admin(writer, msg)
                    elif cmd == 'list_members':
                        room_id = msg.get('room_id')
                        if room_id:
                            await self.broadcast_member_list(room_id)
                    else:
                        await self.send(writer, {'status': 'error', 'reason': f'Unknown command: {cmd}'})
                except Exception as e:
                    print(f"Command error ({cmd}): {e}")
                    await self.send(writer, {'status': 'error', 'reason': str(e)})

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            await self.cleanup_writer(writer)
            print(f"Client disconnected: {addr}")

    async def cleanup_writer(self, writer):
        info = self.clients.pop(writer, None)
        if info:
            room_id = info.get('room_id')
            username = info.get('name')
            if room_id in self.rooms and writer in self.rooms[room_id]:
                self.rooms[room_id].remove(writer)
            if room_id and username:
                await self.broadcast(room_id, {'cmd': 'member_left', 'username': username})
                await self.broadcast_member_list(room_id)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    async def create_room(self, writer, msg):
        room_id = msg.get('room_id')
        room_name = msg.get('room_name')
        password_hash = msg.get('password_hash')
        admin = msg.get('name')

        if not room_id or not password_hash or not admin:
            await self.send(writer, {'status': 'error', 'reason': 'Missing fields'})
            return

        cur = self.conn.cursor()
        cur.execute('SELECT room_id FROM rooms WHERE room_id = ?', (room_id,))
        if cur.fetchone():
            await self.send(writer, {'status': 'error', 'reason': 'Room already exists'})
            return

        cur.execute(
            'INSERT INTO rooms (room_id, room_name, password_hash, admin) VALUES (?, ?, ?, ?)',
            (room_id, room_name, password_hash, admin),
        )
        self.conn.commit()
        print(f"Room created: {room_id} (admin={admin})")
        await self.send(writer, {'status': 'ok', 'message': 'Room created'})

    async def join_room(self, writer, msg):
        room_id = msg.get('room_id')
        username = msg.get('name')
        password_hash = msg.get('password_hash')

        cur = self.conn.cursor()
        cur.execute('SELECT room_name, admin, password_hash FROM rooms WHERE room_id = ?', (room_id,))
        row = cur.fetchone()

        if not row:
            await self.send(writer, {'status': 'error', 'reason': 'no_room'})
            return

        room_name, admin, stored_hash = row
        if stored_hash != password_hash:
            await self.send(writer, {'status': 'error', 'reason': 'wrong_password'})
            return

        # Disallow duplicate names in the same live room.
        active_names = {
            self.clients[w]['name']
            for w in self.rooms.get(room_id, [])
            if w in self.clients
        }
        if username in active_names:
            await self.send(writer, {'status': 'error', 'reason': 'name_taken'})
            return

        cur.execute(
            'INSERT OR IGNORE INTO room_members (room_id, username) VALUES (?, ?)',
            (room_id, username),
        )
        self.conn.commit()

        self.clients[writer] = {'room_id': room_id, 'name': username}
        self.rooms.setdefault(room_id, []).append(writer)

        print(f"{username} joined room {room_id}")

        await self.send(writer, {
            'status': 'ok',
            'action': 'joined',
            'room_info': {'room_name': room_name, 'admin': admin},
        })
        await self.broadcast(
            room_id,
            {'cmd': 'member_joined', 'username': username},
            exclude=writer,
        )
        await self.broadcast_member_list(room_id)

    async def send_message(self, writer, msg):
        room_id = msg.get('room_id')
        sender = msg.get('sender')
        ciphertext = msg.get('ciphertext')
        client_msg_id = msg.get('client_msg_id')

        if not room_id or not sender:
            return

        msg_id = uuid.uuid4().hex[:12]
        self.room_messages.setdefault(room_id, {})[msg_id] = sender

        # Confirm back to the sender so it can tag its own bubble with the same id.
        await self.send(writer, {
            'cmd': 'message_ack',
            'msg_id': msg_id,
            'client_msg_id': client_msg_id,
        })

        await self.broadcast(
            room_id,
            {
                'cmd': 'message',
                'msg_id': msg_id,
                'sender': sender,
                'ciphertext': ciphertext,
                'ts': asyncio.get_event_loop().time(),
            },
            exclude=writer,
        )

    async def kick_user(self, writer, msg):
        room_id = msg.get('room_id')
        target = msg.get('target')

        if not self._is_admin(writer, room_id):
            await self.send(writer, {'status': 'error', 'reason': 'not_admin'})
            return

        target_writer = self._find_writer(room_id, target)
        if target_writer is None:
            await self.send(writer, {'status': 'error', 'reason': 'user_not_found'})
            return

        await self.send(target_writer, {
            'cmd': 'kicked',
            'reason': 'You have been removed from the room by the admin.',
        })

        if target_writer in self.rooms.get(room_id, []):
            self.rooms[room_id].remove(target_writer)
        self.clients.pop(target_writer, None)

        try:
            target_writer.close()
        except Exception:
            pass

        await self.broadcast(
            room_id,
            {'cmd': 'member_left', 'username': target, 'kicked': True},
        )
        await self.broadcast_member_list(room_id)
        print(f"{target} kicked from {room_id}")

    async def delete_message(self, writer, msg):
        room_id = msg.get('room_id')
        msg_id = msg.get('msg_id')

        if not self._can_modify_message(writer, room_id, msg_id):
            await self.send(writer, {'status': 'error', 'reason': 'not_allowed'})
            return

        # Drop the ownership record so the slot can't be reused for further edits.
        self.room_messages.get(room_id, {}).pop(msg_id, None)
        await self.broadcast(
            room_id,
            {'cmd': 'message_deleted', 'msg_id': msg_id},
        )

    async def edit_message(self, writer, msg):
        room_id = msg.get('room_id')
        msg_id = msg.get('msg_id')
        ciphertext = msg.get('ciphertext')

        if not self._can_modify_message(writer, room_id, msg_id):
            await self.send(writer, {'status': 'error', 'reason': 'not_allowed'})
            return

        await self.broadcast(
            room_id,
            {'cmd': 'message_edited', 'msg_id': msg_id, 'ciphertext': ciphertext},
        )

    def _can_modify_message(self, writer, room_id, msg_id):
        """Admins can act on any message; everyone else only on messages they sent."""
        if self._is_admin(writer, room_id):
            return True
        username = self.clients.get(writer, {}).get('name')
        if not username:
            return False
        sender = self.room_messages.get(room_id, {}).get(msg_id)
        return sender == username

    async def transfer_admin(self, writer, msg):
        room_id = msg.get('room_id')
        new_admin = msg.get('new_admin')

        if not self._is_admin(writer, room_id):
            await self.send(writer, {'status': 'error', 'reason': 'not_admin'})
            return

        active_names = {
            self.clients[w]['name']
            for w in self.rooms.get(room_id, [])
            if w in self.clients
        }
        if new_admin not in active_names:
            await self.send(writer, {'status': 'error', 'reason': 'user_not_in_room'})
            return

        cur = self.conn.cursor()
        cur.execute('UPDATE rooms SET admin = ? WHERE room_id = ?', (new_admin, room_id))
        self.conn.commit()

        await self.broadcast(
            room_id,
            {'cmd': 'admin_changed', 'new_admin': new_admin},
        )
        await self.broadcast_member_list(room_id)
        print(f"Admin of {room_id} transferred to {new_admin}")

    async def leave_room(self, writer, msg):
        await self.cleanup_writer(writer)

    def _is_admin(self, writer, room_id):
        cur = self.conn.cursor()
        cur.execute('SELECT admin FROM rooms WHERE room_id = ?', (room_id,))
        row = cur.fetchone()
        if not row:
            return False
        username = self.clients.get(writer, {}).get('name')
        return username is not None and username == row[0]

    def _find_writer(self, room_id, username):
        for w in self.rooms.get(room_id, []):
            if self.clients.get(w, {}).get('name') == username:
                return w
        return None

    async def broadcast_member_list(self, room_id):
        if room_id not in self.rooms:
            return
        cur = self.conn.cursor()
        cur.execute('SELECT admin FROM rooms WHERE room_id = ?', (room_id,))
        row = cur.fetchone()
        admin = row[0] if row else None
        members = [
            self.clients[w]['name']
            for w in self.rooms[room_id]
            if w in self.clients
        ]
        await self.broadcast(
            room_id,
            {'cmd': 'member_list', 'members': members, 'admin': admin},
        )

    async def broadcast(self, room_id, message, exclude=None):
        if room_id not in self.rooms:
            return
        data = (json.dumps(message) + '\n').encode()
        for w in self.rooms[room_id][:]:
            if w is exclude:
                continue
            try:
                w.write(data)
                await w.drain()
            except Exception as e:
                print(f"Broadcast error: {e}")

    async def send(self, writer, message):
        try:
            data = (json.dumps(message) + '\n').encode()
            writer.write(data)
            await writer.drain()
        except Exception as e:
            print(f"Send error: {e}")


async def main():
    server = Server()
    srv = await asyncio.start_server(server.handle_client, '0.0.0.0', 8888)

    print("\n" + "=" * 50)
    print("SecureChat Server Running")
    print("=" * 50)
    print("Listening on: 0.0.0.0:8888")
    print("Database: chat.db")
    print("Press Ctrl+C to stop.")
    print("=" * 50 + "\n")

    async with srv:
        await srv.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
