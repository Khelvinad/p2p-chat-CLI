import socket
import threading
import json
import time
import sys
import atexit
import base64

# --- KONFIGURASI ---
DNS_PORT = 9000

# Global State
CURRENT_GROUP = 'global'
local_cache = {}

# --- MODUL KEAMANAN (ENKRIPSI) ---
class SimpleSecurity:
    KEY = "JARKOM2025"

    @staticmethod
    def encrypt(raw_text):
        """Mengubah text jadi kode acak (XOR + Base64)"""
        key_len = len(SimpleSecurity.KEY)
        encrypted_chars = []
        for i, char in enumerate(raw_text):
            key_char = SimpleSecurity.KEY[i % key_len]
            encrypted_c = chr(ord(char) ^ ord(key_char))
            encrypted_chars.append(encrypted_c)
        return base64.b64encode("".join(encrypted_chars).encode()).decode()

    @staticmethod
    def decrypt(enc_text):
        """Mengembalikan kode acak jadi text asli"""
        try:
            key_len = len(SimpleSecurity.KEY)
            decoded_str = base64.b64decode(enc_text).decode()
            decrypted_chars = []
            for i, char in enumerate(decoded_str):
                key_char = SimpleSecurity.KEY[i % key_len]
                decrypted_c = chr(ord(char) ^ ord(key_char))
                decrypted_chars.append(decrypted_c)
            return "".join(decrypted_chars)
        except:
            return "[Gagal Dekripsi]"

def get_lan_ip():
    """Mendeteksi IP LAN otomatis"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# --- MODUL DNS (UDP) ---
def dns_register(domain, my_ip, my_port, group_name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = {
            "command": "REGISTER", "domain": domain,
            "ip": my_ip, "port": my_port,
            "group": group_name, "ttl": 300
        }
        sock.sendto(json.dumps(msg).encode(), (DNS_IP, DNS_PORT))
        sock.close()
    except:
        print("[!] Gagal konek ke DNS Server.")

def dns_deregister(domain):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = {"command": "DEREGISTER", "domain": domain}
        sock.sendto(json.dumps(msg).encode(), (DNS_IP, DNS_PORT))
        sock.close()
    except:
        pass

def dns_query(domain):
    # Cek Cache Lokal
    current_time = time.time()
    if domain in local_cache:
        cached = local_cache[domain]
        if current_time < cached['expiry']:
            return cached['ip'], cached['port']
        else:
            del local_cache[domain]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    msg = {"command": "QUERY", "domain": domain}
    try:
        sock.sendto(json.dumps(msg).encode(), (DNS_IP, DNS_PORT))
        data, _ = sock.recvfrom(1024)
        resp = json.loads(data.decode())
        if resp['status'] == 'ok':
            # Simpan ke cache
            local_cache[domain] = {
                'ip': resp['ip'], 'port': resp['port'], 
                'expiry': current_time + 300
            }
            return resp['ip'], resp['port']
        return None, None
    except:
        return None, None
    finally:
        sock.close()

def get_users_from_dns(target_group=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    msg = {"command": "LIST"}
    if target_group: msg['group'] = target_group
    try:
        sock.sendto(json.dumps(msg).encode(), (DNS_IP, DNS_PORT))
        data, _ = sock.recvfrom(4096)
        resp = json.loads(data.decode())
        return resp['users'] if resp['status'] == 'ok' else []
    except:
        return []
    finally:
        sock.close()

# --- MODUL CHAT (TCP) ---
def start_listener(my_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', my_port))
    server.listen(5)
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_incoming, args=(conn,)).start()

def handle_incoming(conn):
    try:
        msg = conn.recv(4096).decode()
        
        # 1. DEKRIPSI PESAN
        if msg.startswith("[SEC]"):
            encrypted_content = msg[5:] 
            msg = SimpleSecurity.decrypt(encrypted_content)

        # 2. TAMPILKAN PESAN
        if ":" in msg:
            sender, content = msg.split(":", 1)
            sys.stdout.write(f"\r\033[K") # Hapus baris input
            
            if "[BROADCAST]" in content:
                clean_msg = content.replace('[BROADCAST]', '')
                print(f"\033[91m[GLOBAL] {sender}: {clean_msg}\033[0m")
            else:
                print(f"[{sender}]: {content}")
            
            sys.stdout.write(f"[{CURRENT_GROUP}] You > ") 
            sys.stdout.flush()
    except:
        pass
    finally:
        conn.close()

def send_direct_msg(target, msg, my_username):
    ip, port = dns_query(target)
    if ip:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((ip, int(port)))
            
            raw_payload = f"{my_username}:{msg}"
            secure_payload = SimpleSecurity.encrypt(raw_payload)
            final_packet = f"[SEC]{secure_payload}"
            
            # DEBUG: Tampilkan ini saat demo untuk bukti enkripsi jalan
            # print(f"\n[DEBUG Encrypt] Asli: {msg} -> Kirim: {final_packet}")

            s.send(final_packet.encode())
            s.close()
        except:
            pass
    else:
        print(f"[!] User '{target}' tidak ditemukan.")

def broadcast_logic(message, my_username, target_group=None):
    users = get_users_from_dns(target_group)
    if my_username in users: users.remove(my_username)
    
    if not users:
        print("[Info] Tidak ada user lain.")
        return

    label = "[BROADCAST] " if target_group is None else ""
    final_msg = f"{label}{message}"
    
    print(f"[*] Mengirim ke {len(users)} user...")
    for user in users:
        send_direct_msg(user, final_msg, my_username)

def switch_group(new_group, username, my_ip, my_port):
    global CURRENT_GROUP
    if new_group == CURRENT_GROUP: return
    
    print(f"[*] Pindah ke room '{new_group}'...")
    dns_deregister(username)
    local_cache.clear()
    CURRENT_GROUP = new_group
    dns_register(username, my_ip, my_port, CURRENT_GROUP)
    print(f"[Success] Welcome to {CURRENT_GROUP}!")

# --- MAIN ---
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 chat.py <IP SERVER> <USERNAME> <PORT>")
        sys.exit()

    DNS_IP = sys.argv[1]
    USERNAME = sys.argv[2]
    MY_PORT = int(sys.argv[3])
    MY_IP = get_lan_ip()

    print("=== JARKOM P2P CHAT (SECURE + GROUPS) ===")
    print(f"User: {USERNAME} | IP: {MY_IP}:{MY_PORT}")
    
    threading.Thread(target=start_listener, args=(MY_PORT,), daemon=True).start()
    dns_register(USERNAME, MY_IP, MY_PORT, CURRENT_GROUP)
    atexit.register(dns_deregister, USERNAME)

    print("-" * 50)
    print(" /join <nama>       : Pindah Room")
    print(" /exitgroup         : Kembali ke Global")
    print("-" * 50)
    print(" @broadcast <pesan> : Kirim ke SEMUA USER (Lintas Group)")
    print(" @nama <pesan>      : Chat Personal")
    print("-" * 50)

    while True:
        try:
            msg = input(f"[{CURRENT_GROUP}] You > ")
            if not msg: continue
            if msg.lower() == 'exit': break
            
            # Commands
            if msg.startswith('/join '):
                switch_group(msg.split(" ", 1)[1].strip(), USERNAME, MY_IP, MY_PORT)
            elif msg.strip() == '/exitgroup':
                switch_group('global', USERNAME, MY_IP, MY_PORT)
            
            # Broadcast Global
            elif msg.startswith('@broadcast '):
                broadcast_logic(msg.split(" ", 1)[1], USERNAME, target_group=None)
            
            # Personal Chat
            elif msg.startswith('@'):
                parts = msg.split(" ", 1)
                if len(parts) > 1:
                    send_direct_msg(parts[0][1:], parts[1], USERNAME)
            
            # Group Chat (Default)
            else:
                if CURRENT_GROUP == 'global':
                    print("[X] Di Global wajib tag nama (@user) atau @broadcast.")
                else:
                    broadcast_logic(msg, USERNAME, target_group=CURRENT_GROUP)
        
        except KeyboardInterrupt:
            break
    
    dns_deregister(USERNAME)
    print("\nBye!")