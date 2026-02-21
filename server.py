import socket
import time
import os
import base64  # Necessário para decodificar os fragmentos do arquivo
from protocol import Segmento, Pacote, Quadro, enviar_pela_rede_ruidosa

C_RESET = "\033[0m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"
C_RESET = "\033[0m"

MEU_VIP = "SERVIDOR_PRIME"

PORTA_ESCUTA = 6000
BUFFER_SIZE = 50000

SEQ_ESPERADO = 0
BUFFER_RECEBIMENTO = {} 
HISTORICO_CONVERSA = [] 
REPOSITORIO_ARQUIVOS = {} # Armazena fragmentos: { "foto.png": [chunk0, chunk1, ...] }

def formatar_mensagem(msg_dict):
    try:
        ts = time.strftime('%H:%M:%S', time.localtime(msg_dict.get('timestamp', time.time())))
        sender = msg_dict.get('sender', 'Anon')
        
        # Se for um fragmento de arquivo, formatamos o log de progresso
        if msg_dict.get('type') == "file_chunk":
            info = msg_dict['message']
            return f"[{ts}] {sender} enviando: {info['filename']} ({info['chunk_index']+1}/{info['total_chunks']})"
        
        return f"[{ts}] {sender} diz: {msg_dict.get('message', '')}"
    except Exception as e:
        return f"[Erro ao formatar: {e}]"

def processar_payload(payload):
    """
    Decide o que fazer com o dado: se for chat, vai para o histórico;
    se for fragmento, vai para a reconstrução do arquivo.
    """
    if payload.get('type') == "file_chunk":
        info = payload['message']
        nome = info['filename']
        idx = info['chunk_index']
        total = info['total_chunks']
        conteudo_b64 = info['content']

        # Inicializa a lista de fragmentos se for o primeiro que chega deste arquivo
        if nome not in REPOSITORIO_ARQUIVOS:
            REPOSITORIO_ARQUIVOS[nome] = [None] * total
        
        # Salva o fragmento na posição correta (garante reordenação)
        REPOSITORIO_ARQUIVOS[nome][idx] = conteudo_b64
        
        HISTORICO_CONVERSA.append(formatar_mensagem(payload))
        
        # Verifica se todos os fragmentos chegaram
        if all(f is not None for f in REPOSITORIO_ARQUIVOS[nome]):
            try:
                # Junta tudo e decodifica
                full_b64 = "".join(REPOSITORIO_ARQUIVOS[nome])
                bytes_finais = base64.b64decode(full_b64)
                
                with open(f"recebido_{nome}", "wb") as f:
                    f.write(bytes_finais)
                
                msg_sucesso = f"{C_GREEN}[SISTEMA] Arquivo '{nome}' reconstruído com sucesso!{C_RESET}"
                HISTORICO_CONVERSA.append(msg_sucesso)
                del REPOSITORIO_ARQUIVOS[nome] # Limpa memória
            except Exception as e:
                HISTORICO_CONVERSA.append(f"{C_RED}[ERRO] Falha ao salvar arquivo: {e}{C_RESET}")
    else:
        # Mensagem de texto normal
        HISTORICO_CONVERSA.append(formatar_mensagem(payload))

def enviar_ack(sock, addr, seq_num, dst_vip):
    seg = Segmento(seq_num=seq_num, is_ack=True, payload={})
    pkt = Pacote(src_vip=MEU_VIP, dst_vip=dst_vip, ttl=5, segmento_dict=seg.to_dict())
    frame = Quadro(src_mac="SERVR", dst_mac="CLIEN", pacote_dict=pkt.to_dict())
    enviar_pela_rede_ruidosa(sock, frame.serializar(), ("127.0.0.1", 5000))

def imprimir_historico():
    """Imprime a conversa completa no terminal para monitoramento"""
    print(f"\n{C_MAGENTA}========== HISTÓRICO DE CONVERSA =========={C_RESET}")
    for msg in HISTORICO_CONVERSA:
        print(msg)
    print(f"{C_MAGENTA}==========================================={C_RESET}\n")

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
                # Corrigido o reset de cor para C_RESET
                print(f"{C_RED}[ERRO] CRC Falhou. Descartado.{C_RESET}")
                continue

            pacote = quadro_dict['data']
            segmento = pacote['data']
            seq_recebido = segmento['seq_num']
            
            # 1. Envia ACK imediatamente (Protocolo de ACKs sequenciais)
            enviar_ack(sock, addr, seq_recebido, pacote['src_vip'])
            
            # 2. Lógica de Entrega Ordenada
            if seq_recebido == SEQ_ESPERADO:
                print(f"{C_GREEN}[ARQ] Recebido SEQ {seq_recebido} (Na ordem).{C_RESET}")
                
                processar_payload(segmento['payload'])
                imprimir_historico()
                SEQ_ESPERADO += 1
                
                # 3. Descarrega o buffer de pacotes que chegaram antes mas estavam esperando este
                while SEQ_ESPERADO in BUFFER_RECEBIMENTO:
                    print(f"{C_CYAN}[ARQ] Processando SEQ {SEQ_ESPERADO} do buffer.{C_RESET}")
                    payload_acumulado = BUFFER_RECEBIMENTO.pop(SEQ_ESPERADO)
                    processar_payload(payload_acumulado)
                    imprimir_historico()
                    SEQ_ESPERADO += 1
                    
            elif seq_recebido > SEQ_ESPERADO:
                if seq_recebido not in BUFFER_RECEBIMENTO:
                    print(f"{C_YELLOW}[ARQ] SEQ {seq_recebido} fora de ordem. Guardando no buffer.{C_RESET}")
                    BUFFER_RECEBIMENTO[seq_recebido] = segmento['payload']
            else:
                print(f"{C_YELLOW}[ARQ] Duplicata do SEQ {seq_recebido} ignorada.{C_RESET}")

        except Exception as e:
            print(f"Erro crítico: {e}")

if __name__ == "__main__":
    main()