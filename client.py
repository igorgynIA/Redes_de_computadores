import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
import base64
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

# Cores para o terminal
C_RED = "\033[91m"    # Erros físicos/CRC
C_GREEN = "\033[92m"  # Mensagens de Aplicação
C_YELLOW = "\033[93m" # Retransmissões/Transporte
C_CYAN = "\033[96m"   # Controle/ACKs
C_MAGENTA = "\033[95m"
C_RESET = "\033[0m"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEGUNDOS = 3.0

class ChatClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Mini-NET - {MY_VIP} (Janela Deslizante)")
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
        
        self.seq_atual = 0
        self.mensagens_pendentes = {} 
        self.lock = threading.Lock()
        
        threading.Thread(target=self.loop_recebimento, daemon=True).start()
        threading.Thread(target=self.monitor_timeouts, daemon=True).start()

    def log(self, msg, tag=None):
        self.log_area.configure(state='normal')
        self.log_area.insert("end", f"> {msg}\n", tag)
        self.log_area.configure(state='disabled')
        self.log_area.see("end")

    def chat_print(self, msg):
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

    def atualizar_status_visual(self, seq, novo_icone):
        """Atualiza EXATAMENTE o status atrelado ao número de sequência (SEQ)"""
        try:
            self.text_area.configure(state='normal')
            tag_name = f"status_{seq}" # Busca a tag única da mensagem
            ranges = self.text_area._textbox.tag_ranges(tag_name)
            
            if ranges:
                inicio, fim = ranges[0], ranges[1]
                texto_atual = self.text_area._textbox.get(inicio, fim)
                
                # O texto atual é "15:42 🕒\n". Mantém a hora (5 chars) e troca o ícone
                hora = texto_atual[:5]
                novo_texto = f"{hora} {novo_icone}\n"
                
                self.text_area._textbox.delete(inicio, fim)
                # Reinsere com as mesmas tags para futuras atualizações
                self.text_area._textbox.insert(inicio, novo_texto, ("direita", tag_name))
                
            self.text_area.configure(state='disabled')
        except Exception as e:
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

    def obter_novo_seq(self):
        with self.lock:
            seq = self.seq_atual
            self.seq_atual += 1
            return seq

    def iniciar_envio(self):
        texto = self.entry.get()
        if not texto: return
        self.entry.delete(0, "end")
        
        seq = self.obter_novo_seq()
        horario = time.strftime('%H:%M')
        
        self.text_area.configure(state='normal')
        self.text_area.insert("end", f"Você: {texto}\n", "msg_user")
        
        # Cria uma tag exclusiva para esse SEQ
        tag_status = f"status_{seq}"
        self.text_area._textbox.insert("end", f"{horario} 🕒\n", ("direita", tag_status))
        self.text_area.configure(state='disabled')
        self.text_area.see("end")
        
        threading.Thread(target=self.enviar_dados, args=(texto, "text", seq)).start()

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if not path: return
        
        nome = path.split('/')[-1]
        CHUNK_SIZE = 1024 # 1KB por pedaço
        
        with open(path, 'rb') as f:
            dados_brutos = f.read()

        # Fragmentação correta
        fatias = [dados_brutos[i:i + CHUNK_SIZE] for i in range(0, len(dados_brutos), CHUNK_SIZE)]
        total = len(fatias)
        
        self.log(f"Fragmentando {nome} em {total} pacotes...", "ciano")

        # Dispara os fragmentos
        for i, fatia_binaria in enumerate(fatias):
            fatia_b64 = base64.b64encode(fatia_binaria).decode('utf-8')
            
            # O Payload contém os dados do pedaço
            payload_fragmento = {
                "filename": nome, 
                "chunk_index": i, 
                "total_chunks": total, 
                "content": fatia_b64
            }
            
            # IMPORTANTE: Cada fragmento ganha um SEQ ÚNICO para o transporte
            seq = self.obter_novo_seq()
            
            # Registra no monitor de timeouts global para retransmissão automática
            bytes_p = self.construir_pilha(payload_fragmento, "file_chunk", seq)
            
            with self.lock:
                self.mensagens_pendentes[seq] = {
                    "bytes": bytes_p,
                    "time": time.time(),
                    "tentativas": 1
                }
            
            # Envio inicial
            enviar_pela_rede_ruidosa(self.sock, bytes_p, ROUTER_ADDR)

    def enviar_dados(self, conteudo, tipo, seq, filename=None):
        bytes_envio = self.construir_pilha(conteudo, tipo, seq, filename)
        
        with self.lock:
            self.mensagens_pendentes[seq] = {
                "bytes": bytes_envio,
                "time": time.time(),
                "tentativas": 1
            }

        self.log(f"--- Iniciando envio SEQ {seq} ---", "amarelo")
        enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
        self.atualizar_status_visual(seq, "✓") # Atualiza visualmente para Enviado

    def monitor_timeouts(self):
        while True:
            time.sleep(1)
            agora = time.time()
            with self.lock:
                for seq, info in list(self.mensagens_pendentes.items()):
                    if agora - info["time"] > TIMEOUT_SEGUNDOS:
                        info["tentativas"] += 1
                        info["time"] = agora
                        self.log(f"TIMEOUT. Retransmitindo SEQ {seq} (Tentativa {info['tentativas']})", "amarelo")
                        enviar_pela_rede_ruidosa(self.sock, info["bytes"], ROUTER_ADDR)

    def loop_recebimento(self):
        while True:
            try:
                # Mantemos o buffer maior para evitar truncamento de JSONs grandes
                data, _ = self.sock.recvfrom(50000)
                
                # Deserializa e verifica integridade (Camada de Enlace)
                quadro, integro = Quadro.deserializar(data)
                
                if not integro:
                    # Log em vermelho para erro de CRC (Camada Física/Enlace)
                    self.log("Erro de integridade (CRC)! Pacote descartado.", "red")
                    continue
                
                # Decapsulamento: Quadro -> Pacote -> Segmento
                pacote = quadro['data'] #
                segmento = pacote['data'] #
                
                # Lógica de Transporte (ACKs Sequenciais)
                if segmento['is_ack']:
                    seq = segmento['seq_num']
                    # Log em ciano para mensagens de controle
                    self.log(f"Recebido ACK {seq}", "cyan")
                    
                    # O LOCK é essencial para evitar conflito com a thread de retransmissão
                    with self.lock:
                        if seq in self.mensagens_pendentes:
                            # Remove do dicionário de pendentes para interromper retransmissões
                            del self.mensagens_pendentes[seq]
                            
                            # Feedback visual de sucesso
                            self.log(f"Confirmação do Pacote {seq} OK!", "green")
                            self.atualizar_status_visual(seq, "✓✓")
                
                # Lógica de Aplicação (Mensagens Recebidas)
                else:
                    payload = segmento['payload']
                    sender = payload.get('sender', 'Desconhecido')
                    
                    # Verifica se o que chegou é um fragmento de arquivo
                    if payload.get('type') == "file_chunk":
                        chunk_data = payload.get('message', {})
                        nome_arq = chunk_data.get('filename', 'arquivo')
                        idx = chunk_data.get('chunk_index')
                        total = chunk_data.get('total_chunks')
                        
                        self.chat_print(f"📦 {sender} enviando: {nome_arq} ({idx+1}/{total})")
                        # Dica: Se quiser que o CLIENTE também receba arquivos, 
                        # o Amigo A deve implementar o buffer de reconstrução aqui.
                    else:
                        # Chat convencional
                        msg = payload.get('message', '')
                        self.chat_print(f"{sender}: {msg}")

            except Exception as e:
                # Em caso de erro na rede ou socket fechado
                print(f"Erro no loop de recebimento: {e}")
                break

if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()