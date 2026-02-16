import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

# Configurações de Aparência
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEGUNDOS = 3.0

class ChatClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Mini-NET - {MY_VIP}")
        self.geometry("600x700")

        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Área de Chat
        self.text_area = ctk.CTkTextbox(self, state='disabled', corner_radius=10)
        self.text_area.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Logs do Protocolo (Terminal Interno)
        self.log_area = ctk.CTkTextbox(self, height=150, fg_color="#1a1a1a", text_color="#00ff00", corner_radius=10)
        self.log_area.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        # Frame de Entrada
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Digite sua mensagem...", width=350)
        self.entry.pack(side="left", padx=(0, 10), fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.iniciar_envio_thread())

        self.btn_emoji = ctk.CTkButton(self.input_frame, text="😀", width=40, command=self.abrir_seletor_emojis)
        self.btn_emoji.pack(side="left", padx=5)

        self.btn_file = ctk.CTkButton(self.input_frame, text="📁", width=40, command=self.enviar_arquivo)
        self.btn_file.pack(side="left", padx=5)

        self.btn_send = ctk.CTkButton(self.input_frame, text="Enviar", command=self.iniciar_envio_thread)
        self.btn_send.pack(side="left")

        # Rede e Estado
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 6001))
        self.seq_atual = 0
        self.ack_event = threading.Event()
        self.ack_recebido_seq = -1
        
        threading.Thread(target=self.loop_recebimento, daemon=True).start()

    def log(self, msg):
        self.log_area.configure(state='normal')
        self.log_area.insert("end", f"> {msg}\n")
        self.log_area.configure(state='disabled')
        self.log_area.see("end")

    def chat_print(self, msg):
        self.text_area.configure(state='normal')
        self.text_area.insert("end", f"{msg}\n")
        self.text_area.configure(state='disabled')
        self.text_area.see("end")

    def abrir_seletor_emojis(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Emojis")
        pop.geometry("250x150")
        pop.attributes("-topmost", True)
        
        emojis = ["😀", "😂", "🚀", "🔥", "👍", "🤖", "💻", "✅"]
        for i, emoji in enumerate(emojis):
            btn = ctk.CTkButton(pop, text=emoji, width=40, command=lambda e=emoji: self.inserir_emoji(e, pop))
            btn.grid(row=i//4, column=i%4, padx=5, pady=5)

    def inserir_emoji(self, emoji, pop):
        self.entry.insert("end", emoji)
        pop.destroy()

    def iniciar_envio_thread(self):
        texto = self.entry.get()
        if not texto: return
        self.entry.delete(0, "end")
        self.chat_print(f"Você: {texto}")
        threading.Thread(target=self.enviar_confiavel, args=(texto, "text")).start()

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if path:
            nome = path.split('/')[-1]
            self.chat_print(f"Enviando: {nome}")
            threading.Thread(target=self.enviar_confiavel, args=(nome, "file")).start()

    def enviar_confiavel(self, conteudo, tipo):
        # Lógica Stop-and-Wait (Fase 2)
        app_data = {"type": tipo, "sender": MY_VIP, "message": conteudo, "timestamp": time.time()}
        seg = Segmento(seq_num=self.seq_atual, is_ack=False, payload=app_data)
        pkt = Pacote(src_vip=MY_VIP, dst_vip=DEST_VIP, ttl=5, segmento_dict=seg.to_dict())
        frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=pkt.to_dict())
        bytes_envio = frame.serializar()

        while True:
            self.log(f"Enviando SEQ {self.seq_atual}...")
            enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
            self.ack_event.clear()
            if self.ack_event.wait(timeout=TIMEOUT_SEGUNDOS) and self.ack_recebido_seq == self.seq_atual:
                self.log(f"ACK {self.seq_atual} OK")
                self.seq_atual = 1 - self.seq_atual
                break
            self.log("Retransmitindo...")

    def loop_recebimento(self):
        while True:
            data, _ = self.sock.recvfrom(4096)
            q, integro = Quadro.deserializar(data)
            if integro:
                seg = q['data']['data']
                if seg['is_ack']:
                    self.ack_recebido_seq = seg['seq_num']
                    self.ack_event.set()

if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()