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

**Detailed Feature Explanations**

- **Stronger KDF with passphrase**: Replace the room-id-only key derivation with a password/passphrase-based KDF (Argon2 or PBKDF2/scrypt) that uses a per-room salt and adequate work factor to resist brute-force and rainbow-table attacks.

- **Replace room-id-derived key with key exchange**: Implement an authenticated key agreement (e.g., X25519 + signatures or a Signal-style handshake) so clients derive a shared per-room symmetric key without embedding secrets in the room id.

- **End-to-end key rotation per room session**: Periodically or on membership changes, derive a new symmetric key (re-key) and re-encrypt subsequent messages to reduce the window of exposure if a key is compromised.

- **Encrypted attachments**: Encrypt file blobs client-side under the room key (or a per-file key encrypted by the room key). Server stores ciphertext and metadata only, never plaintext attachments.

- **Store message metadata separately from ciphertext**: Keep searchable fields (timestamp, sender id, message id, content-type) in structured columns while storing the encrypted payload separately so you can index and query without exposing contents.

- **Add authentication for users and the server**: Add user accounts or token-based auth (JWT/opaque tokens), password hashing (bcrypt/argon2), and server-side validation to prevent impersonation and misuse.

- **Room membership rules & permissions**: Support roles (owner/moderator/member/guest), ACLs, and invite-only rooms so the server enforces who can read/post/edit messages.

- **One-time invite links / expiring rooms / guest access**: Generate time-limited or single-use invite tokens for secure onboarding and automatic room deletion/archival for temporary rooms.

- **Use TLS for transport**: Protect metadata and mitigate active MITM by wrapping sockets with TLS (`ssl.SSLContext`) and optionally require client certs or token auth for stronger guarantees.

- **Server-side input validation**: Enforce message size limits, valid ID formats, and command whitelists to avoid injection, oversized payloads, and DB abuse.

- **Rate limiting and abuse mitigation**: Apply per-IP/user rate limits, connection caps, and soft-bans to prevent spam and basic DoS attacks.

- **Clean shutdown path**: Implement signal handlers and graceful shutdown to close listeners, notify clients, flush DB writes, and release locks to avoid stale state on restart.

- **Retry logic and reconnect handling**: Client-side exponential backoff reconnects, automatic resync of missed messages on reconnect, and visible connection states in the UI.

- **Message history retrieval and pagination**: Add server endpoints to page history (cursor or offset) with indexed queries so clients load history lazily and efficiently.

- **Read receipts, edits and deletes**: Store receipt and edit/delete events as separate metadata so clients can update UI while server enforces permission checks and retains an audit trail if desired.

- **Typing indicators & presence**: Send ephemeral presence events for typing and online/offline state so GUIs can show live member indicators without persisting these ephemeral events.

- **Room member list with online/offline indicators**: Maintain per-room presence and a member list (avatar, display name, presence) so UIs can show who is in the room and their state.

- **Desktop notifications**: Integrate system notifications for backgrounded clients to surface new messages; add per-room mute/priority controls.

- **File and image sharing, message reactions and replies**: Support encrypted uploads, structured metadata for thumbnails, reactions, reply threading, and a UI to render them without altering original ciphertexts.

- **Voice notes**: Record, compress, encrypt, upload, and stream short audio clips with client playback controls.

- **Search inside room history**: Provide safe search over metadata; for full-text on encrypted content consider client-side indexing or searchable encryption techniques to avoid leaking plaintext to the server.

- **Export chat history**: Allow users to export their decrypted history as plaintext or JSON locally after verification (warn about security implications of plaintext exports).

- **Custom avatars and theming**: Per-user avatars and light/dark theme toggles for better UX and personalization.

- **Mobile-friendly or web client later**: Reuse protocol and crypto primitives to build cross-platform clients (React Native, PWA, or a web client behind HTTPS) for broader access.

- **Add tests and CI**: Unit tests for DB operations, encryption/decryption, and server commands plus integration tests for client-server flows to prevent regressions. Add CI to run tests automatically.

- **Packaging and deployment**: Provide `pyproject.toml`/`setup.cfg` or a single installer script, and systemd/service examples for robust server deployment.

- **Logging, observability, and monitoring**: Structured logs, metrics (Prometheus), and a health endpoint to monitor server status, active rooms, and error rates.

- **Scalability notes**: For larger scale, consider splitting responsibilities (stateless server + Redis/ broker for pub/sub), sharding rooms, and offloading attachments to object storage.

- If you want, I can also add a short "Implementation notes" section with recommended libraries, code snippets, and example API schemas for the highest-priority items.

**Implementation Notes & Examples**

- **Recommended Python libraries**
  - `cryptography` — symmetric encryption primitives, X25519, and high-level Fernet if desired.
  - `argon2-cffi` or `bcrypt` — password/passphrase hashing and KDF helpers (Argon2 preferred for KDF workloads).
  - `pynacl` (PyNaCl) or `cryptography` X25519/ECDH primitives — authenticated key agreement for per-room keys.
  - `aiohttp`, `websockets`, or `FastAPI` + `uvicorn` — for async servers and WebSocket support (choose based on desired API style).
  - `pytest` and `pytest-asyncio` — unit and async integration tests.

- **Key derivation & exchange (high-level example)**
  - Derive keys from a passphrase using Argon2 (client-side) with a random per-room salt stored with the room metadata (salt is not secret). Use the derived seed to create a Fernet key or a symmetric AEAD key.
  - For better security, perform an authenticated X25519 key agreement between clients (or between each client and a room manager) so the symmetric key is never derived from a public room id.

- **Example DB schema (SQLite)**
  - `rooms` table: `id TEXT PRIMARY KEY, name TEXT, salt BLOB, owner_id TEXT, created_at INTEGER, expires_at INTEGER NULLABLE`
  - `messages` table: `id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, sender_id TEXT, ts INTEGER, metadata JSON, ciphertext BLOB, attachment_ref TEXT NULL`
  - Indexes: `CREATE INDEX idx_messages_room_ts ON messages(room_id, ts DESC)` for fast history queries.

- **Socket / API command examples (JSON-over-TCP or WebSocket messages)**
  - Create room: `{"cmd":"create_room","name":"My Room","salt":"BASE64","token":"..."}`
  - Join room: `{"cmd":"join","room_id":"...","token":"...","client_pub":"BASE64"}` (client_pub used for key agreement)
  - Send message: `{"cmd":"message","room_id":"...","payload":"BASE64_CIPHERTEXT","metadata":{...}}`
  - Typing: `{"cmd":"typing","room_id":"...","state":true}` (ephemeral)
  - History request: `{"cmd":"history","room_id":"...","cursor":"CURSOR_OR_TS","limit":50}` → server responds with `messages: [...]` and next cursor.
  - Receipt / edit / delete events use dedicated `cmd` values (e.g., `receipt`, `edit`, `delete`) and reference the target `message_id`.

- **Pagination pattern**
  - Use cursor-based pagination (cursor = timestamp or message id). Server returns a page of messages plus `next_cursor` so clients can load older messages with `cursor=next_cursor`.

- **Attachment flow**
  - Client encrypts attachment with a per-file AES-GCM key; encrypt that key with the room key (or place it in the metadata encrypted under the room key). Upload ciphertext to object store or server and store a pointer in `messages.attachment_ref`.

- **Presence & typing**
  - Presence/typing should be ephemeral and not stored as persistent messages. Use a lightweight pub/sub path for transient events (broadcast to room members only).

- **Auth & tokens**
  - Use short-lived tokens (JWT or opaque tokens) issued after a login step; protect token issuance with correct password hashing (Argon2) and optional 2FA for production.

- **TLS and server deployment**
  - Use `ssl.SSLContext` to wrap sockets for TLS in the server and require `https`/WSS for web clients. For private deployments, you can optionally require client certificates (mTLS).
  - Example systemd service unit (high-level): create a `securechat.service` that runs the server under a dedicated user and restarts on failure.

- **Testing recommendations**
  - Add unit tests for `db.py`, `crypto.py` and message serialization.
  - Add integration tests that spin up a test server and create two clients to verify encryption, storage and broadcast.
  - Use `pytest-asyncio` to test async server handlers and `sqlite` in-memory DB for speed.

- **CI example (GitHub Actions)**
  - A minimal workflow: `checkout`, `setup-python 3.11`, `pip install -r requirements.txt`, `pytest` — run on pushes and PRs.

- **Packaging & run commands**
  - Provide `pyproject.toml` with an entry point so users can install with `pip install .` and run `securechat-server` and `securechat-client` commands.
  - Suggested environment variables: `CHAT_HOST`, `CHAT_PORT`, `CHAT_LOG_FILE`, `CHAT_DB_PATH`, `CHAT_TLS_CERT`, `CHAT_TLS_KEY`.

**Expanded Priorities & Quick Roadmap**

- Phase 0 — Safety & hygiene (days):
  - Add tests, CI, and structured logging. Add graceful shutdown handlers and DB backups.

- Phase 1 — Security (1–2 weeks):
  - Add Argon2-based KDF, replace room-id key derivation, add TLS for transport, and add basic user auth (username/password + tokens).

- Phase 2 — UX & reliability (1–2 weeks):
  - Client reconnect/resume, message history pagination, better GUI error banners, presence and typing indicators.

- Phase 3 — Rich features (2–4 weeks):
  - Attachments (encrypted), reactions/replies, read receipts, message edits/deletes, desktop notifications.

- Phase 4 — Hardening & deployment (2+ weeks):
  - Load testing, metrics, packaging, systemd/unit files, and optional migration to a scaled architecture (broker + stateless servers).

If you'd like, I can now:
- create a `docs/IMPLEMENTATION.md` from this content,
- or implement one of the Phase 1 items (Argon2 KDF + demo code) directly in the repo.
