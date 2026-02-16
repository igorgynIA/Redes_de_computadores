import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
import base64
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
        self.geometry("650x750")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Área de Chat
        self.text_area = ctk.CTkTextbox(self, state='disabled', corner_radius=10, font=("Roboto", 14))
        self.text_area.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Tags do Chat (Direita/Esquerda)
        self.text_area._textbox.tag_config("direita", justify="right", foreground="gray", spacing3=5)
        self.text_area._textbox.tag_config("msg_user", foreground="white")

        # 2. Área de Logs (Terminal Colorido)
        self.log_area = ctk.CTkTextbox(self, height=200, fg_color="#1a1a1a", font=("Consolas", 12), corner_radius=10)
        self.log_area.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # --- CONFIGURAÇÃO DAS CORES DO TERMINAL (TAGS) ---
        # Mapeando cores ANSI para Hexadecimal do Tkinter
        self.log_area._textbox.tag_config("vermelho", foreground="#ff5555") # Erros/CRC
        self.log_area._textbox.tag_config("verde",    foreground="#55ff55") # Sucesso/App
        self.log_area._textbox.tag_config("amarelo",  foreground="#ffff55") # Transporte/Retransmissão
        self.log_area._textbox.tag_config("ciano",    foreground="#55ffff") # Controle/ACKs
        self.log_area._textbox.tag_config("magenta",  foreground="#ff55ff") # Roteamento (se houver)
        # -------------------------------------------------

        # 3. Frame de Entrada
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Digite sua mensagem...", height=40)
        self.entry.pack(side="left", padx=(0, 10), fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.iniciar_envio_thread())

        self.btn_emoji = ctk.CTkButton(self.input_frame, text="😀", width=40, height=40, command=self.abrir_seletor_emojis)
        self.btn_emoji.pack(side="left", padx=5)

        self.btn_file = ctk.CTkButton(self.input_frame, text="📁", width=40, height=40, command=self.enviar_arquivo)
        self.btn_file.pack(side="left", padx=5)

        self.btn_env = ctk.CTkButton(self.input_frame, text="Enviar", width=80, height=40, command=self.iniciar_envio_thread)
        self.btn_env.pack(side="left")

        # --- Rede ---
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 6001))
        
        self.seq_atual = 0
        self.ack_event = threading.Event()
        self.ack_recebido_seq = -1
        
        threading.Thread(target=self.loop_recebimento, daemon=True).start()

    # --- UI Methods ---
    def log(self, msg, tag=None):
        """
        Insere log no terminal com a cor especificada pela tag.
        Tags disponíveis: 'vermelho', 'verde', 'amarelo', 'ciano', 'magenta'
        """
        self.log_area.configure(state='normal')
        self.log_area.insert("end", f"> {msg}\n", tag) # Aplica a tag aqui
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
            posicao = self.text_area._textbox.search(status_antigo, "end-1c", "end-10l", backwards=True)
            if posicao:
                fim_posicao = f"{posicao}+{len(status_antigo)}c"
                self.text_area._textbox.delete(posicao, fim_posicao)
                self.text_area._textbox.insert(posicao, status_novo, "direita")
            self.text_area.configure(state='disabled')
            self.text_area.see("end")
        except Exception as e:
            print(f"Erro visual: {e}")

    # --- Network Logic ---
    def construir_pilha(self, conteudo, tipo, filename=None):
        app_data = {
            "type": tipo,
            "sender": MY_VIP,
            "message": conteudo,
            "filename": filename,
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
        
        # Visual Chat
        horario = time.strftime('%H:%M')
        self.text_area.configure(state='normal')
        self.text_area.insert("end", f"Você: {texto}\n", "msg_user")
        self.text_area._textbox.insert("end", f"{horario} 🕒\n", "direita")
        self.text_area.configure(state='disabled')
        self.text_area.see("end")
        
        threading.Thread(target=self.enviar_confiavel, args=(texto, "text")).start()

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if path:
            nome = path.split('/')[-1]
            try:
                with open(path, 'rb') as f:
                    dados_brutos = f.read()
                
                if len(dados_brutos) > 50000:
                    self.log("ERRO: Arquivo muito grande (>50kb)", "vermelho")
                    return

                dados_b64 = base64.b64encode(dados_brutos).decode('utf-8')

                horario = time.strftime('%H:%M')
                self.text_area.configure(state='normal')
                self.text_area.insert("end", f"Você: 📁 {nome}\n", "msg_user")
                self.text_area._textbox.insert("end", f"{horario} 🕒\n", "direita")
                self.text_area.configure(state='disabled')
                self.text_area.see("end")

                threading.Thread(target=self.enviar_confiavel, args=(dados_b64, "file", nome)).start()

            except Exception as e:
                self.log(f"Erro ao ler arquivo: {e}", "vermelho")

    def enviar_confiavel(self, conteudo, tipo, filename=None):
        bytes_envio = self.construir_pilha(conteudo, tipo, filename)
        tentativa = 1
        status_atual = "🕒"
        
        # AMARELO: Início de Transporte
        self.log(f"--- Iniciando envio SEQ {self.seq_atual} ---", "amarelo")
        
        while True:
            # AMARELO: Tentativa de Envio
            self.log(f"Tentativa {tentativa}: Enviando...", "amarelo")
            
            enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
            
            if status_atual == "🕒":
                self.atualizar_status_visual("🕒", "✓")
                status_atual = "✓"
            
            self.ack_event.clear()
            ack_chegou = self.ack_event.wait(timeout=TIMEOUT_SEGUNDOS)
            
            if ack_chegou and self.ack_recebido_seq == self.seq_atual:
                # VERDE: Sucesso final da operação
                self.log(f"ACK {self.seq_atual} recebido com sucesso!", "verde")
                
                self.atualizar_status_visual("✓", "✓✓")
                self.seq_atual = 1 - self.seq_atual
                break
            else:
                # AMARELO: Timeout
                self.log("TIMEOUT. Retransmitindo...", "amarelo")
                tentativa += 1

        self.btn_env.configure(state="normal")

    def loop_recebimento(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                quadro, integro = Quadro.deserializar(data)
                
                if not integro:
                    # VERMELHO: Erro Físico/CRC
                    self.log("Pacote corrompido (CRC). Ignorado.", "vermelho")
                    continue
                
                pacote = quadro['data']
                segmento = pacote['data']
                
                if segmento['is_ack']:
                    seq = segmento['seq_num']
                    # CIANO: Controle puro (chegada do pacote)
                    self.log(f"Recebido ACK {seq}", "ciano")
                    
                    self.ack_recebido_seq = seq
                    self.ack_event.set()
                else:
                    # Mensagem de Chat (Outro usuário)
                    sender = segmento['payload']['sender']
                    msg = segmento['payload']['message']
                    nome_arq = segmento['payload'].get('filename') # Pega nome se existir

                    if nome_arq:
                        self.chat_print(f"{sender} enviou arquivo: {nome_arq}")
                    else:
                        self.chat_print(f"{sender}: {msg}")
                    
            except Exception as e:
                print(e)

if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()