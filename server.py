import asyncio
import json
import sqlite3
import os

# Delete old database to start fresh
if os.path.exists('chat.db'):
    os.remove('chat.db')
    print("Removed old database to start fresh")

class Server:
    def __init__(self):
        self.conn = sqlite3.connect('chat.db', check_same_thread=False)
        self.init_db()
        self.rooms = {}  # room_id -> list of writers
        self.clients = {}  # writer -> {'room_id': room_id, 'name': name}
    
    def init_db(self):
        cursor = self.conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                room_name TEXT,
                password_hash TEXT,
                admin TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_members (
                room_id TEXT,
                username TEXT,
                PRIMARY KEY (room_id, username)
            )
        ''')
        
        self.conn.commit()
        print("✓ Database initialized successfully")
    
    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"\n📱 Client connected: {addr}")
        
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode())
                    cmd = msg.get('cmd')
                    print(f"📨 Received: {cmd} from {addr}")
                    
                    if cmd == 'create_room':
                        await self.create_room(writer, msg)
                    elif cmd == 'join_room':
                        await self.join_room(writer, msg)
                    elif cmd == 'send_message':
                        await self.send_message(writer, msg)
                    elif cmd == 'leave_room':
                        await self.leave_room(writer, msg)
                    else:
                        print(f"⚠️ Unknown command: {cmd}")
                        await self.send(writer, {'status': 'error', 'reason': f'Unknown command: {cmd}'})
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    
        except Exception as e:
            print(f"❌ Error handling client: {e}")
        finally:
            # Clean up
            if writer in self.clients:
                info = self.clients[writer]
                room_id = info.get('room_id')
                username = info.get('name')
                if room_id and username:
                    await self.broadcast(room_id, {'cmd': 'member_left', 'username': username}, writer)
                    if room_id in self.rooms and writer in self.rooms[room_id]:
                        self.rooms[room_id].remove(writer)
                del self.clients[writer]
            writer.close()
            await writer.wait_closed()
            print(f"📱 Client disconnected: {addr}")
    
    async def create_room(self, writer, msg):
        room_id = msg.get('room_id')
        room_name = msg.get('room_name')
        password_hash = msg.get('password_hash')
        admin = msg.get('name')
        
        print(f"🏠 Creating room: '{room_id}' by '{admin}'")
        
        cursor = self.conn.cursor()
        
        # Check if room exists
        cursor.execute('SELECT room_id FROM rooms WHERE room_id = ?', (room_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"❌ Room '{room_id}' already exists")
            await self.send(writer, {'status': 'error', 'reason': 'Room already exists'})
            return
        
        # Create room
        try:
            cursor.execute('INSERT INTO rooms (room_id, room_name, password_hash, admin) VALUES (?, ?, ?, ?)',
                          (room_id, room_name, password_hash, admin))
            self.conn.commit()
            print(f"✅ Room '{room_id}' created successfully")
            await self.send(writer, {'status': 'ok', 'message': 'Room created'})
        except Exception as e:
            print(f"❌ Database error: {e}")
            await self.send(writer, {'status': 'error', 'reason': str(e)})
    
    async def join_room(self, writer, msg):
        room_id = msg.get('room_id')
        username = msg.get('name')
        password_hash = msg.get('password_hash')
        
        print(f"🔑 User '{username}' trying to join room '{room_id}'")
        
        cursor = self.conn.cursor()
        
        # Check if room exists
        cursor.execute('SELECT room_name, admin, password_hash FROM rooms WHERE room_id = ?', (room_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Room '{room_id}' does not exist")
            await self.send(writer, {'status': 'error', 'reason': 'no_room'})
            return
        
        stored_hash = row[2]
        if stored_hash != password_hash:
            print(f"❌ Wrong password for room '{room_id}'")
            await self.send(writer, {'status': 'error', 'reason': 'wrong_password'})
            return
        
        # Add to members
        cursor.execute('INSERT OR IGNORE INTO room_members (room_id, username) VALUES (?, ?)', (room_id, username))
        self.conn.commit()
        
        # Store client info
        self.clients[writer] = {'room_id': room_id, 'name': username}
        
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(writer)
        
        print(f"✅ '{username}' joined room '{room_id}'")
        
        await self.send(writer, {
            'status': 'ok',
            'action': 'joined',
            'room_info': {'room_name': row[0], 'admin': row[1]}
        })
        
        # Notify others
        await self.broadcast(room_id, {'cmd': 'member_joined', 'username': username}, writer)
    
    async def send_message(self, writer, msg):
        room_id = msg.get('room_id')
        sender = msg.get('sender')
        ciphertext = msg.get('ciphertext')
        
        print(f"💬 Broadcasting message from '{sender}' in room '{room_id}'")
        
        await self.broadcast(room_id, {
            'cmd': 'message',
            'sender': sender,
            'ciphertext': ciphertext,
            'ts': asyncio.get_event_loop().time()
        }, writer)
    
    async def leave_room(self, writer, msg):
        if writer in self.clients:
            info = self.clients[writer]
            room_id = info.get('room_id')
            username = info.get('name')
            if room_id and username:
                print(f"👋 '{username}' left room '{room_id}'")
                await self.broadcast(room_id, {'cmd': 'member_left', 'username': username}, writer)
    
    async def broadcast(self, room_id, message, exclude=None):
        if room_id in self.rooms:
            data = (json.dumps(message) + '\n').encode()
            for writer in self.rooms[room_id][:]:
                if writer != exclude:
                    try:
                        writer.write(data)
                        await writer.drain()
                    except Exception as e:
                        print(f"❌ Broadcast error: {e}")
    
    async def send(self, writer, message):
        try:
            data = (json.dumps(message) + '\n').encode()
            writer.write(data)
            await writer.drain()
        except Exception as e:
            print(f"❌ Send error: {e}")

async def main():
    server = Server()
    srv = await asyncio.start_server(server.handle_client, '0.0.0.0', 8888)
    
    print("\n" + "="*50)
    print("🔐 SecureChat Server Running")
    print("="*50)
    print(f"📡 Listening on: 0.0.0.0:8888")
    print(f"💾 Database: chat.db")
    print("\n✨ Ready for connections!")
    print("\n⚠️  Press Ctrl+C to stop the server")
    print("="*50 + "\n")
    
    async with srv:
        await srv.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")