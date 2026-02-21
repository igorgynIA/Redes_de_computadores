import socket
import time
import os
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

C_RESET = "\033[0m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"

MEU_VIP = "SERVIDOR_PRIME"
PORTA_ESCUTA = 6000
BUFFER_SIZE = 50000

SEQ_ESPERADO = 0
BUFFER_RECEBIMENTO = {} 
HISTORICO_CONVERSA = [] # Lista para manter o chat ordenado

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

def imprimir_historico():
    """Imprime a conversa completa no terminal para monitoramento"""
    print(f"\n{C_MAGENTA}========== HISTÓRICO DE CONVERSA =========={C_RESET}")
    for msg in HISTORICO_CONVERSA:
        print(msg)
    print(f"{C_MAGENTA}==========================================={C_RESET}\n")

def enviar_ack(sock, addr, seq_num, dst_vip):
    seg = Segmento(seq_num=seq_num, is_ack=True, payload={})
    pkt = Pacote(src_vip=MEU_VIP, dst_vip=dst_vip, ttl=5, segmento_dict=seg.to_dict())
    frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
    enviar_pela_rede_ruidosa(sock, frame.serializar(), ("127.0.0.1", 5000))

def main():
    global SEQ_ESPERADO
    print(f"--- {MEU_VIP} (Fase 2: Confiável e Contínuo) ---")
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
            
            # Envia ACK imediatamente
            enviar_ack(sock, addr, seq_recebido, pacote['src_vip'])
            
            if seq_recebido == SEQ_ESPERADO:
                print(f"{C_GREEN}[ARQ] Recebido SEQ {seq_recebido} (Na ordem).{C_GREEN}")
                
                # Adiciona no histórico e imprime
                HISTORICO_CONVERSA.append(formatar_mensagem(segmento['payload']))
                imprimir_historico()
                SEQ_ESPERADO += 1
                
                # Descarrega o buffer de pacotes recebidos fora de ordem
                while SEQ_ESPERADO in BUFFER_RECEBIMENTO:
                    print(f"{C_CYAN}[ARQ] Processando SEQ {SEQ_ESPERADO} do buffer.{C_CYAN}")
                    HISTORICO_CONVERSA.append(formatar_mensagem(BUFFER_RECEBIMENTO.pop(SEQ_ESPERADO)))
                    imprimir_historico()
                    SEQ_ESPERADO += 1
                    
            elif seq_recebido > SEQ_ESPERADO:
                if seq_recebido not in BUFFER_RECEBIMENTO:
                    print(f"{C_YELLOW}[ARQ] SEQ {seq_recebido} fora de ordem. Guardando no buffer.{C_YELLOW}")
                    BUFFER_RECEBIMENTO[seq_recebido] = segmento['payload']
            else:
                print(f"{C_YELLOW}[ARQ] Duplicata do SEQ {seq_recebido} processada.{C_YELLOW}")

        except Exception as e:
            pass

if __name__ == "__main__":
    main()