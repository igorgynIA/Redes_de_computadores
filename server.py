import socket
import time
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

C_RESET = "\033[0m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"

MEU_VIP = "SERVIDOR_PRIME"
PORTA_ESCUTA = 6000
BUFFER_SIZE = 50000

# No GBN, o receptor precisa apenas esperar o pacote na ordem exata
SEQ_ESPERADO = 0 

def formatar_mensagem(msg_dict):
    try:
        ts = time.strftime('%H:%M:%S', time.localtime(msg_dict['timestamp']))
        sender = msg_dict['sender']
        arq = msg_dict.get('filename')
        if arq:
            return f"[{ts}] {sender} enviou arquivo: {arq}"
        return f"[{ts}] {sender} diz: {msg_dict['message']}"
    except:
        return "[Msg Malformada]"

def enviar_ack(sock, addr, seq_num, dst_vip):
    seg = Segmento(seq_num=seq_num, is_ack=True, payload={})
    pkt = Pacote(src_vip=MEU_VIP, dst_vip=dst_vip, ttl=5, segmento_dict=seg.to_dict())
    frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
    enviar_pela_rede_ruidosa(sock, frame.serializar(), ("127.0.0.1", 5000))

def main():
    global SEQ_ESPERADO
    print(f"--- {MEU_VIP} (Fase 2: Confiável e Go-Back-N) ---")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_ESCUTA))

    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            quadro_dict, integro = Quadro.deserializar(data)
            
            if not integro:
                print(f"{C_RED}[ERRO] CRC Falhou. Descartado.{C_RED}")
                continue

            pacote = quadro_dict['data']
            segmento = pacote['data']
            seq_recebido = segmento['seq_num']
            
            # 1. Se chegou o pacote que eu esperava
            if seq_recebido == SEQ_ESPERADO:
                print(f"{C_GREEN}[ARQ] Recebido SEQ {seq_recebido} na ordem correta.{C_GREEN}")
                print(formatar_mensagem(segmento['payload']))
                
                enviar_ack(sock, addr, SEQ_ESPERADO, pacote['src_vip'])
                SEQ_ESPERADO += 1
                
            # 2. Se chegou pacote fora de ordem (GBN descarta e re-confirma o último correto)
            else:
                print(f"{C_YELLOW}[ARQ] Fora de ordem. Recebido {seq_recebido}, mas esperava {SEQ_ESPERADO}. Descartando.{C_YELLOW}")
                ultimo_correto = SEQ_ESPERADO - 1
                if ultimo_correto >= 0:
                    enviar_ack(sock, addr, ultimo_correto, pacote['src_vip'])

        except Exception as e:
            pass

if __name__ == "__main__":
    main()