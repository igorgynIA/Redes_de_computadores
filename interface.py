import tkinter as tk
from tkinter import filedialog, messagebox
import json
import threading
import time
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa, socket

# Configurações de Rede (Fase 3)
MY_VIP = "HOST_A"
DEST_VIP = "SERVIDOR_PRIME"
ROUTER_ADDR = ("127.0.0.1", 5000) # Endereço real do router.py
DEFAULT_TTL = 5

class ChatApp:
    def __init__(self, master):
        self.master = master
        master.title(f"Mini-NET Chat - {MY_VIP}")
        
        # UI Elements
        self.text_area = tk.Text(master, state='disabled', height=15, width=50)
        self.text_area.pack(padx=10, pady=10)
        
        self.msg_entry = tk.Entry(master, width=40)
        self.msg_entry.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.send_btn = tk.Button(master, text="Enviar", command=self.send_message)
        self.send_btn.pack(side=tk.LEFT, pady=10)
        
        self.file_btn = tk.Button(master, text="📁", command=self.send_file)
        self.file_btn.pack(side=tk.LEFT, padx=5)
        
        self.emoji_btn = tk.Button(master, text="😀", command=self.open_emoji_picker)
        self.emoji_btn.pack(side=tk.LEFT, padx=5)

        # Socket UDP (Fases 2, 3 e 4)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Thread para escuta
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def log(self, msg, color="black"):
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, msg + "\n")
        self.text_area.config(state='disabled')

    def send_message(self):
        msg = self.msg_entry.get()
        if msg:
            self.process_outbound(msg, "text")
            self.msg_entry.delete(0, tk.END)

    def send_file(self):
        path = filedialog.askopenfilename()
        if path:
            # Em IA/Sinais, arquivos são apenas arrays de bytes
            self.process_outbound(f"Arquivo: {path.split('/')[-1]}", "file")

    def open_emoji_picker(self):
            """Cria uma janela flutuante com opções de emojis."""
            top = tk.Toplevel(self.master)
            top.title("Escolha um Emoji")
            top.geometry("200x150")

            emojis = ["😀", "😂", "🚀", "🔥", "👍", "🤖", "💻", "✅"]
            
            # Organiza os emojis em uma grade
            for i, emoji in enumerate(emojis):
                btn = tk.Button(top, text=emoji, font=("Arial", 14),
                                command=lambda e=emoji: self.insert_emoji(e, top))
                btn.grid(row=i//4, column=i%4, padx=5, pady=5)

    def insert_emoji(self, emoji, window):
        """Insere o emoji no campo de entrada e fecha a janela."""
        self.msg_entry.insert(tk.END, emoji)
        window.destroy()
        self.msg_entry.focus_set()

    def process_outbound(self, content, msg_type):
        """Encapsulamento Top-Down (Fase 1 -> 2 -> 3 -> 4)"""
        # Fase 1: Aplicação (JSON)
        app_data = {
            "type": msg_type,
            "sender": MY_VIP,
            "content": content,
            "timestamp": time.time()
        }
        
        # Fase 2: Transporte (Simulado simplificado para o exemplo)
        seg = Segmento(seq_num=0, is_ack=False, payload=app_data)
        
        # Fase 3: Rede (Roteamento Virtual e TTL) - SUA PARTE
        pacote = Pacote(src_vip=MY_VIP, dst_vip=DEST_VIP, ttl=DEFAULT_TTL, segmento_dict=seg.to_dict())
        
        # Fase 4: Enlace (MAC e CRC)
        quadro = Quadro(src_mac="AA:BB", dst_mac="CC:DD", pacote_dict=pacote.to_dict())
        
        # Envio via camada física ruidosa
        enviar_pela_rede_ruidosa(self.sock, quadro.serializar(), ROUTER_ADDR)
        self.log(f"Enviado: {content}")

    def receive_loop(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                quadro_dict, integro = Quadro.deserializar(data)
                
                if not integro:
                    self.log("[ERRO] Quadro corrompido (CRC incorreto)!", "red")
                    continue
                
                # Decapsulamento: Quadro -> Pacote -> Segmento -> App
                pacote_data = quadro_dict['data']
                segmento_data = pacote_data['data']
                app_payload = segmento_data['payload']
                
                self.log(f"{app_payload['sender']}: {app_payload['content']}")
            except:
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()