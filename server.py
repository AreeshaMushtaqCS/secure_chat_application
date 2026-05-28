import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
from db import Database
from datetime import datetime

rooms = {}  # room_id -> set of (writer, username)


LOG_FILE = 'securechat-server.log'


def setup_logging():
    logger = logging.getLogger('securechat.server')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    return logger


class Server:
    def __init__(self, db_path="chat.db"):
        self.db = Database(db_path)
        self.logger = setup_logging()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        username = None
        room_id = None
        peer = writer.get_extra_info('peername')
        self.logger.info('Client connected peer=%s', peer)
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode())
                except Exception:
                    continue

                cmd = msg.get('cmd')
                if cmd == 'create_room':
                    name = msg.get('name')
                    room_id = msg.get('room_id')
                    if self.db.room_exists(room_id):
                        await self.send(writer, {'status': 'error', 'reason': 'room_exists'})
                    else:
                        self.db.create_room(room_id, name)
                        self.logger.info('Room created room_id=%s name=%s peer=%s', room_id, name, peer)
                        await self.send(writer, {'status': 'ok', 'action': 'created'})
                elif cmd == 'join_room':
                    room_id = msg.get('room_id')
                    username = msg.get('name')
                    if not self.db.room_exists(room_id):
                        await self.send(writer, {'status': 'error', 'reason': 'no_room'})
                    else:
                        rooms.setdefault(room_id, set()).add((writer, username))
                        self.logger.info('Room joined room_id=%s username=%s peer=%s', room_id, username, peer)
                        await self.send(writer, {'status': 'ok', 'action': 'joined'})
                elif cmd == 'send_message':
                    room_id = msg.get('room_id')
                    sender = msg.get('sender')
                    ciphertext = msg.get('ciphertext')
                    ts = datetime.utcnow().isoformat() + 'Z'
                    try:
                        self.db.add_message(room_id, sender, ciphertext, ts)
                        self.logger.info('Message stored room_id=%s sender=%s peer=%s', room_id, sender, peer)
                        await self.broadcast(room_id, {
                            'cmd': 'message',
                            'room_id': room_id,
                            'sender': sender,
                            'ciphertext': ciphertext,
                            'ts': ts,
                        })
                    except Exception:
                        self.logger.exception('Failed handling send_message room_id=%s sender=%s peer=%s', room_id, sender, peer)
                        await self.send(writer, {'status': 'error', 'reason': 'server_error'})
                elif cmd == 'list_rooms':
                    rows = self.db.list_rooms()
                    await self.send(writer, {'status': 'ok', 'rooms': rows})
                else:
                    self.logger.warning('Unknown command cmd=%s peer=%s', cmd, peer)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            self.logger.info('Client disconnected peer=%s', peer)
        except Exception:
            self.logger.exception('Unhandled server error peer=%s', peer)
        finally:
            # cleanup writer from any rooms
            for r_id, members in list(rooms.items()):
                to_remove = {m for m in members if m[0] is writer}
                if to_remove:
                    members.difference_update(to_remove)
                    if not members:
                        rooms.pop(r_id, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            self.logger.info('Connection closed peer=%s', peer)

    async def send(self, writer, obj):
        data = (json.dumps(obj) + "\n").encode()
        try:
            writer.write(data)
            await writer.drain()
        except Exception:
            pass

    async def broadcast(self, room_id, obj):
        members = rooms.get(room_id, set())
        data = (json.dumps(obj) + "\n").encode()
        for w, _ in list(members):
            try:
                w.write(data)
                await w.drain()
            except Exception:
                members.discard((w, _))


async def main():
    server = Server()
    s = await asyncio.start_server(server.handle, '127.0.0.1', 8888)
    addr = s.sockets[0].getsockname()
    print(f'Server listening on {addr}')
    server.logger.info('Server listening on %s', addr)
    async with s:
        try:
            await s.serve_forever()
        finally:
            server.db.close()
            server.logger.info('Server stopped')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Server stopped')
