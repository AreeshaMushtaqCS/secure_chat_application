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
