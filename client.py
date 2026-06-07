import json
import socket
import threading
import hashlib
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

# Simple encryption functions (replace with your crypto.py if needed)
def encrypt(password, text):
    # Simple XOR encryption for demo (replace with real encryption)
    key = hashlib.sha256(password.encode()).digest()
    result = bytearray()
    for i, char in enumerate(text.encode()):
        result.append(char ^ key[i % len(key)])
    return result.hex()

def decrypt(password, ciphertext):
    # Simple XOR decryption for demo
    key = hashlib.sha256(password.encode()).digest()
    cipherbytes = bytes.fromhex(ciphertext)
    result = bytearray()
    for i, byte in enumerate(cipherbytes):
        result.append(byte ^ key[i % len(key)])
    return result.decode()

HOST = '127.0.0.1'
PORT = 8888

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("SecureChat")
        self.root.geometry("900x650")
        self.root.configure(bg='#1e1e1e')
        
        self.sock = None
        self.connected = False
        self.running = False
        self.name = None
        self.room_id = None
        self.password = None
        self.is_admin = False
        
        self.show_login()
    
    def show_login(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        main = tk.Frame(self.root, bg='#1e1e1e')
        main.pack(expand=True, fill='both', padx=50, pady=50)
        
        tk.Label(main, text="SecureChat", font=("Arial", 32, "bold"), 
                bg='#1e1e1e', fg='#4CAF50').pack(pady=20)
        tk.Label(main, text="End-to-End Encrypted Chat", 
                font=("Arial", 12), bg='#1e1e1e', fg='#888').pack(pady=(0, 40))
        
        btn_frame = tk.Frame(main, bg='#1e1e1e')
        btn_frame.pack()
        
        tk.Button(btn_frame, text="🏠 Create New Room", command=self.show_create,
                 font=("Arial", 14), bg='#4CAF50', fg='white', padx=30, pady=10).pack(pady=10)
        tk.Button(btn_frame, text="🔑 Join Existing Room", command=self.show_join,
                 font=("Arial", 14), bg='#2196F3', fg='white', padx=30, pady=10).pack(pady=10)
    
    def show_create(self):
        self.show_dialog("create")
    
    def show_join(self):
        self.show_dialog("join")
    
    def show_dialog(self, mode):
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Room" if mode == "create" else "Join Room")
        dialog.geometry("400x550")
        dialog.configure(bg='#2e2e2e')
        dialog.transient(self.root)
        dialog.grab_set()
        
        y_pos = 20
        
        # Room Name (only for create)
        if mode == "create":
            tk.Label(dialog, text="Room Display Name:", bg='#2e2e2e', fg='white', 
                    font=("Arial", 11)).pack(pady=(20, 5))
            room_name_entry = tk.Entry(dialog, font=("Arial", 11), width=30, bg='#3e3e3e', fg='white')
            room_name_entry.pack(pady=5)
        
        # Room ID
        tk.Label(dialog, text="Room ID (unique identifier):", bg='#2e2e2e', fg='white', 
                font=("Arial", 11)).pack(pady=(10, 5))
        room_id_entry = tk.Entry(dialog, font=("Arial", 11), width=30, bg='#3e3e3e', fg='white')
        room_id_entry.pack(pady=5)
        tk.Label(dialog, text="(Use letters, numbers, or underscores)", bg='#2e2e2e', fg='#888', 
                font=("Arial", 8)).pack()
        
        # Password
        tk.Label(dialog, text="Room Password:", bg='#2e2e2e', fg='white', 
                font=("Arial", 11)).pack(pady=(10, 5))
        password_entry = tk.Entry(dialog, font=("Arial", 11), width=30, bg='#3e3e3e', fg='white', show="•")
        password_entry.pack(pady=5)
        
        # Your Name
        tk.Label(dialog, text="Your Display Name:", bg='#2e2e2e', fg='white', 
                font=("Arial", 11)).pack(pady=(10, 5))
        name_entry = tk.Entry(dialog, font=("Arial", 11), width=30, bg='#3e3e3e', fg='white')
        name_entry.pack(pady=5)
        
        def submit():
            room_id = room_id_entry.get().strip()
            password = password_entry.get()
            name = name_entry.get().strip()
            
            if not room_id or not password or not name:
                messagebox.showerror("Error", "Please fill all fields")
                return
            
            if mode == "create":
                room_name = room_name_entry.get().strip()
                if not room_name:
                    messagebox.showerror("Error", "Please enter a room display name")
                    return
            else:
                room_name = None
            
            dialog.destroy()
            # Connect in a separate thread
            threading.Thread(target=self.connect, args=(mode, name, room_id, room_name, password), daemon=True).start()
            # Show connecting message
            self.show_connecting()
        
        btn_frame = tk.Frame(dialog, bg='#2e2e2e')
        btn_frame.pack(pady=30)
        tk.Button(btn_frame, text="Submit", command=submit,
                 font=("Arial", 11), bg='#4CAF50', fg='white', padx=20).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 font=("Arial", 11), bg='#f44336', fg='white', padx=20).pack(side='left', padx=10)
    
    def show_connecting(self):
        self.connecting_window = tk.Toplevel(self.root)
        self.connecting_window.title("Connecting")
        self.connecting_window.geometry("300x100")
        self.connecting_window.configure(bg='#2e2e2e')
        self.connecting_window.transient(self.root)
        tk.Label(self.connecting_window, text="Connecting to server...", 
                font=("Arial", 12), bg='#2e2e2e', fg='white').pack(expand=True)
    
    def connect(self, mode, name, room_id, room_name, password):
        try:
            # Close connecting window
            self.root.after(0, self.connecting_window.destroy)
            
            print(f"Connecting to {HOST}:{PORT}...")
            
            # Connect to server
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((HOST, PORT))
            self.sock.settimeout(None)
            self.connected = True
            
            self.name = name
            self.room_id = room_id
            self.password = password
            
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if mode == "create":
                # Create room
                create_msg = {
                    'cmd': 'create_room',
                    'name': name,
                    'room_id': room_id,
                    'room_name': room_name,
                    'password_hash': password_hash
                }
                self.sock.send((json.dumps(create_msg) + '\n').encode())
                
                # Get response
                response = self.sock.recv(4096).decode().strip()
                print(f"Create response: {response}")
                
                if not response:
                    raise Exception("No response from server")
                
                result = json.loads(response)
                if result.get('status') != 'ok':
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to create room: {result.get('reason', 'Unknown')}"))
                    self.sock.close()
                    return
                
                print("Room created, now joining...")
                
                # Join the room
                join_msg = {
                    'cmd': 'join_room',
                    'name': name,
                    'room_id': room_id,
                    'password_hash': password_hash
                }
                self.sock.send((json.dumps(join_msg) + '\n').encode())
                
                response = self.sock.recv(4096).decode().strip()
                print(f"Join response: {response}")
                
                result = json.loads(response)
                
                if result.get('status') == 'ok':
                    self.is_admin = True
                    self.root.after(0, self.setup_chat)
                    self.root.after(100, lambda: self.add_message("System", f"✅ Room '{room_name}' created successfully!"))
                    self.root.after(100, lambda: self.add_message("System", f"👑 You are the ADMIN of this room"))
                    self.start_receiver()
                else:
                    error_msg = result.get('reason', 'Unknown error')
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to join room: {error_msg}"))
                    self.sock.close()
                    
            else:  # join mode
                join_msg = {
                    'cmd': 'join_room',
                    'name': name,
                    'room_id': room_id,
                    'password_hash': password_hash
                }
                self.sock.send((json.dumps(join_msg) + '\n').encode())
                
                response = self.sock.recv(4096).decode().strip()
                print(f"Join response: {response}")
                
                result = json.loads(response)
                
                if result.get('status') == 'ok':
                    self.is_admin = False
                    self.root.after(0, self.setup_chat)
                    room_info = result.get('room_info', {})
                    self.root.after(100, lambda: self.add_message("System", f"✅ Joined room: {room_info.get('room_name', room_id)}"))
                    self.start_receiver()
                else:
                    error_msg = result.get('reason', 'Unknown error')
                    if error_msg == 'wrong_password':
                        self.root.after(0, lambda: messagebox.showerror("Error", "Incorrect room password!"))
                    elif error_msg == 'no_room':
                        self.root.after(0, lambda: messagebox.showerror("Error", "Room does not exist!"))
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to join: {error_msg}"))
                    self.sock.close()
                    
        except socket.timeout:
            self.root.after(0, lambda: messagebox.showerror("Error", "Connection timeout. Make sure server is running."))
            if self.sock:
                self.sock.close()
        except ConnectionRefusedError:
            self.root.after(0, lambda: messagebox.showerror("Error", "Cannot connect to server.\nMake sure server.py is running on port 8888"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Connection failed: {e}"))
            if self.sock:
                self.sock.close()
    
    def setup_chat(self):
        # Clear window
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Top bar
        top = tk.Frame(self.root, bg='#2e2e2e', height=60)
        top.pack(fill='x')
        top.pack_propagate(False)
        
        title = f"Room: {self.room_id}"
        if self.is_admin:
            title += " 👑 ADMIN"
        
        tk.Label(top, text=title, font=("Arial", 14, "bold"),
                bg='#2e2e2e', fg='#4CAF50').pack(side='left', padx=20, pady=15)
        tk.Label(top, text=f"User: {self.name}", font=("Arial", 11),
                bg='#2e2e2e', fg='white').pack(side='left', padx=20, pady=15)
        tk.Button(top, text="🚪 Disconnect", command=self.disconnect,
                 font=("Arial", 10), bg='#f44336', fg='white').pack(side='right', padx=20, pady=15)
        
        # Chat area
        self.chat_area = scrolledtext.ScrolledText(self.root, font=("Arial", 11),
                                                    bg='#2e2e2e', fg='white',
                                                    wrap=tk.WORD)
        self.chat_area.pack(fill='both', expand=True, padx=10, pady=10)
        self.chat_area.config(state='disabled')
        
        # Configure colors
        self.chat_area.tag_config("sender", foreground="#4CAF50", font=("Arial", 11, "bold"))
        self.chat_area.tag_config("system", foreground="#FFC107", font=("Arial", 10, "italic"))
        
        # Input area
        input_frame = tk.Frame(self.root, bg='#2e2e2e', height=60)
        input_frame.pack(fill='x')
        input_frame.pack_propagate(False)
        
        self.entry = tk.Entry(input_frame, font=("Arial", 11), bg='#3e3e3e', 
                              fg='white', insertbackground='white')
        self.entry.pack(side='left', fill='x', expand=True, padx=10, pady=15)
        self.entry.bind('<Return>', lambda e: self.send_message())
        
        tk.Button(input_frame, text="Send", command=self.send_message,
                 font=("Arial", 11), bg='#4CAF50', fg='white').pack(side='right', padx=10, pady=15)
    
    def start_receiver(self):
        self.running = True
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()
    
    def receive_messages(self):
        while self.running and self.connected:
            try:
                data = self.sock.recv(4096).decode()
                if not data:
                    break
                
                for line in data.strip().split('\n'):
                    if line:
                        msg = json.loads(line)
                        cmd = msg.get('cmd')
                        
                        if cmd == 'message':
                            sender = msg.get('sender')
                            ciphertext = msg.get('ciphertext', '')
                            if sender != self.name:
                                try:
                                    text = decrypt(self.password, ciphertext)
                                    self.root.after(0, lambda s=sender, t=text: self.add_message(s, t))
                                except:
                                    self.root.after(0, lambda s=sender: self.add_message(s, "[Decryption Failed]"))
                        
                        elif cmd == 'member_joined':
                            username = msg.get('username')
                            if username != self.name:
                                self.root.after(0, lambda u=username: self.add_message("System", f"👋 {u} joined the room"))
                        
                        elif cmd == 'member_left':
                            username = msg.get('username')
                            self.root.after(0, lambda u=username: self.add_message("System", f"👋 {u} left the room"))
                        
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break
    
    def add_message(self, sender, message):
        if not hasattr(self, 'chat_area'):
            return
            
        self.chat_area.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if sender == "System":
            self.chat_area.insert(tk.END, f"*** {message} ***\n", "system")
        else:
            self.chat_area.insert(tk.END, f"[{timestamp}] ", "system")
            self.chat_area.insert(tk.END, f"{sender}: ", "sender")
            self.chat_area.insert(tk.END, f"{message}\n")
        
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)
    
    def send_message(self):
        if not hasattr(self, 'entry') or not self.entry:
            return
            
        message = self.entry.get().strip()
        if not message:
            return
        
        self.entry.delete(0, tk.END)
        
        if not self.connected:
            self.add_message("System", "Not connected!")
            return
        
        try:
            ciphertext = encrypt(self.password, message)
            msg = {
                'cmd': 'send_message',
                'room_id': self.room_id,
                'sender': self.name,
                'ciphertext': ciphertext
            }
            self.sock.send((json.dumps(msg) + '\n').encode())
            self.add_message(self.name, message)
        except Exception as e:
            self.add_message("System", f"Failed to send: {e}")
    
    def disconnect(self):
        self.running = False
        self.connected = False
        
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        
        self.show_login()

def main():
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()

if __name__ == '__main__':
    main()