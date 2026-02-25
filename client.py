import customtkinter as ctk
from tkinter import filedialog
import socket
import threading
import time
import base64
import sys
import os
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
        self.geometry("680x750")

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
        
        # Botão de Gerenciamento de Downloads
        self.btn_downloads = ctk.CTkButton(self.input_frame, text="📥 (0)", width=60, height=40, command=self.abrir_downloads)
        self.btn_downloads.pack(side="left", padx=5)

        self.btn_env = ctk.CTkButton(self.input_frame, text="Enviar", width=80, height=40, command=self.iniciar_envio)
        self.btn_env.pack(side="left")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        
        self.seq_atual = 0
        self.mensagens_pendentes = {} 
        self.lock = threading.Lock()
        
        self.seq_esperado_servidor = 0
        self.buffer_recebimento = {}
        self.repositorio_arquivos = {} 
        self.arquivos_prontos = {} # Guarda os arquivos montados esperando download
        
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

    def atualizar_btn_downloads(self):
        qtd = len(self.arquivos_prontos)
        if qtd > 0:
            self.btn_downloads.configure(text=f"📥 ({qtd})", fg_color="#4CAF50")
        else:
            self.btn_downloads.configure(text=f"📥 (0)", fg_color=["#3B8ED0", "#1F6AA5"])

    def abrir_downloads(self):
        if not self.arquivos_prontos: return
        
        top = ctk.CTkToplevel(self)
        top.title("Arquivos Prontos para Baixar")
        top.geometry("400x300")
        top.attributes("-topmost", True)
        
        for nome, bytes_arq in self.arquivos_prontos.items():
            frame = ctk.CTkFrame(top)
            frame.pack(fill="x", padx=10, pady=5)
            
            lbl = ctk.CTkLabel(frame, text=nome, width=250, anchor="w")
            lbl.pack(side="left", padx=10)
            
            btn = ctk.CTkButton(frame, text="Salvar", width=60, command=lambda n=nome, b=bytes_arq: self.salvar_arquivo_disco(n, b, top))
            btn.pack(side="right", padx=10, pady=5)

    def salvar_arquivo_disco(self, nome, bytes_arq, window):
        path = filedialog.asksaveasfilename(initialfile=nome, title="Salvar Arquivo")
        if path:
            try:
                with open(path, "wb") as f:
                    f.write(bytes_arq)
                del self.arquivos_prontos[nome]
                self.atualizar_btn_downloads()
                self.log(f"Arquivo salvo em: {path}", "verde")
                window.destroy()
                self.abrir_downloads()
            except Exception as e:
                self.log(f"Erro ao salvar arquivo: {e}", "vermelho")

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

    def enviar_arquivo_thread(self, path):
        nome = path.split('/')[-1]
        CHUNK_SIZE = 24000 
        
        try:
            with open(path, 'rb') as f:
                dados_brutos = f.read()


            dados_b64_completos = base64.b64encode(dados_brutos).decode('utf-8')
            
            fatias = [dados_b64_completos[i:i + CHUNK_SIZE] for i in range(0, len(dados_b64_completos), CHUNK_SIZE)]
            total = len(fatias)
            
            self.log(f"Enviando {nome} em {total} pacotes grandes...", "ciano")

            horario = time.strftime('%H:%M')
            self.text_area.configure(state='normal')
            self.text_area.insert("end", f"Você: 📁 {nome}\n", "msg_user")
            
            seq_final = self.seq_atual + total - 1
            tag_status = f"status_{seq_final}"
            self.text_area._textbox.insert("end", f"{horario} 🕒\n", ("direita", tag_status))
            self.text_area.configure(state='disabled')
            self.text_area.see("end")

            for i, fatia_b64 in enumerate(fatias):
                payload_fragmento = {
                    "filename": nome, 
                    "chunk_index": i, 
                    "total_chunks": total, 
                    "content": fatia_b64
                }
                
                seq = self.obter_novo_seq()
                bytes_envio = self.construir_pilha(payload_fragmento, "file_chunk", seq)
                
                with self.lock:
                    self.mensagens_pendentes[seq] = {
                        "bytes": bytes_envio,
                        "time": time.time(),
                        "tentativas": 1
                    }
                
                enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
                
                if i == total - 1:
                    self.atualizar_status_visual(seq, "✓")
                
                time.sleep(0.05)

        except Exception as e:
            self.log(f"Erro ao enviar arquivo: {e}", "vermelho")

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if path:
            threading.Thread(target=self.enviar_arquivo_thread, args=(path,)).start()

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
        sender = payload['sender']
        tipo = payload.get('type')
        
        if tipo == "hello":
            self.chat_print(f"[{sender} ENTROU NO CHAT]")
            return

        if tipo == "file_chunk":
            chunk_data = payload.get('message', {})
            nome = chunk_data.get('filename', 'arquivo')
            idx = chunk_data.get('chunk_index', 0)
            total = chunk_data.get('total_chunks', 1)
            conteudo_b64 = chunk_data.get('content', '')

            if nome not in self.repositorio_arquivos:
                self.repositorio_arquivos[nome] = [None] * total
            
            self.repositorio_arquivos[nome][idx] = conteudo_b64

            # Se recebeu o arquivo inteiro
            if all(f is not None for f in self.repositorio_arquivos[nome]):
                try:
                    full_b64 = "".join(self.repositorio_arquivos[nome])
                    bytes_finais = base64.b64decode(full_b64)
                    
                    # Guarda o arquivo na memória e atualiza a interface
                    self.arquivos_prontos[nome] = bytes_finais
                    self.chat_print(f"📁 {sender} enviou arquivo: {nome}")
                    self.atualizar_btn_downloads()
                    
                except Exception as e:
                    self.chat_print(f"❌ Erro ao reconstruir {nome}: {e}")
                finally:
                    del self.repositorio_arquivos[nome]
            return

        nome_arq = payload.get('filename')
        if nome_arq:
            self.chat_print(f"{sender} enviou arquivo: {nome_arq}")
        else:
            msg = payload.get('message', '')
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
                    remetente_pacote = pacote['src_vip']
                    
                    ack_seg = Segmento(seq_num=seq_recebido, is_ack=True, payload={})
                    ack_pkt = Pacote(src_vip=self.MY_VIP, dst_vip=remetente_pacote, ttl=5, segmento_dict=ack_seg.to_dict())
                    ack_frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=ack_pkt.to_dict())
                    enviar_pela_rede_ruidosa(self.sock, ack_frame.serializar(), ROUTER_ADDR)

                    with self.lock:
                        if seq_recebido == self.seq_esperado_servidor:
                            self.processar_mensagem_tela(segmento['payload'])
                            self.seq_esperado_servidor += 1
                            
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