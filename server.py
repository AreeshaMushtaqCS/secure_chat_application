import asyncio
import json
import logging
import socket
import threading
from logging.handlers import RotatingFileHandler
from db import Database
from datetime import datetime

rooms = {}  # room_id -> set of (writer, username)


LOG_FILE = 'securechat-server.log'
DISCOVERY_PORT = 9999
DISCOVERY_MAGIC = b'SECURECHAT_DISCOVER'


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
        self._discovery_thread = None
        self._discovery_stop = threading.Event()

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
    # bind to all interfaces so LAN clients can connect
    s = await asyncio.start_server(server.handle, '0.0.0.0', 8888)
    addr = s.sockets[0].getsockname()
    print(f'Server listening on {addr}')
    server.logger.info('Server listening on %s', addr)
    # start UDP discovery responder in a background thread
    def _discovery_responder(tcp_port, stop_event):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', DISCOVERY_PORT))
        except Exception:
            server.logger.exception('Failed to bind discovery socket')
            return
        server.logger.info('Discovery responder listening on UDP %s', DISCOVERY_PORT)
        while not stop_event.is_set():
            try:
                sock.settimeout(1.0)
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except Exception:
                break
            if not data:
                continue
            if data.strip() != DISCOVERY_MAGIC:
                continue
            # determine a sensible local IP to reply with (best-effort)
            client_ip = addr[0]
            local_ip = None
            try:
                s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s2.connect((client_ip, 80))
                local_ip = s2.getsockname()[0]
                s2.close()
            except Exception:
                try:
                    local_ip = socket.gethostbyname(socket.gethostname())
                except Exception:
                    local_ip = '127.0.0.1'
            reply = json.dumps({'host': local_ip, 'port': tcp_port}).encode()
            try:
                sock.sendto(reply, addr)
            except Exception:
                server.logger.exception('Failed to send discovery reply to %s', addr)
        try:
            sock.close()
        except Exception:
            pass

    server._discovery_thread = threading.Thread(target=_discovery_responder, args=(addr[1], server._discovery_stop), daemon=True)
    server._discovery_thread.start()
    async with s:
        try:
            await s.serve_forever()
        finally:
            # stop discovery
            server._discovery_stop.set()
            try:
                server._discovery_thread.join(timeout=2.0)
            except Exception:
                pass
            server.db.close()
            server.logger.info('Server stopped')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Server stopped')
