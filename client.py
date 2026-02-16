import tkinter as tk
from tkinter import filedialog, messagebox
import socket
import threading
import time
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

# --- CONFIGURAÇÃO ---
MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEGUNDOS = 3.0 # Tempo antes de desistir e reenviar

class ChatClient:
    def __init__(self, master):
        self.master = master
        master.title(f"Mini-NET - {MY_VIP} (Fase 2)")
        
        # --- UI Setup ---
        self.text_area = tk.Text(master, state='disabled', height=15, width=60, bg="#f0f0f0")
        self.text_area.pack(padx=10, pady=10)
        
        self.log_area = tk.Listbox(master, height=8, width=60, bg="black", fg="#00ff00")
        self.log_area.pack(padx=10, pady=(0, 10))
        
        frame = tk.Frame(master)
        frame.pack(pady=10)
        
        self.entry = tk.Entry(frame, width=40)
        self.entry.pack(side=tk.LEFT, padx=5)
        
        # Botão envia em Thread separada para não travar a UI durante o timeout
        self.btn_env = tk.Button(frame, text="Enviar", command=self.iniciar_envio_thread, bg="#4CAF50", fg="white")
        self.btn_env.pack(side=tk.LEFT, padx=5)
        
        # No final do método __init__
        self.entry.bind("<Return>", lambda event: self.iniciar_envio_thread())
        
        self.btn_file = tk.Button(frame, text="📁", command=self.enviar_arquivo)
        self.btn_file.pack(side=tk.LEFT)

        # --- Rede e Estado Stop-and-Wait ---
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 6001)) # Porta que o Router usa para devolver dados ao HOST_A
        
        self.seq_atual = 0  # Começa com 0
        self.ack_event = threading.Event() # Sinalizador de ACK recebido
        self.ack_recebido_seq = -1 # Guarda qual SEQ veio no ACK
        
        # Thread de escuta contínua
        threading.Thread(target=self.loop_recebimento, daemon=True).start()

    def log(self, msg, cor=None):
        self.log_area.insert(tk.END, f"> {msg}")
        self.log_area.yview(tk.END)
        if cor: self.log_area.itemconfig(tk.END, {'fg': cor})

    def chat_print(self, msg):
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, msg + "\n")
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)

    def construir_pilha(self, conteudo, tipo):
        app_data = {
            "type": tipo,
            "sender": MY_VIP,
            "message": conteudo,
            "timestamp": time.time()
        }
        # IMPORTANTE: Usa o SEQ atual
        seg = Segmento(seq_num=self.seq_atual, is_ack=False, payload=app_data)
        pkt = Pacote(src_vip=MY_VIP, dst_vip=DEST_VIP, ttl=5, segmento_dict=seg.to_dict())
        frame = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=pkt.to_dict())
        return frame.serializar()

    def iniciar_envio_thread(self):
        # Se o botão estiver desativado, ignora qualquer comando (inclusive o Enter)
        if self.btn_env["state"] == "disabled":
            return

        texto = self.entry.get()
        if not texto: return
    
        # Desativa o botão aqui na thread principal (UI)
        self.btn_env.config(state="disabled")
    
        self.entry.delete(0, tk.END)
        self.chat_print(f"Você: {texto}")
    
        # Dispara a thread de rede
        threading.Thread(target=self.enviar_confiavel, args=(texto, "text")).start()

    def enviar_arquivo(self):
        path = filedialog.askopenfilename()
        if path:
            nome = path.split('/')[-1]
            self.chat_print(f"Enviando arquivo: {nome}")
            threading.Thread(target=self.enviar_confiavel, args=(nome, "file")).start()

    def enviar_confiavel(self, conteudo, tipo):
        """
        Lógica do STOP-AND-WAIT (Fase 2)
        Envia -> Espera -> Timeout -> Retransmite
        """
        bytes_envio = self.construir_pilha(conteudo, tipo)
        tentativa = 1
        
        self.log(f"--- Iniciando envio SEQ {self.seq_atual} ---")
        self.btn_env.config(state="disabled") # Trava botão

        while True:
            # 1. Envia (com possibilidade de perda simulada)
            self.log(f"Tentativa {tentativa}: Enviando...", "white")
            enviar_pela_rede_ruidosa(self.sock, bytes_envio, ROUTER_ADDR)
            
            # 2. Reseta o evento de ACK e espera
            self.ack_event.clear()
            
            # 3. Bloqueia esperando ACK ou Timeout
            ack_chegou = self.ack_event.wait(timeout=TIMEOUT_SEGUNDOS)
            
            if ack_chegou:
                # Verifica se o ACK é do SEQ correto
                if self.ack_recebido_seq == self.seq_atual:
                    self.log(f"ACK {self.seq_atual} recebido com sucesso!", "green")
                    # Inverte o SEQ para a próxima mensagem
                    self.seq_atual = 1 - self.seq_atual
                    break
                else:
                    self.log(f"ACK incorreto ({self.ack_recebido_seq}). Ignorando.", "yellow")
            else:
                self.log(f"TIMEOUT! Nenhuma confirmação recebida.", "red")
                self.log("Retransmitindo...", "yellow")
                tentativa += 1

        self.btn_env.config(state="normal") # Destrava botão

    def loop_recebimento(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                quadro, integro = Quadro.deserializar(data)
                
                if not integro:
                    self.log("Recebido pacote corrompido (CRC).", "red")
                    continue
                
                # Decapsula para ver se é ACK
                pacote = quadro['data']
                segmento = pacote['data']
                
                if segmento['is_ack']:
                    seq = segmento['seq_num']
                    self.log(f"Recebido ACK {seq}", "cyan")
                    
                    # Avisa a thread de envio
                    self.ack_recebido_seq = seq
                    self.ack_event.set() # Acorda a thread de envio
                    
            except Exception as e:
                print(e)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()