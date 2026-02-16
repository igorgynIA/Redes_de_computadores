import tkinter as tk
from tkinter import filedialog
import socket
import threading
import time
import json
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

# --- CONFIGURAÇÃO ---
MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
# Fase 1: Apontamos direto para o servidor. Na Fase 3 mudaremos para porta 5000 (Router)
ROUTER_ADDR = ("127.0.0.1", 6000) 

class ChatClient:
    def __init__(self, master):
        self.master = master
        master.title(f"Mini-NET - {MY_VIP}")
        
        # --- Interface Gráfica ---
        self.text_area = tk.Text(master, state='disabled', height=15, width=60, bg="#f0f0f0")
        self.text_area.pack(padx=10, pady=10)
        
        self.log_area = tk.Listbox(master, height=6, width=60, bg="black", fg="#00ff00")
        self.log_area.pack(padx=10, pady=(0, 10))
        
        frame = tk.Frame(master)
        frame.pack(pady=10)
        
        self.entry = tk.Entry(frame, width=40)
        self.entry.pack(side=tk.LEFT, padx=5)
        
        btn_env = tk.Button(frame, text="Enviar", command=self.enviar_texto, bg="#4CAF50", fg="white")
        btn_env.pack(side=tk.LEFT, padx=5)
        
        btn_file = tk.Button(frame, text="📁", command=self.enviar_arquivo)
        btn_file.pack(side=tk.LEFT)

        # --- Rede ---
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0)) # Porta aleatória
        
        # Thread para receber mensagens (Fases futuras / ACKs)
        threading.Thread(target=self.loop_recebimento, daemon=True).start()

    def log(self, msg):
        """Log técnico na telinha preta"""
        self.log_area.insert(tk.END, f"> {msg}")
        self.log_area.yview(tk.END)

    def chat_print(self, msg):
        """Mostra no chat principal"""
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, msg + "\n")
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)

    def construir_pilha(self, conteudo, tipo):
        """
        Monta as Bonecas Russas: App -> Seg -> Pkt -> Frame
        """
        # 1. Aplicação
        app_data = {
            "type": tipo,
            "sender": MY_VIP,
            "content": conteudo,
            "timestamp": time.time()
        }
        
        # 2. Transporte (Fase 2: Adicionar controle de SEQ aqui)
        seg = Segmento(seq_num=0, is_ack=False, payload=app_data)
        
        # 3. Rede (Fase 3: TTL e Roteamento)
        pkt = Pacote(src_vip=MY_VIP, dst_vip=DEST_VIP, ttl=5, segmento_dict=seg.to_dict())
        
        # 4. Enlace (Fase 4: MAC e CRC)
        frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=pkt.to_dict())
        
        return frame.serializar()

    def enviar_texto(self):
        texto = self.entry.get()
        if not texto: return
        
        # Constrói
        bytes_envio = self.construir_pilha(texto, "text")
        
        # Envia usando o simulador de ruído
        enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
        
        self.log(f"Enviando {len(bytes_envio)} bytes...")
        self.chat_print(f"Você: {texto}")
        self.entry.delete(0, tk.END)

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if path:
            nome = path.split('/')[-1]
            bytes_envio = self.construir_pilha(nome, "file")
            enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
            self.chat_print(f"Enviando arquivo: {nome}")

    def loop_recebimento(self):
        # Na Fase 1, o cliente basicamente só envia, mas deixamos pronto
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                quadro, integro = Quadro.deserializar(data)
                if integro:
                    self.log("Recebido pacote íntegro (Fase futura: ACK)")
                else:
                    self.log("[ERRO] Pacote corrompido recebido")
            except:
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()