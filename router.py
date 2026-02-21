import socket
from protocol import Quadro, enviar_pela_rede_ruidosa

C_RESET = "\033[0m"
C_RED = "\033[91m"    
C_GREEN = "\033[92m"  
C_CYAN = "\033[96m"   

MY_ADDR = ("127.0.0.1", 5000)

# Tabela dinâmica: Conhece apenas o Servidor no início
ROUTING_TABLE = {
    "SERVIDOR_PRIME": ("127.0.0.1", 6000)
}

def main():
    print(f"--- ROTEADOR ATIVO EM {MY_ADDR} ---")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(MY_ADDR)

    while True:
        try:
            data, addr = sock.recvfrom(50000)
            quadro_dict, integro = Quadro.deserializar(data)
            
            if not integro:
                continue # Descarta silenciosamente se falhar o CRC

            pacote = quadro_dict['data']
            src_vip = pacote['src_vip']
            dst_vip = pacote['dst_vip']
            ttl = pacote['ttl']

            # --- APRENDIZADO DE ROTA ---
            # Se é um cliente novo, grava o IP e a Porta dele na tabela
            if src_vip not in ROUTING_TABLE and src_vip != "SERVIDOR_PRIME":
                ROUTING_TABLE[src_vip] = addr
                print(f"{C_CYAN}[ROUTER] Aprendi rota para {src_vip}: Porta {addr[1]}{C_RESET}")

            if ttl <= 0:
                print(f"{C_RED}[ROUTER] TTL expirado para {dst_vip}. Descartando.{C_RESET}")
                continue

            # Encaminhamento
            if dst_vip in ROUTING_TABLE:
                pacote['ttl'] -= 1 
                proximo_no = ROUTING_TABLE[dst_vip]
                
                novo_quadro = Quadro(src_mac="RT_01", dst_mac="SV_01", pacote_dict=pacote)
                print(f"{C_GREEN}[ROUTER] Encaminhando de {src_vip} para {dst_vip}{C_RESET}")
                enviar_pela_rede_ruidosa(sock, novo_quadro.serializar(), proximo_no)
            else:
                print(f"{C_RED}[ROUTER] VIP {dst_vip} desconhecido.{C_RESET}")
                
        except Exception:
            pass

if __name__ == "__main__":
    main()