import socket
import time
import threading
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

# Estados de Recebimento (Cliente -> Server)
SEQ_ESPERADO = {}         
BUFFER_RECEBIMENTO = {}   
CLIENTES_CONECTADOS = set()

# Estados de Envio (Server -> Cliente)
SEQ_ENVIO = {}
BROADCASTS_PENDENTES = {} # Rastreia envios não confirmados
lock = threading.Lock()

HISTORICO_CONVERSA = [] 

def formatar_mensagem(msg_dict):
    try:
        ts = time.strftime('%H:%M:%S', time.localtime(msg_dict['timestamp']))
        sender = msg_dict['sender']
        arq = msg_dict.get('filename')
        if arq: return f"[{ts}] {sender} enviou arquivo: {arq}"
        return f"[{ts}] {sender}: {msg_dict['message']}"
    except: return "[Msg Malformada]"

def imprimir_historico():
    print(f"\n{C_MAGENTA}========== HISTÓRICO DE CONVERSA =========={C_RESET}")
    for msg in HISTORICO_CONVERSA: print(msg)
    print(f"{C_MAGENTA}==========================================={C_RESET}\n")

def enviar_ack(sock, seq_num, dst_vip):
    seg = Segmento(seq_num=seq_num, is_ack=True, payload={})
    pkt = Pacote(src_vip=MEU_VIP, dst_vip=dst_vip, ttl=5, segmento_dict=seg.to_dict())
    frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
    enviar_pela_rede_ruidosa(sock, frame.serializar(), ("127.0.0.1", 5000))

def broadcast_para_outros(sock, payload, remetente_vip):
    """Envia com garantia de entrega (salva na lista de pendentes)"""
    with lock:
        for destino in CLIENTES_CONECTADOS:
            if destino != remetente_vip:
                if destino not in SEQ_ENVIO:
                    SEQ_ENVIO[destino] = 0
                    BROADCASTS_PENDENTES[destino] = {}
                
                seq = SEQ_ENVIO[destino]
                SEQ_ENVIO[destino] += 1
                
                seg = Segmento(seq_num=seq, is_ack=False, payload=payload)
                pkt = Pacote(src_vip=MEU_VIP, dst_vip=destino, ttl=5, segmento_dict=seg.to_dict())
                frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
                bytes_envio = frame.serializar()
                
                # Salva para retransmitir se não vier o ACK
                BROADCASTS_PENDENTES[destino][seq] = {
                    "bytes": bytes_envio,
                    "time": time.time(),
                    "tentativas": 1
                }
                
                enviar_pela_rede_ruidosa(sock, bytes_envio, ("127.0.0.1", 5000))

def monitor_timeouts_server(sock):
    """Thread em segundo plano que retransmite broadcasts perdidos"""
    while True:
        time.sleep(1)
        agora = time.time()
        with lock:
            for vip, pendentes in list(BROADCASTS_PENDENTES.items()):
                for seq, info in list(pendentes.items()):
                    if agora - info["time"] > 3.0: # TIMEOUT
                        info["tentativas"] += 1
                        info["time"] = agora
                        print(f"{C_YELLOW}[ARQ] TIMEOUT. Re-fazendo broadcast SEQ {seq} para {vip}{C_RESET}")
                        enviar_pela_rede_ruidosa(sock, info["bytes"], ("127.0.0.1", 5000))

def main():
    print(f"--- {MEU_VIP} (Chat Totalmente Confiável) ---")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_ESCUTA))
    
    # Inicia a thread de retransmissão do servidor
    threading.Thread(target=monitor_timeouts_server, args=(sock,), daemon=True).start()

    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            quadro_dict, integro = Quadro.deserializar(data)
            
            if not integro: continue

            pacote = quadro_dict['data']
            segmento = pacote['data']
            src_vip = pacote['src_vip']
            
            if segmento['is_ack']:
                # O Cliente confirmou que recebeu o nosso Broadcast!
                seq = segmento['seq_num']
                with lock:
                    if src_vip in BROADCASTS_PENDENTES and seq in BROADCASTS_PENDENTES[src_vip]:
                        del BROADCASTS_PENDENTES[src_vip][seq]
                        print(f"{C_CYAN}[ARQ] {src_vip} confirmou leitura do broadcast SEQ {seq}{C_RESET}")
                continue

            # --- PROCESSAMENTO DE DADOS CHEGANDO ---
            seq_recebido = segmento['seq_num']
            
            if src_vip not in SEQ_ESPERADO:
                SEQ_ESPERADO[src_vip] = 0
                BUFFER_RECEBIMENTO[src_vip] = {}
                CLIENTES_CONECTADOS.add(src_vip)
            
            # Envia ACK para o cliente
            enviar_ack(sock, seq_recebido, src_vip)
            
            if seq_recebido == SEQ_ESPERADO[src_vip]:
                payload = segmento['payload']
                
                if payload.get('type') != 'hello':
                    print(f"{C_GREEN}[ARQ] Processando SEQ {seq_recebido} de {src_vip}. Fazendo broadcast...{C_RESET}")
                    HISTORICO_CONVERSA.append(formatar_mensagem(payload))
                    imprimir_historico()
                
                # Repassa a mensagem
                broadcast_para_outros(sock, payload, src_vip)
                SEQ_ESPERADO[src_vip] += 1
                
                # Buffer flush
                while SEQ_ESPERADO[src_vip] in BUFFER_RECEBIMENTO[src_vip]:
                    payload_buf = BUFFER_RECEBIMENTO[src_vip].pop(SEQ_ESPERADO[src_vip])
                    if payload_buf.get('type') != 'hello':
                        HISTORICO_CONVERSA.append(formatar_mensagem(payload_buf))
                        imprimir_historico()
                    broadcast_para_outros(sock, payload_buf, src_vip)
                    SEQ_ESPERADO[src_vip] += 1
                    
            elif seq_recebido > SEQ_ESPERADO[src_vip]:
                if seq_recebido not in BUFFER_RECEBIMENTO[src_vip]:
                    BUFFER_RECEBIMENTO[src_vip][seq_recebido] = segmento['payload']
                    print(f"{C_YELLOW}[ARQ] SEQ {seq_recebido} de {src_vip} guardado no buffer.{C_RESET}")

        except Exception as e: 
            pass

if __name__ == "__main__":
    main()