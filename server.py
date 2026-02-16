import socket
import json
import time
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

# --- CONFIGURAÇÃO ---
MEU_VIP = "SERVIDOR_PRIME"
PORTA_ESCUTA = 6000
BUFFER_SIZE = 4096

# Estado do Stop-and-Wait
SEQ_ESPERADO = 0  # Começamos esperando o pacote 0

def formatar_mensagem(msg_dict):
    try:
        ts = time.strftime('%H:%M:%S', time.localtime(msg_dict['timestamp']))
        sender = msg_dict['sender']
        message = msg_dict['message']
        return f"[{ts}] {sender} diz: {message}"
    except:
        return "[Msg Malformada]"

def enviar_ack(sock, addr, seq_num, dst_vip):
    """
    Constrói e envia um pacote contendo apenas um ACK.
    O ACK também deve seguir a estrutura de Bonecas Russas!
    """
    # 1. Segmento (ACK=True)
    seg = Segmento(seq_num=seq_num, is_ack=True, payload={})
    
    # 2. Pacote
    pkt = Pacote(src_vip=MEU_VIP, dst_vip=dst_vip, ttl=5, segmento_dict=seg.to_dict())
    
    # 3. Quadro
    frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
    
    # Em vez de enviar para 'addr' (que seria o IP direto), envia para o roteador
    enviar_pela_rede_ruidosa(sock, frame.serializar(), ("127.0.0.1", 5000))
    print(f"[ARQ] Enviado ACK {seq_num} para {addr}")

def main():
    global SEQ_ESPERADO
    print(f"--- {MEU_VIP} (Fase 2: Confiável) ---")
    print(f"Ouvindo na porta {PORTA_ESCUTA}...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_ESCUTA))

    while True:
        try:
            # --- RECEBIMENTO ---
            data, addr = sock.recvfrom(BUFFER_SIZE)
            
            # 1. Enlace: Verifica CRC
            quadro_dict, integro = Quadro.deserializar(data)
            if not integro:
                print(f"[ERRO FÍSICO] CRC Falhou. Pacote de {addr} ignorado.")
                continue # Se corrompeu, não enviamos ACK (Cliente vai dar timeout)

            # Decapsulamento
            pacote = quadro_dict['data']
            segmento = pacote['data']
            
            # --- TRANSPORTE (Lógica Stop-and-Wait) ---
            seq_recebido = segmento['seq_num']
            
            if seq_recebido == SEQ_ESPERADO:
                # PACOTE NOVO E CORRETO
                print(f"[ARQ] Recebido SEQ {seq_recebido} (Esperado). Aceitando.")
                
                # Entrega para Aplicação
                app_data = segmento['payload']
                print("-" * 40)
                print(formatar_mensagem(app_data))
                print("-" * 40)
                
                # Envia ACK
                enviar_ack(sock, addr, seq_recebido, pacote['src_vip'])
                
                # Inverte o esperado (0->1 ou 1->0)
                SEQ_ESPERADO = 1 - SEQ_ESPERADO
                
            else:
                # DUPLICATA
                print(f"[ARQ] Duplicata detectada! Recebido {seq_recebido}, mas esperava {SEQ_ESPERADO}.")
                print(f"[ARQ] Reenviando ACK {seq_recebido} para destravar o cliente.")
                # Reenvia o ACK do que chegou (para o cliente parar de reenviar)
                enviar_ack(sock, addr, seq_recebido, pacote['src_vip'])

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()