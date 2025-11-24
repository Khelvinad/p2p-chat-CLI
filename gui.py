import customtkinter as ctk
from chat import ChatCore
import sys
from tkinter import messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ChatGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("P2P Chat (Smart UI)")
        self.geometry("750x650")
        self.backend = None

        # --- LOGIN FRAME ---
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=50, padx=50, fill="both", expand=True)

        ctk.CTkLabel(self.login_frame, text="Login Jarkom P2P", font=("Arial", 24, "bold")).pack(pady=30)
        
        self.e_ip = ctk.CTkEntry(self.login_frame, placeholder_text="IP DNS Server", width=300, height=40)
        self.e_ip.pack(pady=10)
        self.e_ip.insert(0, "192.168.1.X") # Sesuaikan default

        self.e_user = ctk.CTkEntry(self.login_frame, placeholder_text="Username", width=300, height=40)
        self.e_user.pack(pady=10)

        self.e_port = ctk.CTkEntry(self.login_frame, placeholder_text="Port (8001-8005)", width=300, height=40)
        self.e_port.pack(pady=10)

        self.btn_connect = ctk.CTkButton(self.login_frame, text="Connect & Validate", command=self.attempt_login, width=300, height=40, fg_color="#2CC985", hover_color="#229A65")
        self.btn_connect.pack(pady=30)

        # --- CHAT FRAME (Hidden Awalnya) ---
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        # 1. Header
        self.header_frame = ctk.CTkFrame(self.chat_frame, height=60, fg_color="#1a1a1a", corner_radius=0)
        self.header_frame.pack(fill="x")
        
        self.lbl_room = ctk.CTkLabel(self.header_frame, text="Room: global", font=("Arial", 16, "bold"), text_color="white")
        self.lbl_room.pack(side="left", padx=20)
        
        # Tombol Kanan (Switch & Exit)
        self.btn_exit_group = ctk.CTkButton(self.header_frame, text="Exit Group", width=80, fg_color="#C0392B", hover_color="#922B21", command=self.do_exit_group)
        self.btn_exit_group.pack(side="right", padx=(5, 20))
        
        self.btn_switch = ctk.CTkButton(self.header_frame, text="Pindah Room", width=100, fg_color="#444", hover_color="#333", command=self.switch_room_dialog)
        self.btn_switch.pack(side="right", padx=5)

        # 2. Area Chat (Scrollable Frame)
        self.scroll_chat = ctk.CTkScrollableFrame(self.chat_frame, fg_color="transparent")
        self.scroll_chat.pack(pady=5, padx=0, fill="both", expand=True)

        # 3. Area Kontrol
        self.ctrl_frame = ctk.CTkFrame(self.chat_frame, fg_color="#2b2b2b", height=50)
        self.ctrl_frame.pack(fill="x", padx=0, pady=0)

        self.combo_mode = ctk.CTkComboBox(self.ctrl_frame, values=["Broadcast", "Private", "Group"], command=self.on_mode_change, width=110)
        self.combo_mode.pack(side="left", padx=10, pady=10)

        self.e_target = ctk.CTkEntry(self.ctrl_frame, placeholder_text="Target...", width=120)
        # Default hidden

        self.e_msg = ctk.CTkEntry(self.ctrl_frame, placeholder_text="", height=40)
        self.e_msg.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.e_msg.bind("<Return>", self.send_msg)
        
        self.btn_send = ctk.CTkButton(self.ctrl_frame, text="➤", width=50, height=40, command=self.send_msg)
        self.btn_send.pack(side="right", padx=10, pady=10)

    # --- LOGIC VALIDASI ---
    def attempt_login(self):
        ip = self.e_ip.get()
        user = self.e_user.get()
        port = self.e_port.get()

        if not ip or not user or not port:
            messagebox.showwarning("Input Error", "Semua field harus diisi!")
            return

        # Disable tombol biar ga dipencet 2x
        self.btn_connect.configure(state="disabled", text="Checking...")
        self.update() # Force update UI

        # Inisialisasi Backend sementara untuk cek validasi
        temp_backend = ChatCore(ip, 9000, user, port, None)
        is_ok, msg = temp_backend.validate_login()

        if is_ok:
            # Lanjut Masuk App
            self.backend = temp_backend
            self.backend.output_callback = self.update_display # Attach UI callback
            self.backend.start() # Start real connection
            
            self.login_frame.pack_forget()
            self.chat_frame.pack(fill="both", expand=True)
            self.protocol("WM_DELETE_WINDOW", self.on_close)
        else:
            # Munculin Popup Error
            messagebox.showerror("Connection Failed", msg)
            self.btn_connect.configure(state="normal", text="Connect & Validate")

    def on_mode_change(self, choice):
        if choice == "Private":
            self.e_target.pack(side="left", padx=5, before=self.e_msg)
            self.e_msg.configure(placeholder_text="")
        else:
            self.e_target.pack_forget()
            ph = "" if choice == "Broadcast" else ""z
            self.e_msg.configure(placeholder_text=ph)

    def add_bubble(self, sender, message, is_me, is_system=False, context_label=None):
        row_frame = ctk.CTkFrame(self.scroll_chat, fg_color="transparent")
        row_frame.pack(fill="x", pady=5, padx=10)

        if is_system:
            ctk.CTkLabel(row_frame, text=message, font=("Arial", 11), text_color="gray").pack(anchor="center")
            return

        if is_me:
            bubble_color, text_color, anchor = "#3B3B3B", "white", "e"
            sender_text = "You"
        else:
            bubble_color, text_color, anchor = "#1F6AA5", "white", "w"
            sender_text = sender

        content_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        content_frame.pack(anchor=anchor)

        # Label Pengirim + Konteks (misal: "Alice (Private)")
        header_text = sender_text
        if context_label:
            header_text += f" {context_label}"
            
        if not is_me or context_label: # Tampilkan label 'You' juga kalau ada konteks (misal You (Private))
            lbl_color = "#FFD700" if "Private" in (context_label or "") else "gray"
            ctk.CTkLabel(content_frame, text=header_text, font=("Arial", 10, "bold"), text_color=lbl_color).pack(anchor="w", padx=5)

        ctk.CTkLabel(
            content_frame, text=message, fg_color=bubble_color, text_color=text_color,
            corner_radius=15, font=("Arial", 14), wraplength=350, padx=15, pady=10, justify="left"
        ).pack(anchor=anchor)

        self.after(10, lambda: self.scroll_chat._parent_canvas.yview_moveto(1.0))

    def update_display(self, raw_message):
        clean_msg = raw_message.replace("\033[91m", "").replace("\033[0m", "")
        
        # Parsing Pesan System
        if any(x in clean_msg for x in ["[Success]", "[!]", "[*]", "Welcome to", "[Info]"]):
            if "Welcome to" in clean_msg:
                new_room = clean_msg.split("Welcome to ")[1].replace("!", "").strip()
                self.lbl_room.configure(text=f"Room: {new_room}")
                # Tombol exit group hanya aktif kalau bukan global (opsional visual)
                state = "disabled" if new_room == "global" else "normal"
                self.btn_exit_group.configure(state=state)

            self.add_bubble("System", clean_msg, False, is_system=True)
            return

        # Parsing Pesan Chat (Dengan Tag Baru)
        if ":" in clean_msg:
            try:
                # Format: [Sender]: Message
                # Format: [Sender]: !!TAG!! Message
                
                parts = clean_msg.split("]: ", 1)
                sender = parts[0].replace("[", "").strip()
                content = parts[1].strip()
                
                context = None
                
                # 1. Deteksi Tag Private
                if "!!PRIV!!" in content:
                    content = content.replace("!!PRIV!!", "").strip()
                    context = "(Private)"
                    # Handle Sender nama khusus dari log lokal
                    if ">" in content and "<" in content and sender == "Me":
                        # Format lokal: >Target< Pesan
                        target_name = content.split("<")[0].replace(">", "").strip()
                        content = content.split("<")[1].strip()
                        context = f"(Private to {target_name})"

                # 2. Deteksi Tag Group
                elif "!!GRP:" in content:
                    # Format: !!GRP:NamaGroup!! Pesan
                    grp_part = content.split("!!")[1] # GRP:NamaGroup
                    grp_name = grp_part.split(":")[1]
                    content = content.split("!!", 2)[2].strip()
                    context = f"(Group: {grp_name})"

                # 3. Deteksi Broadcast
                elif "[BROADCAST]" in content or "GLOBAL" in sender:
                    content = content.replace("[BROADCAST]", "").strip()
                    sender = sender.replace("[GLOBAL]", "").replace("[", "").strip()
                    context = "(GLOBAL)"

                is_me = (sender == "Me" or sender == self.e_user.get())
                self.add_bubble(sender, content, is_me, context_label=context)
                
            except:
                self.add_bubble("System", clean_msg, False, is_system=True)

    def do_exit_group(self):
        self.backend.process_input("/exitgroup")

    def switch_room_dialog(self):
        dialog = ctk.CTkInputDialog(text="Masukkan Nama Room Baru:", title="Pindah Room")
        new_room = dialog.get_input()
        if new_room: self.backend.process_input(f"/join {new_room}")

    def send_msg(self, event=None):
        msg = self.e_msg.get()
        if not msg: return
        mode = self.combo_mode.get()
        
        cmd = msg
        if mode == "Private":
            target = self.e_target.get()
            if not target: return
            cmd = f"@{target} {msg}"
        elif mode == "Broadcast":
            cmd = f"@broadcast {msg}"
            
        self.backend.process_input(cmd)
        self.e_msg.delete(0, "end")

    def on_close(self):
        if self.backend: self.backend.stop()
        self.destroy()
        sys.exit()

if __name__ == "__main__":
    app = ChatGUI()
    app.mainloop()