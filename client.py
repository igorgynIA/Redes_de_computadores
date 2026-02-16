import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

# --- CONFIGURAÇÃO ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEGUNDOS = 3.0

class ChatClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Mini-NET - {MY_VIP} (Fase 2)")
        self.geometry("600x750")

        # Layout Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Área de Chat
        self.text_area = ctk.CTkTextbox(self, state='disabled', corner_radius=10)
        self.text_area.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # 2. Área de Logs (Terminal Style)
        self.log_area = ctk.CTkTextbox(self, height=150, fg_color="#1a1a1a", text_color="#00ff00", corner_radius=10)
        self.log_area.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        # 3. Frame de Entrada
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

        # Widgets de Entrada
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Digite sua mensagem...", height=40)
        self.entry.pack(side="left", padx=(0, 10), fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.iniciar_envio_thread())

        # Botões
        self.btn_emoji = ctk.CTkButton(self.input_frame, text="😀", width=40, height=40, command=self.abrir_seletor_emojis)
        self.btn_emoji.pack(side="left", padx=5)

        self.btn_file = ctk.CTkButton(self.input_frame, text="📁", width=40, height=40, command=self.enviar_arquivo)
        self.btn_file.pack(side="left", padx=5)

        self.btn_env = ctk.CTkButton(self.input_frame, text="Enviar", width=80, height=40, command=self.iniciar_envio_thread)
        self.btn_env.pack(side="left")

        # --- Rede e Estado ---
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 6001)) # Porta sincronizada com Router
        
        self.seq_atual = 0
        self.ack_event = threading.Event()
        self.ack_recebido_seq = -1
        
        threading.Thread(target=self.loop_recebimento, daemon=True).start()

    # --- UI Methods ---
    def log(self, msg, cor=None):
        # CustomTkinter não usa tags de cor linha a linha facilmente, mantendo texto padrão verde do init
        self.log_area.configure(state='normal')
        self.log_area.insert("end", f"> {msg}\n")
        self.log_area.configure(state='disabled')
        self.log_area.see("end")

    def chat_print(self, msg):
        self.text_area.configure(state='normal')
        self.text_area.insert("end", msg + "\n")
        self.text_area.configure(state='disabled')
        self.text_area.see("end")

    def abrir_seletor_emojis(self):
        # Pop-up moderno para Emojis
        top = ctk.CTkToplevel(self)
        top.title("Emojis")
        top.geometry("250x160")
        top.attributes("-topmost", True)
        
        emojis = ["😀", "😂", "🚀", "🔥", "👍", "🤖", "💻", "✅"]
        for i, emoji in enumerate(emojis):
            btn = ctk.CTkButton(top, text=emoji, width=50, command=lambda e=emoji: self.inserir_emoji(e, top))
            btn.grid(row=i//4, column=i%4, padx=5, pady=5)

    def inserir_emoji(self, emoji, window):
        self.entry.insert("end", emoji)
        window.destroy()
        self.entry.focus_set()

    # --- Network Logic (Inalterada) ---
    def construir_pilha(self, conteudo, tipo):
        app_data = {
            "type": tipo,
            "sender": MY_VIP,
            "message": conteudo,
            "timestamp": time.time()
        }
        seg = Segmento(seq_num=self.seq_atual, is_ack=False, payload=app_data)
        pkt = Pacote(src_vip=MY_VIP, dst_vip=DEST_VIP, ttl=5, segmento_dict=seg.to_dict())
        frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=pkt.to_dict())
        return frame.serializar()

    def iniciar_envio_thread(self):
        if self.btn_env._state == "disabled": return
        texto = self.entry.get()
        if not texto: return
        
        self.btn_env.configure(state="disabled")
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
        bytes_envio = self.construir_pilha(conteudo, tipo)
        tentativa = 1
        
        self.log(f"--- Iniciando envio SEQ {self.seq_atual} ---")
        
        while True:
            self.log(f"Tentativa {tentativa}: Enviando...")
            enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
            
            self.ack_event.clear()
            ack_chegou = self.ack_event.wait(timeout=TIMEOUT_SEGUNDOS)
            
            if ack_chegou and self.ack_recebido_seq == self.seq_atual:
                self.log(f"ACK {self.seq_atual} recebido com sucesso!")
                self.seq_atual = 1 - self.seq_atual
                break
            else:
                self.log("TIMEOUT ou ACK incorreto. Retransmitindo...")
                tentativa += 1

        self.btn_env.configure(state="normal")

    def loop_recebimento(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                quadro, integro = Quadro.deserializar(data)
                
                if not integro:
                    self.log("Pacote corrompido (CRC). Ignorado.")
                    continue
                
                pacote = quadro['data']
                segmento = pacote['data']
                
                if segmento['is_ack']:
                    seq = segmento['seq_num']
                    self.log(f"Recebido ACK {seq}")
                    self.ack_recebido_seq = seq
                    self.ack_event.set()
                    
            except Exception as e:
                print(e)

if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()