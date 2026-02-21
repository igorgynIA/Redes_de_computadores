import socket
import time
import threading
import base64
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

SEQ_ESPERADO = {}         
BUFFER_RECEBIMENTO = {}   
CLIENTES_CONECTADOS = set()
SEQ_ENVIO = {}
BROADCASTS_PENDENTES = {} 
lock = threading.Lock()

HISTORICO_CONVERSA = [] 
REPOSITORIO_ARQUIVOS = {} 

def formatar_mensagem(msg_dict):
    try:
        ts = time.strftime('%H:%M:%S', time.localtime(msg_dict.get('timestamp', time.time())))
        sender = msg_dict.get('sender', 'Anon')
        
        if msg_dict.get('type') == "file_chunk":
            info = msg_dict['message']
            return f"[{ts}] {sender} enviando: {info['filename']} ({info['chunk_index']+1}/{info['total_chunks']})"
            
        return f"[{ts}] {sender}: {msg_dict.get('message', '')}"
    except: 
        return "[Msg Malformada]"

def imprimir_historico():
    print(f"\n{C_MAGENTA}========== HISTÓRICO DE CONVERSA =========={C_RESET}")
    for msg in HISTORICO_CONVERSA: print(msg)
    print(f"{C_MAGENTA}==========================================={C_RESET}\n")

def processar_payload_arquivo(payload):
    if payload.get('type') == "file_chunk":
        info = payload['message']
        nome = info['filename']
        idx = info['chunk_index']
        total = info['total_chunks']
        conteudo_b64 = info['content']

        if nome not in REPOSITORIO_ARQUIVOS:
            REPOSITORIO_ARQUIVOS[nome] = [None] * total
        
        REPOSITORIO_ARQUIVOS[nome][idx] = conteudo_b64
        
        if all(f is not None for f in REPOSITORIO_ARQUIVOS[nome]):
            try:
                full_b64 = "".join(REPOSITORIO_ARQUIVOS[nome])
                bytes_finais = base64.b64decode(full_b64)
                
                # Salva o arquivo na pasta 'uploads/'
                pasta_destino = "uploads"
                os.makedirs(pasta_destino, exist_ok=True)
                
                caminho_arquivo = os.path.join(pasta_destino, nome)
                with open(caminho_arquivo, "wb") as f:
                    f.write(bytes_finais)
                
                msg_sucesso = f"{C_GREEN}[SISTEMA] Arquivo '{nome}' reconstruído no servidor em '{pasta_destino}/'{C_RESET}"
                HISTORICO_CONVERSA.append(msg_sucesso)
                del REPOSITORIO_ARQUIVOS[nome] 
            except Exception as e:
                HISTORICO_CONVERSA.append(f"{C_RED}[ERRO] Falha ao salvar arquivo no servidor: {e}{C_RESET}")

def enviar_ack(sock, seq_num, dst_vip):
    seg = Segmento(seq_num=seq_num, is_ack=True, payload={})
    pkt = Pacote(src_vip=MEU_VIP, dst_vip=dst_vip, ttl=5, segmento_dict=seg.to_dict())
    frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
    enviar_pela_rede_ruidosa(sock, frame.serializar(), ("127.0.0.1", 5000))

def broadcast_para_outros(sock, payload, remetente_vip):
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
                
                BROADCASTS_PENDENTES[destino][seq] = {
                    "bytes": bytes_envio,
                    "time": time.time(),
                    "tentativas": 1
                }
                
                enviar_pela_rede_ruidosa(sock, bytes_envio, ("127.0.0.1", 5000))

def monitor_timeouts_server(sock):
    while True:
        time.sleep(1)
        agora = time.time()
        with lock:
            for vip, pendentes in list(BROADCASTS_PENDENTES.items()):
                for seq, info in list(pendentes.items()):
                    if agora - info["time"] > 3.0:
                        info["tentativas"] += 1
                        info["time"] = agora
                        enviar_pela_rede_ruidosa(sock, info["bytes"], ("127.0.0.1", 5000))

def main():
    print(f"--- {MEU_VIP} (Chat Confiável + Reconstrução em /uploads) ---")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_ESCUTA))
    
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
                seq = segmento['seq_num']
                with lock:
                    if src_vip in BROADCASTS_PENDENTES and seq in BROADCASTS_PENDENTES[src_vip]:
                        del BROADCASTS_PENDENTES[src_vip][seq]
                continue

            seq_recebido = segmento['seq_num']
            
            if src_vip not in SEQ_ESPERADO:
                SEQ_ESPERADO[src_vip] = 0
                BUFFER_RECEBIMENTO[src_vip] = {}
                CLIENTES_CONECTADOS.add(src_vip)
            
            enviar_ack(sock, seq_recebido, src_vip)
            
            if seq_recebido == SEQ_ESPERADO[src_vip]:
                payload = segmento['payload']
                
                if payload.get('type') != 'hello':
                    HISTORICO_CONVERSA.append(formatar_mensagem(payload))
                    processar_payload_arquivo(payload) 
                    imprimir_historico()
                
                broadcast_para_outros(sock, payload, src_vip)
                SEQ_ESPERADO[src_vip] += 1
                
                while SEQ_ESPERADO[src_vip] in BUFFER_RECEBIMENTO[src_vip]:
                    payload_buf = BUFFER_RECEBIMENTO[src_vip].pop(SEQ_ESPERADO[src_vip])
                    if payload_buf.get('type') != 'hello':
                        HISTORICO_CONVERSA.append(formatar_mensagem(payload_buf))
                        processar_payload_arquivo(payload_buf)
                        imprimir_historico()
                    broadcast_para_outros(sock, payload_buf, src_vip)
                    SEQ_ESPERADO[src_vip] += 1
                    
            elif seq_recebido > SEQ_ESPERADO[src_vip]:
                if seq_recebido not in BUFFER_RECEBIMENTO[src_vip]:
                    BUFFER_RECEBIMENTO[src_vip][seq_recebido] = segmento['payload']

        except Exception as e: 
            pass

if __name__ == "__main__":
    main()