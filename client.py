import json
import socket
import threading
import hashlib
import re
import uuid
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime


# ---------- crypto (symmetric XOR keyed off the room password) ----------

def encrypt(password, text):
    key = hashlib.sha256(password.encode()).digest()
    result = bytearray()
    for i, char in enumerate(text.encode()):
        result.append(char ^ key[i % len(key)])
    return result.hex()


def decrypt(password, ciphertext):
    key = hashlib.sha256(password.encode()).digest()
    cipherbytes = bytes.fromhex(ciphertext)
    result = bytearray()
    for i, byte in enumerate(cipherbytes):
        result.append(byte ^ key[i % len(key)])
    return result.decode()


HOST = '127.0.0.1'
PORT = 8888


# ---------- theme ----------

BG = '#0b1220'
SURFACE = '#111a30'
SURFACE_2 = '#172241'
SURFACE_3 = '#1f2c52'
BORDER = '#2a3866'
TEXT = '#e8ebf5'
MUTED = '#8a96b4'
ACCENT = '#6366f1'
ACCENT_HOVER = '#7c7ff5'
SUCCESS = '#10b981'
SUCCESS_HOVER = '#34d399'
WARN = '#f59e0b'
DANGER = '#ef4444'
DANGER_HOVER = '#f87171'
INFO = '#3b82f6'

FONT_BRAND = ('Segoe UI', 30, 'bold')
FONT_TITLE = ('Segoe UI', 16, 'bold')
FONT_SUBTITLE = ('Segoe UI', 11)
FONT_LABEL = ('Segoe UI', 9, 'bold')
FONT_INPUT = ('Segoe UI', 11)
FONT_BTN = ('Segoe UI', 10, 'bold')
FONT_BIG_BTN = ('Segoe UI', 12, 'bold')
FONT_CHAT = ('Segoe UI', 11)
FONT_SENDER = ('Segoe UI', 10, 'bold')
FONT_TIME = ('Segoe UI', 8)
FONT_SYS = ('Segoe UI', 9, 'italic')


# ---------- validation helpers ----------

def validate_room_id(rid):
    if not rid:
        return False, 'Required'
    if not (3 <= len(rid) <= 32):
        return False, 'Must be 3-32 characters'
    if not re.match(r'^[A-Za-z0-9_]+$', rid):
        return False, 'Only letters, numbers, underscore'
    return True, 'Valid'


def validate_name(n):
    if not n:
        return False, 'Required'
    if not (1 <= len(n) <= 32):
        return False, 'Must be 1-32 characters'
    if not re.match(r'^[A-Za-z0-9_ .\-]+$', n):
        return False, 'Only letters, numbers, space, _ . -'
    return True, 'Valid'


def validate_room_name(n):
    if not n:
        return False, 'Required'
    if not (1 <= len(n) <= 48):
        return False, 'Must be 1-48 characters'
    return True, 'Valid'


def password_strength(pw):
    """Return integer 0..5 reflecting password strength."""
    if not pw:
        return 0
    score = 0
    if len(pw) >= 8:
        score += 1
    if len(pw) >= 12:
        score += 1
    if re.search(r'[a-z]', pw) and re.search(r'[A-Z]', pw):
        score += 1
    if re.search(r'\d', pw):
        score += 1
    if re.search(r'[^A-Za-z0-9]', pw):
        score += 1
    return min(score, 5)


def validate_password_for_create(pw):
    if len(pw) < 8:
        return False, 'Min 8 characters'
    if not re.search(r'[a-z]', pw):
        return False, 'Add lowercase letter'
    if not re.search(r'[A-Z]', pw):
        return False, 'Add uppercase letter'
    if not re.search(r'\d', pw):
        return False, 'Add a digit'
    if not re.search(r'[^A-Za-z0-9]', pw):
        return False, 'Add a special character'
    return True, 'Strong password'


def validate_password_for_join(pw):
    if not pw:
        return False, 'Required'
    return True, ''


# ---------- ui helpers ----------

AVATAR_COLORS = [
    '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#3b82f6',
    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#84cc16',
]


def color_for(name):
    if not name:
        return ACCENT
    h = hashlib.md5(name.encode()).digest()[0]
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]


def make_button(parent, text, command, bg=ACCENT, hover=ACCENT_HOVER, fg='white',
                font=FONT_BTN, padx=20, pady=10, **kw):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
        relief='flat', borderwidth=0, cursor='hand2',
        font=font, padx=padx, pady=pady, **kw,
    )
    btn.bind('<Enter>', lambda e, b=btn, h=hover: b.config(bg=h))
    btn.bind('<Leave>', lambda e, b=btn, c=bg: b.config(bg=c))
    return btn


def make_input(parent, password=False):
    """Returns a (frame, entry, hint_label) bundle with a colored border."""
    border = tk.Frame(parent, bg=BORDER, highlightthickness=0)
    inner = tk.Frame(border, bg=SURFACE_2)
    inner.pack(fill='x', padx=1, pady=1)

    entry = tk.Entry(
        inner, bg=SURFACE_2, fg=TEXT, insertbackground=TEXT,
        relief='flat', borderwidth=0, font=FONT_INPUT,
        show='•' if password else '',
    )
    entry.pack(fill='x', padx=10, ipady=8)

    def on_focus_in(_e):
        border.config(bg=ACCENT)

    def on_focus_out(_e):
        border.config(bg=BORDER)

    entry.bind('<FocusIn>', on_focus_in)
    entry.bind('<FocusOut>', on_focus_out)
    return border, entry


def make_label(parent, text, font=FONT_LABEL, fg=MUTED, bg=SURFACE):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, anchor='w')


# ---------- ChatClient ----------

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title('SecureChat')
        self.root.geometry('1100x720')
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.sock = None
        self.connected = False
        self.running = False
        self.name = None
        self.room_id = None
        self.room_name = None
        self.password = None
        self.is_admin = False
        self.current_admin = None
        self.members = []

        # chat-side state
        self.connecting_window = None
        self.chat_area = None
        self.entry = None
        self.title_label = None
        self.members_panel = None
        self.members_list_frame = None
        self.messages = {}                 # msg_id -> sender
        self.pending_msgs = {}             # client_msg_id -> {'sender','text'}

        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.show_login()

    # ---------- screens ----------

    def _clear_root(self):
        for w in self.root.winfo_children():
            w.destroy()

    def show_login(self):
        self._clear_root()
        self.root.title('SecureChat')

        main = tk.Frame(self.root, bg=BG)
        main.pack(expand=True, fill='both')

        card = tk.Frame(main, bg=SURFACE, padx=60, pady=50, highlightthickness=1,
                        highlightbackground=BORDER)
        card.place(relx=0.5, rely=0.5, anchor='center')

        # Brand
        brand = tk.Frame(card, bg=SURFACE)
        brand.pack(pady=(0, 8))
        brand_dot = tk.Canvas(brand, width=44, height=44, bg=SURFACE, highlightthickness=0)
        brand_dot.pack(side='left', padx=(0, 14))
        brand_dot.create_oval(2, 2, 42, 42, fill=ACCENT, outline='')
        brand_dot.create_text(22, 22, text='S', fill='white', font=('Segoe UI', 18, 'bold'))
        tk.Label(brand, text='SecureChat', font=FONT_BRAND, bg=SURFACE,
                 fg=TEXT).pack(side='left')

        tk.Label(card, text='End-to-end encrypted rooms with admin controls',
                 font=FONT_SUBTITLE, bg=SURFACE, fg=MUTED).pack(pady=(0, 36))

        btn_create = make_button(
            card, text='+   Create New Room', command=self.show_create_dialog,
            bg=ACCENT, hover=ACCENT_HOVER, font=FONT_BIG_BTN, padx=36, pady=14,
        )
        btn_create.pack(fill='x', pady=8)

        btn_join = make_button(
            card, text='→   Join Existing Room', command=self.show_join_dialog,
            bg=SURFACE_3, hover=SURFACE_2, font=FONT_BIG_BTN, padx=36, pady=14,
        )
        btn_join.pack(fill='x', pady=8)

        tk.Label(card, text=f'Server: {HOST}:{PORT}', font=('Segoe UI', 8),
                 bg=SURFACE, fg=MUTED).pack(pady=(28, 0))

    def show_create_dialog(self):
        self._open_dialog('create')

    def show_join_dialog(self):
        self._open_dialog('join')

    def _open_dialog(self, mode):
        dlg = tk.Toplevel(self.root)
        dlg.title('Create Room' if mode == 'create' else 'Join Room')
        dlg.geometry('460x640' if mode == 'create' else '460x540')
        dlg.configure(bg=SURFACE)
        dlg.transient(self.root)
        dlg.resizable(False, False)
        self._safe_grab(dlg)

        # Header
        header = tk.Frame(dlg, bg=SURFACE)
        header.pack(fill='x', padx=30, pady=(24, 8))
        title_text = 'Create New Room' if mode == 'create' else 'Join Existing Room'
        tk.Label(header, text=title_text, font=FONT_TITLE, bg=SURFACE,
                 fg=TEXT, anchor='w').pack(fill='x')
        subtitle = ('Set a strong password — everyone uses it to encrypt messages.'
                    if mode == 'create'
                    else 'Enter the room id and password to join.')
        tk.Label(header, text=subtitle, font=FONT_SUBTITLE, bg=SURFACE,
                 fg=MUTED, anchor='w', justify='left', wraplength=400).pack(fill='x', pady=(4, 0))

        # Body
        body = tk.Frame(dlg, bg=SURFACE)
        body.pack(fill='both', expand=True, padx=30, pady=(12, 20))

        fields = {}

        def add_field(label, key, password=False, validator=None):
            make_label(body, label, bg=SURFACE).pack(fill='x', pady=(10, 4))
            border, entry = make_input(body, password=password)
            border.pack(fill='x')
            hint = make_label(body, '', font=('Segoe UI', 8), bg=SURFACE, fg=MUTED)
            hint.pack(fill='x', pady=(2, 0))

            def on_key(_e):
                value = entry.get()
                if not value:
                    hint.config(text='', fg=MUTED)
                    border.config(bg=BORDER if dlg.focus_get() is not entry else ACCENT)
                    return
                ok, msg = validator(value) if validator else (True, '')
                if ok:
                    hint.config(text=msg, fg=SUCCESS)
                    border.config(bg=SUCCESS)
                else:
                    hint.config(text=msg, fg=DANGER)
                    border.config(bg=DANGER)
            entry.bind('<KeyRelease>', on_key)
            fields[key] = {'entry': entry, 'hint': hint, 'border': border}
            return entry

        if mode == 'create':
            add_field('Room Display Name', 'room_name', validator=validate_room_name)
        add_field('Room ID (unique)', 'room_id', validator=validate_room_id)

        # Password field is special: needs show/hide + strength meter.
        make_label(body, 'Room Password', bg=SURFACE).pack(fill='x', pady=(10, 4))

        pw_border = tk.Frame(body, bg=BORDER)
        pw_border.pack(fill='x')
        pw_inner = tk.Frame(pw_border, bg=SURFACE_2)
        pw_inner.pack(fill='x', padx=1, pady=1)
        pw_entry = tk.Entry(
            pw_inner, bg=SURFACE_2, fg=TEXT, insertbackground=TEXT,
            relief='flat', borderwidth=0, font=FONT_INPUT, show='•',
        )
        pw_entry.pack(side='left', fill='x', expand=True, padx=(10, 0), ipady=8)

        toggle_state = {'visible': False}

        def toggle_pw():
            toggle_state['visible'] = not toggle_state['visible']
            pw_entry.config(show='' if toggle_state['visible'] else '•')
            toggle_btn.config(text='Hide' if toggle_state['visible'] else 'Show')

        toggle_btn = tk.Button(
            pw_inner, text='Show', command=toggle_pw, bd=0,
            bg=SURFACE_2, fg=MUTED, activebackground=SURFACE_2,
            activeforeground=TEXT, cursor='hand2', font=('Segoe UI', 9, 'bold'), padx=10,
        )
        toggle_btn.pack(side='right')
        pw_entry.bind('<FocusIn>', lambda _e: pw_border.config(bg=ACCENT))
        pw_entry.bind('<FocusOut>', lambda _e: pw_border.config(bg=BORDER))

        # Strength meter (only meaningful for create)
        meter_frame = tk.Frame(body, bg=SURFACE)
        if mode == 'create':
            meter_frame.pack(fill='x', pady=(6, 0))
            meter_segments = []
            for _ in range(5):
                seg = tk.Frame(meter_frame, bg=BORDER, height=4, width=60)
                seg.pack(side='left', padx=2)
                seg.pack_propagate(False)
                meter_segments.append(seg)
            meter_label = tk.Label(body, text='', font=('Segoe UI', 8),
                                   bg=SURFACE, fg=MUTED, anchor='w')
            meter_label.pack(fill='x', pady=(2, 0))
        else:
            meter_segments = []
            meter_label = None

        pw_hint = make_label(body, '', font=('Segoe UI', 8), bg=SURFACE, fg=MUTED)
        pw_hint.pack(fill='x', pady=(4, 0))

        strength_colors = [DANGER, DANGER, WARN, INFO, SUCCESS, SUCCESS_HOVER]
        strength_words = ['Too short', 'Weak', 'Fair', 'Good', 'Strong', 'Very strong']

        def on_pw_key(_e):
            value = pw_entry.get()
            if mode == 'create':
                score = password_strength(value)
                for i, seg in enumerate(meter_segments):
                    seg.config(bg=strength_colors[score] if i < score else BORDER)
                if meter_label is not None:
                    meter_label.config(
                        text=strength_words[score] if value else '',
                        fg=strength_colors[score],
                    )
                if not value:
                    pw_hint.config(text='', fg=MUTED)
                    pw_border.config(bg=BORDER if dlg.focus_get() is not pw_entry else ACCENT)
                    return
                ok, msg = validate_password_for_create(value)
                pw_hint.config(text=msg, fg=SUCCESS if ok else DANGER)
                pw_border.config(bg=SUCCESS if ok else DANGER)
            else:
                ok, msg = validate_password_for_join(value)
                pw_hint.config(text=msg, fg=SUCCESS if ok else DANGER)
                pw_border.config(bg=SUCCESS if ok else (BORDER if not value else DANGER))
        pw_entry.bind('<KeyRelease>', on_pw_key)

        add_field('Your Display Name', 'name', validator=validate_name)

        # Submit / cancel
        btn_row = tk.Frame(dlg, bg=SURFACE)
        btn_row.pack(fill='x', padx=30, pady=(0, 24))

        def submit():
            room_id = fields['room_id']['entry'].get().strip()
            name = fields['name']['entry'].get().strip()
            password = pw_entry.get()
            room_name = (fields['room_name']['entry'].get().strip()
                         if mode == 'create' else None)

            checks = [
                validate_room_id(room_id),
                validate_name(name),
                (validate_password_for_create(password) if mode == 'create'
                 else validate_password_for_join(password)),
            ]
            if mode == 'create':
                checks.append(validate_room_name(room_name))

            failures = [m for ok, m in checks if not ok]
            if failures:
                messagebox.showerror('Fix validation', '\n'.join(f'• {m}' for m in failures))
                return

            dlg.destroy()
            self.show_connecting()
            threading.Thread(
                target=self.connect,
                args=(mode, name, room_id, room_name, password),
                daemon=True,
            ).start()

        make_button(btn_row, 'Cancel', dlg.destroy,
                    bg=SURFACE_3, hover=SURFACE_2, padx=28).pack(side='right', padx=(8, 0))
        make_button(btn_row, 'Continue', submit,
                    bg=ACCENT, hover=ACCENT_HOVER, padx=28).pack(side='right')

    def show_connecting(self):
        win = tk.Toplevel(self.root)
        self.connecting_window = win
        win.title('Connecting')
        win.geometry('320x140')
        win.configure(bg=SURFACE)
        win.transient(self.root)
        win.resizable(False, False)

        tk.Label(win, text='Connecting to server…', font=FONT_TITLE,
                 bg=SURFACE, fg=TEXT).pack(pady=(28, 6))
        tk.Label(win, text=f'{HOST}:{PORT}', font=FONT_SUBTITLE,
                 bg=SURFACE, fg=MUTED).pack()
        self._safe_grab(win)

    def _close_connecting(self):
        if self.connecting_window is not None:
            try:
                self.connecting_window.destroy()
            except Exception:
                pass
            self.connecting_window = None

    def _safe_grab(self, dlg):
        """Tk on X11 raises 'grab failed: window not viewable' if grab_set
        runs before the window has been mapped. Defer until it is."""
        try:
            if dlg.winfo_exists() and dlg.winfo_viewable():
                dlg.grab_set()
            elif dlg.winfo_exists():
                dlg.after(40, lambda: self._safe_grab(dlg))
        except tk.TclError:
            pass

    # ---------- networking ----------

    def connect(self, mode, name, room_id, room_name, password):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((HOST, PORT))
            self.sock.settimeout(None)
            self.connected = True

            self.name = name
            self.room_id = room_id
            self.room_name = room_name
            self.password = password

            password_hash = hashlib.sha256(password.encode()).hexdigest()

            # 'create' tries to create the room first, but if it already exists
            # we silently fall through to join. The password check on join_room
            # is the gatekeeper, so this can't be used to hijack someone else's room.
            room_was_created = False
            room_existed_already = False
            if mode == 'create':
                self._send_now({
                    'cmd': 'create_room',
                    'name': name,
                    'room_id': room_id,
                    'room_name': room_name,
                    'password_hash': password_hash,
                })
                result = self._recv_one()
                if result.get('status') == 'ok':
                    room_was_created = True
                else:
                    reason = (result.get('reason') or '').lower()
                    if 'already exists' in reason:
                        room_existed_already = True
                    else:
                        raise ConnectionError(
                            f"Failed to create room: {result.get('reason', 'Unknown')}"
                        )

            self._send_now({
                'cmd': 'join_room',
                'name': name,
                'room_id': room_id,
                'password_hash': password_hash,
            })
            result = self._recv_one()
            if result.get('status') != 'ok':
                reason = result.get('reason', 'Unknown error')
                if room_existed_already and reason == 'wrong_password':
                    pretty = (
                        f'A room with ID "{room_id}" already exists, but the password '
                        'you entered does not match. Either pick a different Room ID, '
                        'or click "Join Existing Room" and use the original password.'
                    )
                else:
                    pretty = {
                        'wrong_password': 'Incorrect room password.',
                        'no_room': 'Room does not exist.',
                        'name_taken': 'Someone else in the room already uses that name.',
                    }.get(reason, f'Failed to join: {reason}')
                raise ConnectionError(pretty)

            room_info = result.get('room_info', {}) or {}
            self.current_admin = room_info.get('admin')
            self.is_admin = (self.current_admin == self.name)
            self.room_name = room_info.get('room_name') or room_id

            self.root.after(0, self._close_connecting)
            self.root.after(0, self.setup_chat)
            if room_was_created:
                self.root.after(120, lambda: self._add_system(f'Room "{self.room_name}" created.'))
                self.root.after(120, lambda: self._add_system('You are the ADMIN of this room.'))
            elif room_existed_already:
                self.root.after(120, lambda: self._add_system(
                    f'Room "{self.room_name}" already existed — joined as a member.'
                ))
            else:
                self.root.after(120, lambda: self._add_system(f'Joined room: {self.room_name}'))
            self._start_receiver()

        except socket.timeout:
            self._fail_connect('Connection timed out. Make sure server.py is running.')
        except ConnectionRefusedError:
            self._fail_connect(f'Cannot reach server at {HOST}:{PORT}.\nIs server.py running?')
        except ConnectionError as exc:
            self._fail_connect(str(exc))
        except Exception as exc:
            # Bind the message NOW; the bare `e` was the source of the original NameError.
            err = str(exc) or exc.__class__.__name__
            self._fail_connect(f'Connection failed: {err}')

    def _fail_connect(self, message):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        def show():
            self._close_connecting()
            messagebox.showerror('Error', message)

        self.root.after(0, show)

    def _send_now(self, message):
        self.sock.sendall((json.dumps(message) + '\n').encode())

    def _recv_one(self):
        """Read one newline-terminated JSON message from the socket."""
        buf = b''
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('Server closed the connection.')
            buf += chunk
            if b'\n' in buf:
                line, rest = buf.split(b'\n', 1)
                self._recv_buffer = rest
                return json.loads(line.decode())

    def _start_receiver(self):
        self.running = True
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _receive_loop(self):
        buf = getattr(self, '_recv_buffer', b'')
        while self.running and self.connected:
            try:
                if b'\n' not in buf:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line.decode())
                    self._dispatch_server_msg(msg)
            except Exception as exc:
                if self.running:
                    print(f'Receive error: {exc}')
                break
        self.running = False

    def _dispatch_server_msg(self, msg):
        cmd = msg.get('cmd')

        if cmd == 'message':
            sender = msg.get('sender')
            ciphertext = msg.get('ciphertext', '')
            msg_id = msg.get('msg_id')
            try:
                text = decrypt(self.password, ciphertext)
            except Exception:
                text = '[Decryption failed]'
            self.root.after(0, lambda s=sender, t=text, m=msg_id: self._add_message(s, t, m))

        elif cmd == 'message_ack':
            msg_id = msg.get('msg_id')
            client_id = msg.get('client_msg_id')
            self.root.after(0, lambda c=client_id, m=msg_id: self._confirm_local_message(c, m))

        elif cmd == 'message_deleted':
            msg_id = msg.get('msg_id')
            self.root.after(0, lambda m=msg_id: self._mark_message_deleted(m))

        elif cmd == 'message_edited':
            msg_id = msg.get('msg_id')
            try:
                new_text = decrypt(self.password, msg.get('ciphertext', ''))
            except Exception:
                new_text = '[Decryption failed]'
            self.root.after(0, lambda m=msg_id, t=new_text: self._apply_edit(m, t))

        elif cmd == 'member_joined':
            username = msg.get('username')
            if username != self.name:
                self.root.after(0, lambda u=username: self._add_system(f'{u} joined the room'))

        elif cmd == 'member_left':
            username = msg.get('username')
            kicked = msg.get('kicked')
            note = f'{username} was removed by the admin' if kicked else f'{username} left the room'
            self.root.after(0, lambda n=note: self._add_system(n))

        elif cmd == 'member_list':
            self.members = msg.get('members', [])
            new_admin = msg.get('admin')
            self.current_admin = new_admin
            self.is_admin = (new_admin == self.name)
            self.root.after(0, self._render_members)
            self.root.after(0, self._refresh_title)

        elif cmd == 'admin_changed':
            new_admin = msg.get('new_admin')
            self.current_admin = new_admin
            self.is_admin = (new_admin == self.name)
            self.root.after(0, lambda a=new_admin: self._add_system(f'Ownership transferred to {a}'))
            self.root.after(0, self._render_members)
            self.root.after(0, self._refresh_title)
            # Re-render history so Edit/Delete buttons appear or disappear for the new admin.
            self.root.after(0, self._redraw_chat)

        elif cmd == 'kicked':
            reason = msg.get('reason', 'You were removed by the admin.')
            self.root.after(0, lambda r=reason: self._handle_kicked(r))

    # ---------- chat ui ----------

    def setup_chat(self):
        self._clear_root()
        self.root.title(f'SecureChat — {self.room_name}')
        self.messages = {}
        self.pending_msgs = {}
        self.message_log = []  # ordered list of {kind, ...} entries — source of truth for chat redraws

        # Top bar
        top = tk.Frame(self.root, bg=SURFACE, height=64)
        top.pack(fill='x', side='top')
        top.pack_propagate(False)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x')

        left_top = tk.Frame(top, bg=SURFACE)
        left_top.pack(side='left', padx=18, pady=10)

        brand_chip = tk.Canvas(left_top, width=32, height=32, bg=SURFACE, highlightthickness=0)
        brand_chip.pack(side='left', padx=(0, 12))
        brand_chip.create_oval(2, 2, 30, 30, fill=ACCENT, outline='')
        brand_chip.create_text(16, 16, text='S', fill='white', font=('Segoe UI', 12, 'bold'))
        meta = tk.Frame(left_top, bg=SURFACE)
        meta.pack(side='left')
        self.title_label = tk.Label(meta, text='', font=FONT_TITLE,
                                    bg=SURFACE, fg=TEXT, anchor='w')
        self.title_label.pack(anchor='w')
        self.subtitle_label = tk.Label(meta, text='', font=('Segoe UI', 9),
                                       bg=SURFACE, fg=MUTED, anchor='w')
        self.subtitle_label.pack(anchor='w')

        # Right side: user chip + disconnect
        right_top = tk.Frame(top, bg=SURFACE)
        right_top.pack(side='right', padx=14)

        user_chip = tk.Frame(right_top, bg=SURFACE_3)
        user_chip.pack(side='left', padx=8, pady=14)
        av = tk.Canvas(user_chip, width=26, height=26, bg=SURFACE_3, highlightthickness=0)
        av.pack(side='left', padx=(8, 6), pady=4)
        col = color_for(self.name)
        av.create_oval(2, 2, 24, 24, fill=col, outline='')
        av.create_text(13, 13, text=(self.name[:1].upper() if self.name else '?'),
                       fill='white', font=('Segoe UI', 10, 'bold'))
        tk.Label(user_chip, text=self.name, font=FONT_LABEL,
                 bg=SURFACE_3, fg=TEXT).pack(side='left', padx=(0, 12), pady=4)

        make_button(right_top, 'Leave room', self.disconnect,
                    bg=DANGER, hover=DANGER_HOVER, padx=14, pady=8).pack(side='left', padx=8, pady=14)

        # Body: members panel + chat
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)

        # Members panel
        self.members_panel = tk.Frame(body, bg=SURFACE, width=240)
        self.members_panel.pack(side='left', fill='y')
        self.members_panel.pack_propagate(False)

        tk.Frame(body, bg=BORDER, width=1).pack(side='left', fill='y')

        m_header = tk.Frame(self.members_panel, bg=SURFACE)
        m_header.pack(fill='x', padx=14, pady=(14, 8))
        tk.Label(m_header, text='Members', font=FONT_LABEL,
                 bg=SURFACE, fg=MUTED).pack(side='left')
        self.member_count_label = tk.Label(m_header, text='0', font=FONT_LABEL,
                                           bg=SURFACE, fg=MUTED)
        self.member_count_label.pack(side='right')

        self.members_list_frame = tk.Frame(self.members_panel, bg=SURFACE)
        self.members_list_frame.pack(fill='both', expand=True, padx=6)

        # Admin hint at the bottom of members panel
        self.admin_hint = tk.Label(
            self.members_panel,
            text='',
            font=('Segoe UI', 8, 'italic'),
            bg=SURFACE, fg=MUTED, wraplength=210, justify='left',
        )
        self.admin_hint.pack(fill='x', side='bottom', padx=14, pady=10)

        # Chat column
        chat_col = tk.Frame(body, bg=BG)
        chat_col.pack(side='left', fill='both', expand=True)

        chat_wrap = tk.Frame(chat_col, bg=BG)
        chat_wrap.pack(fill='both', expand=True, padx=16, pady=(14, 0))

        self.chat_area = scrolledtext.ScrolledText(
            chat_wrap, font=FONT_CHAT, bg=SURFACE, fg=TEXT,
            wrap=tk.WORD, relief='flat', borderwidth=0,
            insertbackground=TEXT, padx=12, pady=10,
            highlightthickness=1, highlightbackground=BORDER,
        )
        self.chat_area.pack(fill='both', expand=True)
        self.chat_area.config(state='disabled')

        self.chat_area.tag_config('system', foreground=MUTED, font=FONT_SYS,
                                  spacing1=4, spacing3=4, lmargin1=8, lmargin2=8)
        self.chat_area.tag_config('time', foreground=MUTED, font=FONT_TIME)
        self.chat_area.tag_config('sender_me', foreground=SUCCESS, font=FONT_SENDER,
                                  spacing1=6, lmargin1=6, lmargin2=6)
        self.chat_area.tag_config('sender_other', foreground=ACCENT, font=FONT_SENDER,
                                  spacing1=6, lmargin1=6, lmargin2=6)
        self.chat_area.tag_config('body', spacing3=4, lmargin1=6, lmargin2=6)
        self.chat_area.tag_config('deleted', foreground=MUTED, font=FONT_SYS,
                                  spacing1=4, spacing3=4, lmargin1=8, lmargin2=8)

        self.chat_area.bind('<Button-3>', self._on_chat_right_click)

        # Input area
        input_wrap = tk.Frame(chat_col, bg=BG)
        input_wrap.pack(fill='x', padx=16, pady=14)

        input_border = tk.Frame(input_wrap, bg=BORDER)
        input_border.pack(fill='x')
        inner = tk.Frame(input_border, bg=SURFACE_2)
        inner.pack(fill='x', padx=1, pady=1)

        self.entry = tk.Entry(
            inner, bg=SURFACE_2, fg=TEXT, insertbackground=TEXT,
            relief='flat', borderwidth=0, font=FONT_INPUT,
        )
        self.entry.pack(side='left', fill='x', expand=True, padx=12, ipady=10)
        self.entry.bind('<FocusIn>', lambda _e: input_border.config(bg=ACCENT))
        self.entry.bind('<FocusOut>', lambda _e: input_border.config(bg=BORDER))
        self.entry.bind('<Return>', lambda _e: self._send_message())

        send_btn = make_button(inner, 'Send', self._send_message,
                               bg=SUCCESS, hover=SUCCESS_HOVER, padx=18, pady=8)
        send_btn.pack(side='right', padx=4, pady=2)

        self._refresh_title()
        self._render_members()
        self.entry.focus_set()

    def _refresh_title(self):
        if self.title_label is None:
            return
        room_label = self.room_name or self.room_id or 'Room'
        crown = '   ★ ADMIN' if self.is_admin else ''
        self.title_label.config(text=f'{room_label}{crown}')
        sub = f'ID: {self.room_id}   •   Admin: {self.current_admin or "—"}'
        self.subtitle_label.config(text=sub)
        if self.is_admin:
            self.admin_hint.config(
                text='Tip: click ⋮ next to a member to remove them or transfer ownership. '
                     'Right-click any message to delete it.',
            )
        else:
            self.admin_hint.config(text='')

    def _render_members(self):
        if self.members_list_frame is None:
            return
        for w in self.members_list_frame.winfo_children():
            w.destroy()

        self.member_count_label.config(text=str(len(self.members)))

        for name in self.members:
            row = tk.Frame(self.members_list_frame, bg=SURFACE)
            row.pack(fill='x', padx=6, pady=2)

            # hover effect
            def _enter(_e, r=row): r.config(bg=SURFACE_3)
            def _leave(_e, r=row): r.config(bg=SURFACE)
            row.bind('<Enter>', _enter)
            row.bind('<Leave>', _leave)

            avatar = tk.Canvas(row, width=30, height=30, bg=SURFACE,
                               highlightthickness=0)
            avatar.pack(side='left', padx=(6, 8), pady=6)
            avatar.create_oval(2, 2, 28, 28, fill=color_for(name), outline='')
            avatar.create_text(15, 15, text=name[:1].upper(), fill='white',
                               font=('Segoe UI', 11, 'bold'))

            label_frame = tk.Frame(row, bg=SURFACE)
            label_frame.pack(side='left', fill='x', expand=True)
            display = name + ('  (you)' if name == self.name else '')
            tk.Label(label_frame, text=display, font=FONT_LABEL,
                     bg=SURFACE, fg=TEXT, anchor='w').pack(anchor='w')
            tag = 'Admin' if name == self.current_admin else 'Member'
            tk.Label(label_frame, text=tag, font=('Segoe UI', 8),
                     bg=SURFACE, fg=WARN if name == self.current_admin else MUTED,
                     anchor='w').pack(anchor='w')

            if self.is_admin and name != self.name:
                btn = tk.Label(row, text='⋮', font=('Segoe UI', 14, 'bold'),
                               bg=SURFACE, fg=MUTED, cursor='hand2', padx=8)
                btn.pack(side='right', pady=8)
                btn.bind('<Button-1>', lambda e, n=name: self._show_member_menu(e, n))
                btn.bind('<Enter>', lambda _e, b=btn: b.config(fg=TEXT))
                btn.bind('<Leave>', lambda _e, b=btn: b.config(fg=MUTED))

    def _show_member_menu(self, event, target_name):
        menu = tk.Menu(self.root, tearoff=0, bg=SURFACE_2, fg=TEXT,
                       activebackground=ACCENT, activeforeground='white',
                       borderwidth=0)
        menu.add_command(
            label=f'Remove {target_name} from room',
            command=lambda: self._confirm_kick(target_name),
        )
        menu.add_separator()
        menu.add_command(
            label=f'Transfer ownership to {target_name}',
            command=lambda: self._confirm_transfer(target_name),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _confirm_kick(self, target):
        if not messagebox.askyesno(
            'Remove user',
            f'Remove "{target}" from the room? They will be disconnected.',
        ):
            return
        self._send_safe({'cmd': 'kick_user', 'room_id': self.room_id, 'target': target})

    def _confirm_transfer(self, target):
        if not messagebox.askyesno(
            'Transfer ownership',
            f'Transfer admin to "{target}"? You will lose admin privileges.',
        ):
            return
        self._send_safe({'cmd': 'transfer_admin', 'room_id': self.room_id, 'new_admin': target})

    def _on_chat_right_click(self, event):
        index = self.chat_area.index(f'@{event.x},{event.y}')
        tags = self.chat_area.tag_names(index)
        target_id = None
        for t in tags:
            if t.startswith('msg_'):
                target_id = t[4:]
                break
        if not target_id:
            return
        entry = next(
            (e for e in self.message_log if e.get('msg_id') == target_id),
            None,
        )
        if not entry or entry.get('deleted'):
            return
        if not (self.is_admin or entry.get('sender') == self.name):
            return
        menu = tk.Menu(self.root, tearoff=0, bg=SURFACE_2, fg=TEXT,
                       activebackground=ACCENT, activeforeground='white',
                       borderwidth=0)
        menu.add_command(
            label='Edit this message',
            command=lambda mid=target_id, t=entry.get('text', ''): self._prompt_edit(mid, t),
        )
        menu.add_separator()
        menu.add_command(
            label='Delete this message',
            command=lambda mid=target_id: self._request_delete(mid),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ---------- chat messages ----------
    #
    # All rendering goes through self.message_log + self._render_one so that admin
    # status changes can simply trigger a full redraw to add/remove inline buttons.

    def _add_system(self, text):
        if not self.chat_area:
            return
        entry = {'kind': 'system', 'text': text}
        self.message_log.append(entry)
        self._render_one(entry)

    def _add_message(self, sender, text, msg_id):
        if not self.chat_area:
            return
        entry = {
            'kind': 'message',
            'msg_id': msg_id,
            'sender': sender,
            'text': text,
            'deleted': False,
            'edited': False,
            'ts': datetime.now().strftime('%H:%M'),
        }
        self.message_log.append(entry)
        self.messages[msg_id] = sender
        self._render_one(entry)

    def _confirm_local_message(self, client_msg_id, server_msg_id):
        """Server has assigned an id to a message we sent. Swap the placeholder
        id for the real one in the log and redraw so admin buttons can act on it."""
        entry = self.pending_msgs.pop(client_msg_id, None)
        if not entry or not server_msg_id:
            return
        entry['msg_id'] = server_msg_id
        self.messages[server_msg_id] = entry['sender']
        self._redraw_chat()

    def _mark_message_deleted(self, msg_id):
        for entry in self.message_log:
            if entry.get('msg_id') == msg_id:
                entry['deleted'] = True
                entry['text'] = '× Message deleted by admin'
                break
        else:
            return
        self.messages.pop(msg_id, None)
        self._redraw_chat()

    def _apply_edit(self, msg_id, new_text):
        for entry in self.message_log:
            if entry.get('msg_id') == msg_id and not entry.get('deleted'):
                entry['text'] = new_text
                entry['edited'] = True
                break
        else:
            return
        self._redraw_chat()

    def _redraw_chat(self):
        """Wipe and re-render the chat area from self.message_log. Preserves
        scroll-to-bottom behavior so live conversations don't jump around."""
        if not self.chat_area:
            return
        try:
            yview = self.chat_area.yview()
            stuck_to_bottom = yview[1] >= 0.995
        except Exception:
            stuck_to_bottom = True

        self.chat_area.config(state='normal')
        self.chat_area.delete('1.0', tk.END)
        self.chat_area.config(state='disabled')

        for entry in self.message_log:
            self._render_one(entry)

        if stuck_to_bottom:
            self.chat_area.see(tk.END)

    def _render_one(self, entry):
        if not self.chat_area:
            return
        self.chat_area.config(state='normal')

        if entry['kind'] == 'system':
            self.chat_area.insert(tk.END, f"  ·  {entry['text']}\n", ('system',))
            self.chat_area.config(state='disabled')
            self.chat_area.see(tk.END)
            return

        msg_id = entry.get('msg_id') or ''
        sender = entry['sender']
        text = entry['text']
        ts = entry.get('ts', '')
        deleted = entry.get('deleted', False)
        edited = entry.get('edited', False)
        is_local_pending = isinstance(msg_id, str) and msg_id.startswith('local_')

        sender_tag = 'sender_me' if sender == self.name else 'sender_other'
        msg_tag = f'msg_{msg_id}' if msg_id else None
        body_tag = f'msgbody_{msg_id}' if msg_id else None
        bubble_tags_text = ('time',) + ((msg_tag,) if msg_tag else ())

        self.chat_area.insert(tk.END, f'  {sender}', (sender_tag,) + ((msg_tag,) if msg_tag else ()))
        self.chat_area.insert(tk.END, f'   {ts}', bubble_tags_text)

        # Edit / Delete chips. Admin can act on anyone's message; everyone else
        # can only act on their own. Pending self-messages get them after ack.
        can_modify = self.is_admin or (sender == self.name)
        if can_modify and msg_id and not deleted and not is_local_pending:
            self.chat_area.insert(tk.END, '   ', bubble_tags_text)
            edit_btn = tk.Label(
                self.chat_area, text=' Edit ', bg=SURFACE_3, fg=TEXT,
                font=('Segoe UI', 8, 'bold'), cursor='hand2',
                padx=4, pady=0, borderwidth=0,
            )
            edit_btn.bind('<Button-1>',
                          lambda _e, mid=msg_id, t=text: self._prompt_edit(mid, t))
            edit_btn.bind('<Enter>',
                          lambda _e, b=edit_btn: b.config(bg=ACCENT, fg='white'))
            edit_btn.bind('<Leave>',
                          lambda _e, b=edit_btn: b.config(bg=SURFACE_3, fg=TEXT))
            self.chat_area.window_create(tk.END, window=edit_btn, padx=2)

            del_btn = tk.Label(
                self.chat_area, text=' Delete ', bg=SURFACE_3, fg=TEXT,
                font=('Segoe UI', 8, 'bold'), cursor='hand2',
                padx=4, pady=0, borderwidth=0,
            )
            del_btn.bind('<Button-1>',
                         lambda _e, mid=msg_id: self._request_delete(mid))
            del_btn.bind('<Enter>',
                         lambda _e, b=del_btn: b.config(bg=DANGER, fg='white'))
            del_btn.bind('<Leave>',
                         lambda _e, b=del_btn: b.config(bg=SURFACE_3, fg=TEXT))
            self.chat_area.window_create(tk.END, window=del_btn, padx=2)

        if edited and not deleted:
            self.chat_area.insert(tk.END, '   (edited)', bubble_tags_text)

        self.chat_area.insert(tk.END, '\n', bubble_tags_text)

        body_style = 'deleted' if deleted else 'body'
        body_tags = (body_style,) + ((msg_tag, body_tag) if msg_tag else ())
        self.chat_area.insert(tk.END, f'  {text}\n\n', body_tags)

        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)

    def _request_delete(self, msg_id):
        if not messagebox.askyesno(
            'Delete message',
            'Delete this message for everyone in the room?',
        ):
            return
        self._send_safe({
            'cmd': 'delete_message',
            'room_id': self.room_id,
            'msg_id': msg_id,
        })

    def _prompt_edit(self, msg_id, current_text):
        dlg = tk.Toplevel(self.root)
        dlg.title('Edit message')
        dlg.configure(bg=SURFACE)
        dlg.geometry('540x280')
        dlg.resizable(False, False)
        dlg.transient(self.root)

        tk.Label(dlg, text='Edit message', font=FONT_TITLE,
                 bg=SURFACE, fg=TEXT).pack(padx=28, pady=(22, 4), anchor='w')
        tk.Label(dlg, text='Your edit replaces the message for everyone in the room.',
                 font=FONT_SUBTITLE, bg=SURFACE, fg=MUTED, anchor='w',
                 wraplength=480, justify='left').pack(padx=28, anchor='w')

        body = tk.Frame(dlg, bg=SURFACE)
        body.pack(fill='both', expand=True, padx=28, pady=14)

        border = tk.Frame(body, bg=BORDER)
        border.pack(fill='both', expand=True)
        inner = tk.Frame(border, bg=SURFACE_2)
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        txt = tk.Text(inner, height=4, bg=SURFACE_2, fg=TEXT,
                      insertbackground=TEXT, relief='flat', borderwidth=0,
                      font=FONT_INPUT, wrap='word')
        txt.pack(fill='both', expand=True, padx=10, pady=8)
        txt.insert('1.0', current_text)
        txt.focus_set()
        txt.bind('<FocusIn>', lambda _e: border.config(bg=ACCENT))
        txt.bind('<FocusOut>', lambda _e: border.config(bg=BORDER))

        btn_row = tk.Frame(dlg, bg=SURFACE)
        btn_row.pack(fill='x', padx=28, pady=(0, 20))

        def submit():
            new_text = txt.get('1.0', 'end-1c').strip()
            if not new_text:
                messagebox.showerror('Empty', 'Message cannot be empty.')
                return
            if len(new_text) > 2000:
                messagebox.showerror('Too long', 'Messages must be 2000 characters or fewer.')
                return
            if new_text == current_text:
                dlg.destroy()
                return
            try:
                ciphertext = encrypt(self.password, new_text)
            except Exception as exc:
                messagebox.showerror('Encryption error', str(exc))
                return
            self._send_safe({
                'cmd': 'edit_message',
                'room_id': self.room_id,
                'msg_id': msg_id,
                'ciphertext': ciphertext,
            })
            dlg.destroy()

        make_button(btn_row, 'Cancel', dlg.destroy,
                    bg=SURFACE_3, hover=SURFACE_2, padx=22).pack(side='right', padx=(6, 0))
        make_button(btn_row, 'Save', submit,
                    bg=ACCENT, hover=ACCENT_HOVER, padx=22).pack(side='right')

        self._safe_grab(dlg)

    def _send_message(self):
        if not self.entry:
            return
        text = self.entry.get().strip()
        if not text:
            return
        if len(text) > 2000:
            messagebox.showwarning('Too long', 'Messages must be 2000 characters or fewer.')
            return
        self.entry.delete(0, tk.END)

        if not self.connected:
            self._add_system('Not connected to server.')
            return

        client_msg_id = uuid.uuid4().hex[:12]
        try:
            ciphertext = encrypt(self.password, text)
            # Render immediately with a placeholder id. _confirm_local_message will
            # swap the id once the server ack arrives, then redraw to attach buttons.
            entry = {
                'kind': 'message',
                'msg_id': f'local_{client_msg_id}',
                'sender': self.name,
                'text': text,
                'deleted': False,
                'edited': False,
                'ts': datetime.now().strftime('%H:%M'),
            }
            self.message_log.append(entry)
            self.pending_msgs[client_msg_id] = entry
            self._render_one(entry)
            self._send_safe({
                'cmd': 'send_message',
                'room_id': self.room_id,
                'sender': self.name,
                'ciphertext': ciphertext,
                'client_msg_id': client_msg_id,
            })
        except Exception as exc:
            self._add_system(f'Failed to send: {exc}')

    # ---------- admin / network helpers ----------

    def _send_safe(self, message):
        if not self.connected or not self.sock:
            return
        try:
            self.sock.sendall((json.dumps(message) + '\n').encode())
        except Exception as exc:
            self._add_system(f'Network error: {exc}')

    def _handle_kicked(self, reason):
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        messagebox.showwarning('Removed from room', reason)
        self.show_login()

    def disconnect(self):
        if self.connected and self.sock:
            try:
                self._send_safe({'cmd': 'leave_room', 'room_id': self.room_id, 'name': self.name})
            except Exception:
                pass
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.show_login()

    def on_close(self):
        self.disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    ChatClient(root)
    root.mainloop()


if __name__ == '__main__':
    main()
