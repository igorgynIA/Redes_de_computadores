import socket
import json
import time
from protocol import Quadro  # Importa apenas as classes básicas

# --- CONFIGURAÇÃO ---
MEU_VIP = "SERVIDOR_PRIME"
PORTA_ESCUTA = 6000
BUFFER_SIZE = 4096

def formatar_mensagem(msg_dict):
    """Formata o JSON recebido para exibir bonitinho no terminal"""
    try:
        ts = time.strftime('%H:%M:%S', time.localtime(msg_dict['timestamp']))
        sender = msg_dict['sender']
        content = msg_dict['content']
        tipo = msg_dict['type']
        
        if tipo == 'file':
            return f"[{ts}] 📁 {sender} enviou arquivo: {content}"
        return f"[{ts}] {sender} diz: {content}"
    except:
        return "[Msg Malformada]"

def main():
    print(f"--- {MEU_VIP} INICIADO NA PORTA {PORTA_ESCUTA} ---")
    print("Aguardando mensagens...")

    # Configura socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_ESCUTA))

    while True:
        try:
            # 1. Recebimento Físico
            data, addr = sock.recvfrom(BUFFER_SIZE)
            
            # 2. Camada de Enlace (Verifica CRC)
            quadro_dict, integro = Quadro.deserializar(data)
            
            if not integro:
                print(f"[ERRO] Quadro de {addr} corrompido! Descartando.")
                continue # Simula o hardware descartando silenciosamente
            
            # 3. Decapsulamento (Bonecas Russas)
            # Quadro -> Pacote -> Segmento -> Aplicação
            pacote = quadro_dict['data']
            segmento = pacote['data']
            app_data = segmento['payload']
            
            # 4. Aplicação (Exibir)
            msg_formatada = formatar_mensagem(app_data)
            print("-" * 40)
            print(f"Recebido de {addr}:")
            print(msg_formatada)
            print("-" * 40)

        except KeyboardInterrupt:
            print("\nServidor encerrado.")
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()