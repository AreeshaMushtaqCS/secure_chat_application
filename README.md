# SecureChatSystem (Python)

Simple secure chat demo using a central server, SQLite storage, and end-to-end message encryption.

Features
- Create or join rooms.
- Messages are encrypted client-side (Fernet) using a key derived from the room id.
- Server stores ciphertexts in SQLite and forwards encrypted messages to room members.
- Premium Tkinter GUI mode is available behind an environment flag.

Files
- server.py — asyncio-based chat server (stores rooms & messages in SQLite)
- client.py — GUI/CLI client that creates/joins rooms and sends encrypted messages
- db.py — simple SQLite helper
- crypto.py — key derivation and encrypt/decrypt helpers (Fernet)
- requirements.txt — Python requirements

How it works
- Clients derive a symmetric key from the room id using SHA-256.
- Clients encrypt plaintext messages with Fernet and send ciphertext to the server.
- Server stores ciphertexts and broadcasts them to other clients in the same room.
- Recipients decrypt messages locally using the room id.

Security notes
- This demo derives the key solely from the `room id`. In a real system, use a proper
  passphrase-based key derivation (e.g., PBKDF2 / Argon2) and a secret agreed out-of-band.
- Server does not decrypt messages — it only stores and forwards ciphertext.

Setup
1. Create a virtualenv and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the server (keeps SQLite DB `chat.db` in the working dir):

```bash
python server.py
```

3. Open one or more terminals and run the client:

```bash
python client.py
```

To launch the premium GUI client:

```bash
CHAT_GUI=1 python client.py
```

Optional settings:
- `CHAT_HOST` sets the server host, default `127.0.0.1`.
- `CHAT_PORT` sets the server port, default `8888`.
- `CHAT_LOG_FILE` sets the client log file name, default `securechat-client.log`.

Logs
- Server activity is written to `securechat-server.log`.
- Client activity is written to `securechat-client.log`.
- In CLI mode, if you pipe input into the client, it will exit when stdin ends and log `Disconnected from server`; that is expected.

Usage
- In CLI mode, the client prompts for `create` or `join` and for `name` and `room id`.
- In GUI mode, the app opens a premium landing screen with large create/join actions.
- If you join a non-existent room the client offers to create it.
- Type messages and press Enter or click Send. Messages are encrypted before leaving the client.

Next steps / improvements
- Use a stronger KDF with a passphrase instead of raw room ids.
- Add authentication for users and the server.
- Use TLS for transport (the demo uses localhost only).
- Add message history retrieval and pagination.

How to improve this project
- Replace the room-id-derived key with a real secret-based key exchange.
- Add proper user login, room membership rules, and permissions.
- Store message metadata separately from encrypted payloads.
- Add retry logic and reconnect handling in the client.
- Add server-side input validation and rate limiting.
- Add tests for room creation, join flow, encryption, and disconnect handling.
- Add a packaging step so the app can be launched with a single command.
- Add better error banners in the GUI instead of generic dialogs.
- Add a clean shutdown path so sockets close without leaving stale server state.

Feature ideas you can add next
- Message history in the chat window.
- Room member list with online/offline indicators.
- Typing indicators.
- Read receipts.
- File and image sharing.
- Message reactions and replies.
- Voice notes.
- Search inside room history.
- Export chat history to text or JSON.
- Dark/light theme toggle.
- Custom avatars and display colors.
- One-time invite links for rooms.
- Expiring rooms or temporary guest access.
- End-to-end key rotation per room session.
- Encrypted attachments.
- Message edit and delete support.
- Desktop notifications for new messages.
- Mobile-friendly or web client later.

Suggested roadmap
1. Security hardening.
2. Better room and user management.
3. Message history and search.
4. File sharing and notifications.
5. Packaging and deployment.
