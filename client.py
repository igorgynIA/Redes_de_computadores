import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
import base64
import sys
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEGUNDOS = 3.0

class ChatClient(ctk.CTk):
    def __init__(self, meu_vip):
        super().__init__()
        self.MY_VIP = meu_vip 
        self.title(f"Mini-NET - {self.MY_VIP}")
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
        self.sock.bind(("127.0.0.1", 0))
        
        # Estado de Envio
        self.seq_atual = 0
        self.mensagens_pendentes = {} 
        self.lock = threading.Lock()
        
        # Estado de Recebimento (NOVO: Para ordenar mensagens do servidor)
        self.seq_esperado_servidor = 0
        self.buffer_recebimento = {}
        
        threading.Thread(target=self.loop_recebimento, daemon=True).start()
        threading.Thread(target=self.monitor_timeouts, daemon=True).start()

        seq_hello = self.obter_novo_seq()
        threading.Thread(target=self.enviar_dados, args=("Entrou no chat", "hello", seq_hello)).start()

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
        try:
            self.text_area.configure(state='normal')
            tag_name = f"status_{seq}"
            ranges = self.text_area._textbox.tag_ranges(tag_name)
            if ranges:
                inicio, fim = ranges[0], ranges[1]
                texto_atual = self.text_area._textbox.get(inicio, fim)
                hora = texto_atual[:5]
                novo_texto = f"{hora} {novo_icone}\n"
                self.text_area._textbox.delete(inicio, fim)
                self.text_area._textbox.insert(inicio, novo_texto, ("direita", tag_name))
            self.text_area.configure(state='disabled')
        except: pass

    def construir_pilha(self, conteudo, tipo, seq, filename=None):
        app_data = {
            "type": tipo,
            "sender": self.MY_VIP,
            "message": conteudo,
            "filename": filename,
            "timestamp": time.time()
        }
        seg = Segmento(seq_num=seq, is_ack=False, payload=app_data)
        pkt = Pacote(src_vip=self.MY_VIP, dst_vip=DEST_VIP, ttl=5, segmento_dict=seg.to_dict())
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
        
        tag_status = f"status_{seq}"
        self.text_area._textbox.insert("end", f"{horario} 🕒\n", ("direita", tag_status))
        self.text_area.configure(state='disabled')
        self.text_area.see("end")
        
        threading.Thread(target=self.enviar_dados, args=(texto, "text", seq)).start()

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

                seq = self.obter_novo_seq()
                horario = time.strftime('%H:%M')
                
                self.text_area.configure(state='normal')
                self.text_area.insert("end", f"Você: 📁 {nome}\n", "msg_user")
                
                tag_status = f"status_{seq}"
                self.text_area._textbox.insert("end", f"{horario} 🕒\n", ("direita", tag_status))
                self.text_area.configure(state='disabled')
                self.text_area.see("end")

                threading.Thread(target=self.enviar_dados, args=(dados_b64, "file", seq, nome)).start()
            except Exception as e:
                self.log(f"Erro ao ler arquivo: {e}", "vermelho")

    def enviar_dados(self, conteudo, tipo, seq, filename=None):
        bytes_envio = self.construir_pilha(conteudo, tipo, seq, filename)
        
        with self.lock:
            self.mensagens_pendentes[seq] = {
                "bytes": bytes_envio,
                "time": time.time(),
                "tentativas": 1
            }

        if tipo != "hello":
            self.log(f"--- Iniciando envio SEQ {seq} ---", "amarelo")
        
        enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
        if tipo != "hello": self.atualizar_status_visual(seq, "✓")

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

    def processar_mensagem_tela(self, payload):
        """Helper para imprimir na tela a mensagem recebida"""
        sender = payload['sender']
        msg = payload['message']
        tipo = payload.get('type')
        
        if tipo == "hello":
            self.chat_print(f"[{sender} ENTROU NO CHAT]")
            return

        nome_arq = payload.get('filename')
        if nome_arq:
            self.chat_print(f"{sender} enviou arquivo: {nome_arq}")
        else:
            self.chat_print(f"{sender}: {msg}")

    def loop_recebimento(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(50000)
                quadro, integro = Quadro.deserializar(data)
                
                if not integro:
                    self.log("Pacote corrompido (CRC). Ignorado.", "vermelho")
                    continue
                
                pacote = quadro['data']
                segmento = pacote['data']
                
                if segmento['is_ack']:
                    seq = segmento['seq_num']
                    with self.lock:
                        if seq in self.mensagens_pendentes:
                            del self.mensagens_pendentes[seq]
                            self.log(f"ACK {seq} confirmado com sucesso!", "verde")
                            self.atualizar_status_visual(seq, "✓✓")
                else:
                    seq_recebido = segmento['seq_num']
                    remetente_pacote = pacote['src_vip'] # SERVIDOR_PRIME
                    
                    # Envia ACK obrigatoriamente
                    ack_seg = Segmento(seq_num=seq_recebido, is_ack=True, payload={})
                    ack_pkt = Pacote(src_vip=self.MY_VIP, dst_vip=remetente_pacote, ttl=5, segmento_dict=ack_seg.to_dict())
                    ack_frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=ack_pkt.to_dict())
                    enviar_pela_rede_ruidosa(self.sock, ack_frame.serializar(), ROUTER_ADDR)

                    # --- NOVA LÓGICA DE ORDENAÇÃO NA TELA ---
                    with self.lock:
                        if seq_recebido == self.seq_esperado_servidor:
                            self.processar_mensagem_tela(segmento['payload'])
                            self.seq_esperado_servidor += 1
                            
                            # Descarrega buffer de mensagens fora de ordem
                            while self.seq_esperado_servidor in self.buffer_recebimento:
                                payload_buf = self.buffer_recebimento.pop(self.seq_esperado_servidor)
                                self.processar_mensagem_tela(payload_buf)
                                self.seq_esperado_servidor += 1
                                
                        elif seq_recebido > self.seq_esperado_servidor:
                            if seq_recebido not in self.buffer_recebimento:
                                self.buffer_recebimento[seq_recebido] = segmento['payload']
                                self.log(f"Mensagem {seq_recebido} no buffer de tela.", "amarelo")

            except Exception as e: pass

if __name__ == "__main__":
    vip_escolhido = input("Digite seu VIP (Ex: HOST_A, HOST_B): ").strip().upper()
    if not vip_escolhido: vip_escolhido = "HOST_ANONIMO"
    app = ChatClient(vip_escolhido)
    app.mainloop()