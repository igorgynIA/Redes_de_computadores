import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
import base64
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEGUNDOS = 4.0 # Ligeiramente maior para dar tempo à janela

class ChatClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Mini-NET - {MY_VIP} (Go-Back-N)")
        self.geometry("650x750")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.text_area = ctk.CTkTextbox(self, state='disabled', corner_radius=10, font=("Roboto", 14))
        self.text_area.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.text_area._textbox.tag_config("direita", justify="right", foreground="gray", spacing3=5)
        self.text_area._textbox.tag_config("msg_user", foreground="white")

        self.log_area = ctk.CTkTextbox(self, height=200, fg_color="#1a1a1a", font=("Consolas", 12), corner_radius=10)
        self.log_area.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.log_area._textbox.tag_config("vermelho", foreground="#ff5555")
        self.log_area._textbox.tag_config("verde",    foreground="#55ff55")
        self.log_area._textbox.tag_config("amarelo",  foreground="#ffff55")
        self.log_area._textbox.tag_config("ciano",    foreground="#55ffff")

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Digite sua mensagem...", height=40)
        self.entry.pack(side="left", padx=(0, 10), fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.iniciar_envio())

        self.btn_emoji = ctk.CTkButton(self.input_frame, text="😀", width=40, height=40, command=self.abrir_seletor_emojis)
        self.btn_emoji.pack(side="left", padx=5)

        self.btn_file = ctk.CTkButton(self.input_frame, text="📁", width=40, height=40, command=self.enviar_arquivo)
        self.btn_file.pack(side="left", padx=5)

        self.btn_env = ctk.CTkButton(self.input_frame, text="Enviar", width=80, height=40, command=self.iniciar_envio)
        self.btn_env.pack(side="left")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 6001))
        
        # --- Variáveis de Estado do Go-Back-N ---
        self.base = 0           # Pacote mais antigo não confirmado
        self.next_seq_num = 0   # Próximo número de sequência a ser usado
        self.pacotes_enviados = {} # Buffer da janela: {seq_num: bytes_envio}
        self.tempo_envio_base = 0  # Timer único para a 'base'
        self.lock = threading.Lock()
        
        threading.Thread(target=self.loop_recebimento, daemon=True).start()
        threading.Thread(target=self.monitor_timeouts, daemon=True).start()

    def log(self, msg, tag=None):
        self.log_area.configure(state='normal')
        self.log_area.insert("end", f"> {msg}\n", tag)
        self.log_area.configure(state='disabled')
        self.log_area.see("end")

    def chat_print(self, msg, align="left"):
        horario = time.strftime('%H:%M')
        self.text_area.configure(state='normal')
        self.text_area.insert("end", f"[{horario}] {msg}\n")
        self.text_area.configure(state='disabled')
        self.text_area.see("end")

    def abrir_seletor_emojis(self):
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

    def atualizar_status_visual(self, status_antigo, status_novo):
        try:
            self.text_area.configure(state='normal')
            posicao = self.text_area._textbox.search(status_antigo, "end-1c", "end-15l", backwards=True)
            if posicao:
                fim_posicao = f"{posicao}+{len(status_antigo)}c"
                self.text_area._textbox.delete(posicao, fim_posicao)
                self.text_area._textbox.insert(posicao, status_novo, "direita")
            self.text_area.configure(state='disabled')
            self.text_area.see("end")
        except:
            pass

    def construir_pilha(self, conteudo, tipo, seq, filename=None):
        app_data = {
            "type": tipo,
            "sender": MY_VIP,
            "message": conteudo,
            "filename": filename,
            "timestamp": time.time()
        }
        seg = Segmento(seq_num=seq, is_ack=False, payload=app_data)
        pkt = Pacote(src_vip=MY_VIP, dst_vip=DEST_VIP, ttl=5, segmento_dict=seg.to_dict())
        frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=pkt.to_dict())
        return frame.serializar()

    def iniciar_envio(self):
        texto = self.entry.get()
        if not texto: return
        self.entry.delete(0, "end")
        
        horario = time.strftime('%H:%M')
        self.text_area.configure(state='normal')
        self.text_area.insert("end", f"Você: {texto}\n", "msg_user")
        self.text_area._textbox.insert("end", f"{horario} 🕒\n", "direita")
        self.text_area.configure(state='disabled')
        self.text_area.see("end")
        
        threading.Thread(target=self.enviar_dados, args=(texto, "text")).start()

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if path:
            nome = path.split('/')[-1]
            try:
                with open(path, 'rb') as f:
                    dados_brutos = f.read()
                if len(dados_brutos) > 50000:
                    self.log("ERRO: Arquivo >50kb", "vermelho")
                    return
                dados_b64 = base64.b64encode(dados_brutos).decode('utf-8')

                horario = time.strftime('%H:%M')
                self.text_area.configure(state='normal')
                self.text_area.insert("end", f"Você: 📁 {nome}\n", "msg_user")
                self.text_area._textbox.insert("end", f"{horario} 🕒\n", "direita")
                self.text_area.configure(state='disabled')
                self.text_area.see("end")

                threading.Thread(target=self.enviar_dados, args=(dados_b64, "file", nome)).start()
            except Exception as e:
                self.log(f"Erro ao ler arquivo: {e}", "vermelho")

    def enviar_dados(self, conteudo, tipo, filename=None):
        with self.lock:
            seq = self.next_seq_num
            bytes_envio = self.construir_pilha(conteudo, tipo, seq, filename)
            self.pacotes_enviados[seq] = bytes_envio
            
            # Se for o primeiro da janela, inicia o timer
            if self.base == self.next_seq_num:
                self.tempo_envio_base = time.time()
                
            self.next_seq_num += 1

        self.log(f"Enviando SEQ {seq}...", "amarelo")
        enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
        self.atualizar_status_visual("🕒", "✓")

    def monitor_timeouts(self):
        """No GBN, o timeout de 1 pacote força a retransmissão de toda a janela"""
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.base < self.next_seq_num: # Há pacotes em trânsito
                    if time.time() - self.tempo_envio_base > TIMEOUT_SEGUNDOS:
                        self.log(f"TIMEOUT na base {self.base}. Retransmitindo do {self.base} ao {self.next_seq_num - 1}...", "vermelho")
                        self.tempo_envio_base = time.time() # Reseta timer
                        
                        # Retransmite TODOS a partir da base
                        for i in range(self.base, self.next_seq_num):
                            if i in self.pacotes_enviados:
                                self.log(f"Re-enviando SEQ {i}", "amarelo")
                                enviar_pela_rede_ruidosa(self.sock, self.pacotes_enviados[i], ROUTER_ADDR)

    def loop_recebimento(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(50000)
                quadro, integro = Quadro.deserializar(data)
                
                if not integro:
                    self.log("Pacote corrompido (CRC).", "vermelho")
                    continue
                
                segmento = quadro['data']['data']
                
                if segmento['is_ack']:
                    ack_num = segmento['seq_num']
                    self.log(f"Recebido ACK {ack_num}", "ciano")
                    
                    with self.lock:
                        # GBN usa ACKs cumulativos
                        if ack_num >= self.base:
                            qtd_confirmada = (ack_num - self.base) + 1
                            for i in range(qtd_confirmada):
                                self.atualizar_status_visual("✓", "✓✓")
                            
                            self.log(f"Janela avançou para a base {ack_num + 1}", "verde")
                            self.base = ack_num + 1
                            
                            # Limpa os confirmados do buffer
                            for i in list(self.pacotes_enviados.keys()):
                                if i < self.base:
                                    del self.pacotes_enviados[i]
                            
                            if self.base < self.next_seq_num:
                                # Reinicia timer para o novo pacote base
                                self.tempo_envio_base = time.time()
                else:
                    sender = segmento['payload']['sender']
                    msg = segmento['payload']['message']
                    nome_arq = segmento['payload'].get('filename')
                    if nome_arq:
                        self.chat_print(f"{sender} enviou arquivo: {nome_arq}")
                    else:
                        self.chat_print(f"{sender}: {msg}")
            except Exception as e:
                pass

if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()