import json
import os
import queue
import socket
import threading
import logging
from logging.handlers import RotatingFileHandler

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False
    tk = None
    messagebox = None
    ttk = None

from crypto import decrypt, encrypt


HOST = os.environ.get('CHAT_HOST', '127.0.0.1')
PORT = int(os.environ.get('CHAT_PORT', '8888'))
ENABLE_GUI = os.environ.get('CHAT_GUI', '0').lower() in {'1', 'true', 'yes', 'on'}
LOG_FILE = os.environ.get('CHAT_LOG_FILE', 'securechat-client.log')


def setup_logging():
    logger = logging.getLogger('securechat.client')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    return logger


LOGGER = setup_logging()


def send_json(sock: socket.socket, obj):
    sock.sendall((json.dumps(obj) + '\n').encode())


def recv_json_line(file_obj):
    line = file_obj.readline()
    if not line:
        return None
    return json.loads(line.decode())


class NetworkClient:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.reader = None
        self.writer_lock = threading.Lock()
        self.connected = False

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.sock.settimeout(None)
        self.reader = self.sock.makefile('rb')
        self.connected = True
        LOGGER.info('Connected host=%s port=%s', self.host, self.port)

    def request(self, payload):
        with self.writer_lock:
            send_json(self.sock, payload)
            return recv_json_line(self.reader)

    def send(self, payload):
        with self.writer_lock:
            send_json(self.sock, payload)
            LOGGER.info('Sent payload cmd=%s', payload.get('cmd'))

    def close(self):
        self.connected = False
        try:
            if self.reader:
                self.reader.close()
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        LOGGER.info('Connection closed')


class PremiumChatUI:
    BG = '#0e1117'
    PANEL = '#151b24'
    PANEL_2 = '#1b2230'
    TEXT = '#e8edf7'
    MUTED = '#9aa7bd'
    ACCENT = '#6ea8fe'
    ACCENT_2 = '#4dd4ac'
    DANGER = '#ff6b6b'

    def __init__(self, root):
        self.root = root
        self.root.title('SecureChat')
        self.root.configure(bg=self.BG)
        self.root.geometry('1080x720')
        self.root.minsize(960, 640)

        self.client = None
        self.name = ''
        self.room_id = ''
        self.mode = ''
        self.receiver_thread = None
        self.inbox = queue.Queue()
        self.running = False

        self._setup_styles()
        self._build_shell()
        self._build_landing()
        self._poll_inbox()

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Premium.TFrame', background=self.BG)
        style.configure('Card.TFrame', background=self.PANEL)
        style.configure('Panel.TFrame', background=self.PANEL_2)
        style.configure('Premium.TLabel', background=self.BG, foreground=self.TEXT, font=('DejaVu Sans', 12))
        style.configure('Title.TLabel', background=self.BG, foreground=self.TEXT, font=('DejaVu Sans', 26, 'bold'))
        style.configure('Subtitle.TLabel', background=self.BG, foreground=self.MUTED, font=('DejaVu Sans', 11))
        style.configure('Accent.TButton', font=('DejaVu Sans', 11, 'bold'), padding=10)
        style.map('Accent.TButton', foreground=[('active', self.BG)], background=[('active', self.ACCENT)])

    def _build_shell(self):
        self.shell = ttk.Frame(self.root, style='Premium.TFrame')
        self.shell.pack(fill='both', expand=True, padx=18, pady=18)

    def _clear_shell(self):
        for widget in self.shell.winfo_children():
            widget.destroy()

    def _build_landing(self):
        self._clear_shell()

        hero = tk.Frame(self.shell, bg=self.BG)
        hero.pack(fill='both', expand=True)

        left = tk.Frame(hero, bg=self.BG)
        left.pack(side='left', fill='both', expand=True, padx=(0, 18))

        tk.Label(left, text='SecureChat', bg=self.BG, fg=self.TEXT, font=('DejaVu Sans', 34, 'bold')).pack(anchor='w', pady=(28, 8))
        tk.Label(left, text='A premium encrypted room chat client built with Tkinter.', bg=self.BG, fg=self.MUTED, font=('DejaVu Sans', 13)).pack(anchor='w')

        features = tk.Frame(left, bg=self.BG)
        features.pack(anchor='w', pady=24, fill='x')
        for title, body in [
            ('Encrypted', 'Messages are encrypted client-side before leaving your device.'),
            ('Rooms', 'Create or join a shared room with a room id.'),
            ('Multi-user', 'Multiple clients can join the same room and chat together.'),
        ]:
            card = tk.Frame(features, bg=self.PANEL, highlightbackground='#223047', highlightthickness=1)
            card.pack(fill='x', pady=8)
            tk.Label(card, text=title, bg=self.PANEL, fg=self.TEXT, font=('DejaVu Sans', 14, 'bold')).pack(anchor='w', padx=16, pady=(14, 2))
            tk.Label(card, text=body, bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 10), wraplength=420, justify='left').pack(anchor='w', padx=16, pady=(0, 14))

        right = tk.Frame(hero, bg=self.BG)
        right.pack(side='right', fill='y')

        panel = tk.Frame(right, bg=self.PANEL, highlightbackground='#253047', highlightthickness=1)
        panel.pack(fill='y', expand=False, padx=10, pady=18)
        panel.configure(width=320, height=420)
        panel.pack_propagate(False)

        tk.Label(panel, text='Start Chatting', bg=self.PANEL, fg=self.TEXT, font=('DejaVu Sans', 20, 'bold')).pack(anchor='w', padx=20, pady=(20, 8))
        tk.Label(panel, text='Choose how you want to enter a room.', bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 11), wraplength=270, justify='left').pack(anchor='w', padx=20)

        self._premium_button(panel, 'Create a room', self._open_create_dialog).pack(fill='x', padx=20, pady=(34, 10))
        self._premium_button(panel, 'Join a room', self._open_join_dialog, accent2=True).pack(fill='x', padx=20, pady=10)

        footer = tk.Label(panel, text='GUI mode enabled via CHAT_GUI=1', bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 9))
        footer.pack(anchor='s', side='bottom', padx=20, pady=18)

    def _premium_button(self, parent, text, command, accent2=False):
        bg = self.ACCENT_2 if accent2 else self.ACCENT
        fg = '#081018'
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                        activebackground=bg, activeforeground=fg,
                        relief='flat', bd=0, font=('DejaVu Sans', 12, 'bold'), cursor='hand2')
        btn.bind('<Enter>', lambda e: btn.configure(relief='raised'))
        btn.bind('<Leave>', lambda e: btn.configure(relief='flat'))
        return btn

    def _open_create_dialog(self):
        self._open_room_dialog('Create Room', 'create')

    def _open_join_dialog(self):
        self._open_room_dialog('Join Room', 'join')

    def _open_room_dialog(self, title, mode):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=self.BG)
        dialog.geometry('460x390')
        dialog.minsize(460, 390)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=self.PANEL, highlightbackground='#253047', highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=16, pady=16)

        content = tk.Frame(frame, bg=self.PANEL)
        content.pack(fill='both', expand=True)

        tk.Label(content, text=title, bg=self.PANEL, fg=self.TEXT, font=('DejaVu Sans', 20, 'bold')).pack(anchor='w', padx=20, pady=(18, 6))
        tk.Label(content, text='Enter your display name and room id.', bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 10)).pack(anchor='w', padx=20)

        name_var = tk.StringVar()
        room_var = tk.StringVar()

        self._entry_field(content, 'Name', name_var).pack(fill='x', padx=20, pady=(20, 10))
        self._entry_field(content, 'Room ID', room_var).pack(fill='x', padx=20, pady=10)

        footer = tk.Frame(frame, bg=self.PANEL)
        footer.pack(side='bottom', fill='x', padx=20, pady=(8, 18))
        self._premium_button(footer, title, lambda: self._submit_room(dialog, mode, name_var.get().strip(), room_var.get().strip())).pack(side='left')
        tk.Button(footer, text='Cancel', command=dialog.destroy, bg=self.PANEL_2, fg=self.TEXT, relief='flat', bd=0,
                  font=('DejaVu Sans', 11), cursor='hand2').pack(side='right')

    def _entry_field(self, parent, label, var):
        container = tk.Frame(parent, bg=parent['bg'])
        tk.Label(container, text=label, bg=parent['bg'], fg=self.MUTED, font=('DejaVu Sans', 9, 'bold')).pack(anchor='w', pady=(0, 6))
        entry = tk.Entry(container, textvariable=var, bg=self.PANEL_2, fg=self.TEXT, insertbackground=self.TEXT,
                         relief='flat', font=('DejaVu Sans', 12), highlightthickness=1,
                         highlightbackground='#2f3b52', highlightcolor=self.ACCENT)
        entry.pack(fill='x', ipady=10)
        return container

    def _submit_room(self, dialog, mode, name, room_id):
        if not name or not room_id:
            messagebox.showerror('Missing info', 'Please enter both your name and room id.')
            return

        try:
            self.client = NetworkClient()
            self.client.connect()
            self.mode = mode
            self.name = name
            self.room_id = room_id

            if mode == 'create':
                resp = self.client.request({'cmd': 'create_room', 'name': name, 'room_id': room_id})
                if resp.get('status') != 'ok':
                    self.client.close()
                    messagebox.showerror('Room exists', 'That room id already exists. Choose a different one or join it.')
                    return
                self.client.request({'cmd': 'join_room', 'name': name, 'room_id': room_id})
            else:
                resp = self.client.request({'cmd': 'join_room', 'name': name, 'room_id': room_id})
                if resp.get('status') == 'error' and resp.get('reason') == 'no_room':
                    self.client.close()
                    create = messagebox.askyesno('Room not found', 'That room does not exist. Do you want to create it now?')
                    if create:
                        self.client = NetworkClient()
                        self.client.connect()
                        self.client.request({'cmd': 'create_room', 'name': name, 'room_id': room_id})
                        self.client.request({'cmd': 'join_room', 'name': name, 'room_id': room_id})
                    else:
                        return
                elif resp.get('status') != 'ok':
                    self.client.close()
                    messagebox.showerror('Join failed', 'Unable to join the selected room.')
                    return

            dialog.destroy()
            self._build_chat_ui()
            self._start_receiver()
            self._append_system(f'Connected as {self.name} in room {self.room_id}')
            LOGGER.info('Joined room mode=%s name=%s room_id=%s', mode, name, room_id)
        except Exception as exc:
            LOGGER.exception('Failed to submit room mode=%s name=%s room_id=%s', mode, name, room_id)
            if self.client:
                self.client.close()
            messagebox.showerror('Connection failed', f'Could not connect to the server.\n\n{exc}')

    def _build_chat_ui(self):
        self._clear_shell()

        root_frame = tk.Frame(self.shell, bg=self.BG)
        root_frame.pack(fill='both', expand=True)

        sidebar = tk.Frame(root_frame, bg=self.PANEL, width=260, highlightbackground='#253047', highlightthickness=1)
        sidebar.pack(side='left', fill='y', padx=(0, 16))
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text='SecureChat', bg=self.PANEL, fg=self.TEXT, font=('DejaVu Sans', 22, 'bold')).pack(anchor='w', padx=18, pady=(20, 4))
        tk.Label(sidebar, text='Connected room', bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 10)).pack(anchor='w', padx=18)

        info = tk.Frame(sidebar, bg=self.PANEL_2, highlightbackground='#2f3b52', highlightthickness=1)
        info.pack(fill='x', padx=18, pady=18)
        tk.Label(info, text='Room ID', bg=self.PANEL_2, fg=self.MUTED, font=('DejaVu Sans', 9, 'bold')).pack(anchor='w', padx=14, pady=(12, 2))
        tk.Label(info, text=self.room_id, bg=self.PANEL_2, fg=self.TEXT, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w', padx=14, pady=(0, 12))
        tk.Label(info, text='User', bg=self.PANEL_2, fg=self.MUTED, font=('DejaVu Sans', 9, 'bold')).pack(anchor='w', padx=14, pady=(0, 2))
        tk.Label(info, text=self.name, bg=self.PANEL_2, fg=self.TEXT, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w', padx=14, pady=(0, 12))

        tk.Label(sidebar, text='Security', bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 9, 'bold')).pack(anchor='w', padx=18)
        sec = tk.Label(sidebar, text='Messages are encrypted locally with the room id before transmission.', wraplength=210,
                       justify='left', bg=self.PANEL, fg=self.TEXT, font=('DejaVu Sans', 10))
        sec.pack(anchor='w', padx=18, pady=(8, 18))

        self._premium_button(sidebar, 'Back to start', self._reset_to_landing, accent2=True).pack(fill='x', padx=18, pady=(0, 10))
        self._premium_button(sidebar, 'Disconnect', self._disconnect, accent2=False).pack(fill='x', padx=18, pady=(0, 18))

        main = tk.Frame(root_frame, bg=self.BG)
        main.pack(side='right', fill='both', expand=True)

        header = tk.Frame(main, bg=self.BG)
        header.pack(fill='x', pady=(6, 12))
        tk.Label(header, text='Encrypted conversation', bg=self.BG, fg=self.TEXT, font=('DejaVu Sans', 26, 'bold')).pack(anchor='w')
        tk.Label(header, text='Type a message below. It will be encrypted before it leaves your machine.', bg=self.BG, fg=self.MUTED, font=('DejaVu Sans', 11)).pack(anchor='w', pady=(4, 0))

        messages_wrap = tk.Frame(main, bg=self.BG)
        messages_wrap.pack(fill='both', expand=True)
        self.message_canvas = tk.Canvas(messages_wrap, bg=self.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(messages_wrap, orient='vertical', command=self.message_canvas.yview)
        self.message_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.message_canvas.pack(side='left', fill='both', expand=True)

        self.message_container = tk.Frame(self.message_canvas, bg=self.BG)
        self.message_canvas_window = self.message_canvas.create_window((0, 0), window=self.message_container, anchor='nw')
        self.message_container.bind('<Configure>', lambda e: self.message_canvas.configure(scrollregion=self.message_canvas.bbox('all')))
        self.message_canvas.bind('<Configure>', self._resize_message_canvas)

        composer = tk.Frame(main, bg=self.PANEL, highlightbackground='#253047', highlightthickness=1)
        composer.pack(fill='x', pady=(16, 0))
        tk.Label(composer, text='Send a secure message', bg=self.PANEL, fg=self.MUTED, font=('DejaVu Sans', 9, 'bold')).pack(anchor='w', padx=16, pady=(14, 4))

        input_row = tk.Frame(composer, bg=self.PANEL)
        input_row.pack(fill='x', padx=16, pady=(0, 14))
        self.message_var = tk.StringVar()
        self.message_entry = tk.Entry(input_row, textvariable=self.message_var, bg=self.PANEL_2, fg=self.TEXT,
                                      insertbackground=self.TEXT, relief='flat', font=('DejaVu Sans', 12),
                                      highlightthickness=1, highlightbackground='#2f3b52', highlightcolor=self.ACCENT)
        self.message_entry.pack(side='left', fill='x', expand=True, ipady=11, padx=(0, 12))
        self.message_entry.bind('<Return>', lambda e: self._send_message())
        self._premium_button(input_row, 'Send', self._send_message).pack(side='right')

    def _resize_message_canvas(self, event):
        self.message_canvas.itemconfigure(self.message_canvas_window, width=event.width)

    def _start_receiver(self):
        self.running = True
        self.receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self.receiver_thread.start()

    def _receiver_loop(self):
        try:
            while self.running and self.client and self.client.connected:
                line = self.client.reader.readline()
                if not line:
                    LOGGER.info('Receiver reached EOF for room_id=%s', self.room_id)
                    self.inbox.put(('system', 'Disconnected from server'))
                    break
                try:
                    obj = json.loads(line.decode())
                except Exception:
                    continue
                if obj.get('cmd') == 'message':
                    sender = obj.get('sender', 'unknown')
                    ciphertext = obj.get('ciphertext', '')
                    timestamp = obj.get('ts', '')
                    if sender == self.name:
                        continue
                    try:
                        plaintext = decrypt(self.room_id, ciphertext)
                    except Exception:
                        plaintext = '<decrypt-failed>'
                        LOGGER.exception('Failed to decrypt message room_id=%s sender=%s', self.room_id, sender)
                    self.inbox.put(('message', timestamp, sender, plaintext))
        except Exception:
            LOGGER.exception('Receiver loop error room_id=%s', self.room_id)
            self.inbox.put(('system', 'Connection closed'))

    def _poll_inbox(self):
        try:
            while True:
                item = self.inbox.get_nowait()
                kind = item[0]
                if kind == 'message':
                    _, timestamp, sender, plaintext = item
                    self._append_message(timestamp, sender, plaintext)
                elif kind == 'system':
                    self._append_system(item[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_inbox)

    def _append_system(self, text):
        self._append_bubble('System', text, self.ACCENT_2, '#0e1117', align='center', system=True)

    def _append_message(self, timestamp, sender, text):
        color = self.ACCENT if sender != self.name else self.ACCENT_2
        bubble_bg = '#1a2230' if sender != self.name else '#152b25'
        prefix = f'{sender}  ·  {timestamp}' if timestamp else sender
        self._append_bubble(prefix, text, color, bubble_bg, align='left' if sender != self.name else 'right')

    def _append_bubble(self, title, text, accent_color, bubble_bg, align='left', system=False):
        card = tk.Frame(self.message_container, bg=self.BG)
        card.pack(fill='x', pady=8, padx=12)

        if align == 'right':
            inner = tk.Frame(card, bg=self.BG)
            inner.pack(anchor='e', fill='x')
            bubble_anchor = 'e'
        elif align == 'center':
            inner = tk.Frame(card, bg=self.BG)
            inner.pack(anchor='center', fill='x')
            bubble_anchor = 'center'
        else:
            inner = tk.Frame(card, bg=self.BG)
            inner.pack(anchor='w', fill='x')
            bubble_anchor = 'w'

        bubble = tk.Frame(inner, bg=bubble_bg, highlightbackground=accent_color, highlightthickness=1)
        bubble.pack(anchor=bubble_anchor, padx=6, ipadx=0)
        max_width = 640
        tk.Label(bubble, text=title, bg=bubble_bg, fg=accent_color,
                 font=('DejaVu Sans', 9, 'bold'), anchor='w', justify='left').pack(anchor='w', padx=14, pady=(12, 2))
        tk.Label(bubble, text=text, bg=bubble_bg, fg=self.TEXT, wraplength=max_width,
                 justify='left', font=('DejaVu Sans', 11)).pack(anchor='w', padx=14, pady=(0, 12))
        self.root.after(10, lambda: self.message_canvas.yview_moveto(1.0))

    def _send_message(self):
        if not self.client or not self.client.connected:
            messagebox.showerror('Disconnected', 'The client is not connected to the server.')
            return
        text = self.message_var.get().strip()
        if not text:
            return
        self.message_var.set('')
        try:
            ciphertext = encrypt(self.room_id, text)
            self.client.send({'cmd': 'send_message', 'room_id': self.room_id, 'sender': self.name, 'ciphertext': ciphertext})
            self._append_message('', self.name, text)
            LOGGER.info('Message queued room_id=%s sender=%s', self.room_id, self.name)
        except Exception as exc:
            LOGGER.exception('Send failed room_id=%s sender=%s', self.room_id, self.name)
            messagebox.showerror('Send failed', f'Could not send the message.\n\n{exc}')

    def _disconnect(self):
        self.running = False
        if self.client:
            self.client.close()
        LOGGER.info('GUI returned to landing screen')
        self._build_landing()

    def _reset_to_landing(self):
        self._disconnect()


def run_gui():
    try:
        root = tk.Tk()
    except Exception as exc:
        print(f'GUI mode could not start ({exc}). Falling back to CLI mode.')
        run_cli()
        return
    PremiumChatUI(root)
    root.mainloop()


def run_cli():
    import asyncio
    import sys

    LOGGER.info('CLI mode started host=%s port=%s', HOST, PORT)

    async def send_msg(writer, obj):
        data = (json.dumps(obj) + '\n').encode()
        writer.write(data)
        await writer.drain()
        LOGGER.info('CLI sent cmd=%s', obj.get('cmd'))

    async def listen(reader, room_id):
        while True:
            line = await reader.readline()
            if not line:
                LOGGER.info('CLI receiver EOF room_id=%s', room_id)
                print('Disconnected from server')
                return
            try:
                obj = json.loads(line.decode())
            except Exception:
                continue
            if obj.get('cmd') == 'message':
                sender = obj.get('sender')
                ct = obj.get('ciphertext')
                ts = obj.get('ts')
                try:
                    pt = decrypt(room_id, ct)
                except Exception:
                    pt = '<decrypt-failed>'
                    LOGGER.exception('CLI decrypt failed room_id=%s sender=%s', room_id, sender)
                print(f'[{ts}] {sender}: {pt}')
                LOGGER.info('CLI received message room_id=%s sender=%s', room_id, sender)

    async def main():
        reader, writer = await asyncio.open_connection(HOST, PORT)

        print('Create or join a room? (create/join)')
        mode = input('> ').strip()
        name = input('Your name: ').strip()
        room_id = input('Room id: ').strip()

        if mode == 'create':
            await send_msg(writer, {'cmd': 'create_room', 'name': name, 'room_id': room_id})
            resp = json.loads((await reader.readline()).decode())
            if resp.get('status') != 'ok':
                LOGGER.warning('CLI create room failed room_id=%s reason=%s', room_id, resp.get('reason'))
                print('Could not create room:', resp.get('reason'))
                writer.close()
                await writer.wait_closed()
                return
            print('Room created and joined.')
            LOGGER.info('CLI created room room_id=%s name=%s', room_id, name)
            await send_msg(writer, {'cmd': 'join_room', 'name': name, 'room_id': room_id})
            _ = await reader.readline()
        else:
            await send_msg(writer, {'cmd': 'join_room', 'name': name, 'room_id': room_id})
            resp = json.loads((await reader.readline()).decode())
            if resp.get('status') == 'error' and resp.get('reason') == 'no_room':
                LOGGER.warning('CLI join failed because room missing room_id=%s', room_id)
                print('Room does not exist. Create it? (y/n)')
                ans = input('> ').strip().lower()
                if ans == 'y':
                    await send_msg(writer, {'cmd': 'create_room', 'name': name, 'room_id': room_id})
                    await reader.readline()
                    await send_msg(writer, {'cmd': 'join_room', 'name': name, 'room_id': room_id})
                    await reader.readline()
                    LOGGER.info('CLI created missing room room_id=%s name=%s', room_id, name)
                else:
                    print('Exiting')
                    writer.close()
                    await writer.wait_closed()
                    return
            elif resp.get('status') == 'ok':
                print('Joined room.')
                LOGGER.info('CLI joined room room_id=%s name=%s', room_id, name)

        asyncio.create_task(listen(reader, room_id))

        print('You can now type messages. Ctrl-C to quit.')
        try:
            while True:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                text = line.rstrip('\n')
                if not text:
                    continue
                ct = encrypt(room_id, text)
                await send_msg(writer, {'cmd': 'send_message', 'room_id': room_id, 'sender': name, 'ciphertext': ct})
                LOGGER.info('CLI queued message room_id=%s sender=%s', room_id, name)
        except KeyboardInterrupt:
            print('Exiting')
            LOGGER.info('CLI interrupted by user')
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            LOGGER.info('CLI connection closed')

    asyncio.run(main())


if __name__ == '__main__':
    if ENABLE_GUI and TK_AVAILABLE:
        run_gui()
    elif ENABLE_GUI and not TK_AVAILABLE:
        print('Tkinter is not available in this environment. Falling back to CLI mode.')
        run_cli()
    else:
        run_cli()
