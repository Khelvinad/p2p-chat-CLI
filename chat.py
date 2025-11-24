import socket
import threading
import json
import time
import sys
import atexit
import base64

class SimpleSecurity:
    KEY = "JARKOM2025"

    @staticmethod
    def encrypt(raw_text):
        try:
            key_len = len(SimpleSecurity.KEY)
            encrypted_chars = []
            for i, char in enumerate(raw_text):
                key_char = SimpleSecurity.KEY[i % key_len]
                encrypted_c = chr(ord(char) ^ ord(key_char))
                encrypted_chars.append(encrypted_c)
            return base64.b64encode("".join(encrypted_chars).encode()).decode()
        except: return raw_text

    @staticmethod
    def decrypt(enc_text):
        try:
            key_len = len(SimpleSecurity.KEY)
            decoded_str = base64.b64decode(enc_text).decode()
            decrypted_chars = []
            for i, char in enumerate(decoded_str):
                key_char = SimpleSecurity.KEY[i % key_len]
                decrypted_c = chr(ord(char) ^ ord(key_char))
                decrypted_chars.append(decrypted_c)
            return "".join(decrypted_chars)
        except: return "[Gagal Dekripsi]"

class ChatCore:
    def __init__(self, dns_ip, dns_port, username, my_port, output_callback=None):
        self.dns_ip = dns_ip
        self.dns_port = int(dns_port)
        self.username = username
        self.my_port = int(my_port)
        self.output_callback = output_callback
        self.current_group = 'global'
        self.local_cache = {}
        self.running = False

    def log(self, message):
        if self.output_callback: self.output_callback(message)
        else: print(message)

    def validate_login(self):
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.bind(('0.0.0.0', self.my_port))
            test_sock.close()
        except OSError:
            return False, f"Port {self.my_port} sudah digunakan aplikasi lain!"

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        try:
            msg = {"command": "QUERY", "domain": self.username}
            sock.sendto(json.dumps(msg).encode(), (self.dns_ip, self.dns_port))
            data, _ = sock.recvfrom(1024)
            resp = json.loads(data.decode())
            
            if resp['status'] == 'ok':
                return False, f"Username '{self.username}' sudah dipakai orang lain!"
            else:
                return True, "OK"
        except socket.timeout:
            return False, f"DNS Server ({self.dns_ip}) tidak merespon/down!"
        except Exception as e:
            return False, f"Error Jaringan: {e}"
        finally:
            sock.close()

    def get_lan_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            IP = s.getsockname()[0]
        except: IP = '127.0.0.1'
        finally: s.close()
        return IP

    def start(self):
        self.running = True
        self.my_ip = self.get_lan_ip()
        
        t = threading.Thread(target=self.start_listener, daemon=True)
        t.start()
        
        self.dns_register(self.username, self.my_ip, self.my_port, self.current_group)
        atexit.register(lambda: self.dns_deregister(self.username))
        
        self.log(f"[*] Connected to DNS. Welcome {self.username}!")
        self.log(f"Welcome to {self.current_group}")

    def stop(self):
        self.running = False
        self.dns_deregister(self.username)

    def dns_register(self, domain, my_ip, my_port, group_name):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = {"command": "REGISTER", "domain": domain, "ip": my_ip, "port": my_port, "group": group_name, "ttl": 300}
            sock.sendto(json.dumps(msg).encode(), (self.dns_ip, self.dns_port))
            sock.close()
        except: pass

    def dns_deregister(self, domain):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = {"command": "DEREGISTER", "domain": domain}
            sock.sendto(json.dumps(msg).encode(), (self.dns_ip, self.dns_port))
            sock.close()
        except: pass

    def dns_query(self, domain):
        curr = time.time()
        if domain in self.local_cache:
            cached = self.local_cache[domain]
            if curr < cached['expiry']: return cached['ip'], cached['port']
            else: del self.local_cache[domain]

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        try:
            sock.sendto(json.dumps({"command": "QUERY", "domain": domain}).encode(), (self.dns_ip, self.dns_port))
            data, _ = sock.recvfrom(1024)
            resp = json.loads(data.decode())
            if resp['status'] == 'ok':
                self.local_cache[domain] = {'ip': resp['ip'], 'port': resp['port'], 'expiry': curr + 300}
                return resp['ip'], resp['port']
            return None, None
        except: return None, None
        finally: sock.close()

    def get_users_from_dns(self, target_group=None):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        msg = {"command": "LIST"}
        if target_group: msg['group'] = target_group
        try:
            sock.sendto(json.dumps(msg).encode(), (self.dns_ip, self.dns_port))
            data, _ = sock.recvfrom(4096)
            resp = json.loads(data.decode())
            return resp['users'] if resp['status'] == 'ok' else []
        except: return []
        finally: sock.close()

    def start_listener(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('0.0.0.0', self.my_port))
            server.listen(5)
            while self.running:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_incoming, args=(conn,)).start()
        except: pass

    def handle_incoming(self, conn):
        try:
            msg = conn.recv(4096).decode()
            if msg.startswith("[SEC]"):
                msg = SimpleSecurity.decrypt(msg[5:])

            if ":" in msg:
                sender, content = msg.split(":", 1)
                self.log(f"[{sender}]: {content}")
        except: pass
        finally: conn.close()

    def send_direct_msg(self, target, msg):
        ip, port = self.dns_query(target)
        if ip:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect((ip, int(port)))
                
                payload = f"{self.username}:{msg}"
                secure = SimpleSecurity.encrypt(payload)
                s.send(f"[SEC]{secure}".encode())
                s.close()
                return True
            except: return False
        return False

    def broadcast_logic(self, message, target_group=None):
        users = self.get_users_from_dns(target_group)
        if self.username in users: users.remove(self.username)
        if not users:
            self.log("[Info] Tidak ada user lain.")
            return
        
        context_tag = ""
        if target_group is None: 
            context_tag = "[BROADCAST] "
        else:
            context_tag = f"!!GRP:{target_group}!! "

        final_msg = f"{context_tag}{message}"
        
        count = 0
        for user in users:
            if self.send_direct_msg(user, final_msg): count += 1
        
        return count

    def switch_group(self, new_group):
        if new_group == self.current_group: return
        self.log(f"[*] Switching to room '{new_group}'...")
        self.dns_deregister(self.username)
        self.local_cache.clear()
        self.current_group = new_group
        self.dns_register(self.username, self.my_ip, self.my_port, self.current_group)
        self.log(f"[Success] Welcome to {self.current_group}!")

    def process_input(self, msg):
        if not msg: return
        
        if msg.lower() == 'exit':
            self.stop()
            return

        if msg.startswith('/join'):
            try: self.switch_group(msg.split(" ", 1)[1].strip())
            except: pass
        elif msg == '/exitgroup':
            self.switch_group('global')
        
        elif msg.startswith('@broadcast '):
            clean = msg.split(" ", 1)[1]
            self.broadcast_logic(clean, target_group=None)
            self.log(f"[Me]: [BROADCAST] {clean}")
            
        elif msg.startswith('@'):
            try:
                parts = msg.split(" ", 1)
                target = parts[0][1:]
                clean_msg = parts[1]
                
                final_msg = f"!!PRIV!! {clean_msg}"
                
                if self.send_direct_msg(target, final_msg):
                    self.log(f"[Me]: !!PRIV!! >{target}< {clean_msg}")
                else:
                    self.log(f"[!] Gagal kirim ke {target} (Offline/Unknown)")
            except: self.log("[!] Format: @user pesan")
            
        else:
            if self.current_group == 'global':
                self.log("[X] Global Lobby: Silahkan masuk ke group atau pilih chat broadcast/private!")
            else:
                self.broadcast_logic(msg, target_group=self.current_group)
                self.log(f"[Me]: !!GRP:{self.current_group}!! {msg}")