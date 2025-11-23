import socket
import json
import time
import threading

# --- KONFIGURASI ---
DNS_PORT = 9000 
RECORDS_FILE = 'dns_records.json'
DEFAULT_TTL = 300  # 5 menit

records = {}

def load_records():
    global records
    try:
        with open(RECORDS_FILE, 'r') as f:
            records = json.load(f)
    except:
        records = {}

def save_records():
    with open(RECORDS_FILE, 'w') as f:
        json.dump(records, f, indent=4)

def cleanup_expired_ttl():
    """Background Process: Menghapus user yang sudah offline/timeout"""
    while True:
        time.sleep(10)
        current_time = time.time()
        expired = []
        for domain, data in records.items():
            if current_time > data['timestamp'] + data['ttl']:
                expired.append(domain)
        
        if expired:
            for domain in expired:
                del records[domain]
            save_records()
            print(f"[TTL] Menghapus user offline: {expired}")

def handle_dns_request(sock):
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            request = json.loads(data.decode())
            command = request.get('command')
            response = {"status": "error", "message": "Unknown command"}

            current_time = time.time()

            # --- 1. REGISTER ---
            if command == 'REGISTER':
                domain = request.get('domain')
                records[domain] = {
                    "ip": request.get('ip'),
                    "port": request.get('port'),
                    "group": request.get('group', 'global'),
                    "ttl": request.get('ttl', DEFAULT_TTL),
                    "timestamp": current_time
                }
                save_records()
                print(f"[REG] {domain} masuk group '{records[domain]['group']}'")
                response = {"status": "ok", "message": "Registered"}

            # --- 2. QUERY ---
            elif command == 'QUERY':
                domain = request.get('domain')
                if domain in records:
                    rec = records[domain]
                    if current_time <= rec['timestamp'] + rec['ttl']:
                        response = {
                            "status": "ok",
                            "ip": rec['ip'],
                            "port": rec['port'],
                            "ttl_remaining": int((rec['timestamp'] + rec['ttl']) - current_time)
                        }
                    else:
                        del records[domain]
                        response = {"status": "error", "message": "Expired"}
                else:
                    response = {"status": "error", "message": "Not Found"}

            # --- 3. DEREGISTER ---
            elif command == 'DEREGISTER':
                domain = request.get('domain')
                if domain in records:
                    del records[domain]
                    save_records()
                    print(f"[DEL] {domain} logout")
                response = {"status": "ok", "message": "Deregistered"}

            # --- 4. LIST (Untuk Broadcast/Group) ---
            elif command == 'LIST':
                target_group = request.get('group')
                online_users = []
                for domain, data in records.items():
                    if current_time <= data['timestamp'] + data['ttl']:
                        # Jika group None, ambil semua (untuk broadcast global)
                        # Jika group ada isinya, filter berdasarkan group itu
                        if target_group is None or data.get('group') == target_group:
                            online_users.append(domain)
                
                response = {"status": "ok", "users": online_users}

            sock.sendto(json.dumps(response).encode(), addr)

        except Exception as e:
            print(f"[ERR] {e}")

def start_server():
    load_records()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind(('0.0.0.0', DNS_PORT))
        print(f"=== DNS SERVER BERJALAN (UDP Port {DNS_PORT}) ===")
        print("Menunggu request...")
        
        threading.Thread(target=cleanup_expired_ttl, daemon=True).start()
        handle_dns_request(sock)
    except OSError:
        print(f"[FATAL] Port {DNS_PORT} sedang dipakai. Coba matikan python lama atau ganti port.")

if __name__ == "__main__":
    start_server()