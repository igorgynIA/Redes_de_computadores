import socket
from protocol import Quadro, enviar_pela_rede_ruidosa

# Cores para o terminal
C_RESET = "\033[0m"
C_RED = "\033[91m"    # Erros físicos/CRC
C_GREEN = "\033[92m"  # Mensagens de Aplicação
C_YELLOW = "\033[93m" # Retransmissões/Transporte
C_CYAN = "\033[96m"   # Controle/ACKs
C_MAGENTA = "\033[95m"# Roteamento

# Configurações de Rede
MY_ADDR = ("127.0.0.1", 5000)
# Tabela de Roteamento Estática: VIP -> (IP_Real, Porta_Real)
ROUTING_TABLE = {
    "HOST_A": ("127.0.0.1", 6001), # Porta onde o cliente vai ouvir
    "SERVIDOR_PRIME": ("127.0.0.1", 6000) # Porta onde o servidor ouve
}

def main():
    print(f"--- ROTEADOR ATIVO EM {MY_ADDR} ---")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(MY_ADDR)

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            quadro_dict, integro = Quadro.deserializar(data)
            
            if not integro:
                print(f"{C_RED}[ROUTER] Erro de CRC de {addr}. Descartando.{C_RED}")
                continue

            pacote = quadro_dict['data']
            dst_vip = pacote['dst_vip']
            ttl = pacote['ttl']

            # Lógica de Roteamento (Fase 3)
            if ttl <= 0:
                print(f"{C_RED}[ROUTER] TTL expirado para {dst_vip}. Descartando.{C_RED}")
                continue

            if dst_vip in ROUTING_TABLE:
                pacote['ttl'] -= 1 # Decremento do TTL
                proximo_no = ROUTING_TABLE[dst_vip]
                
                # Re-encapsula (Novo salto na camada de enlace)
                novo_quadro = Quadro(src_mac="ROUTER_MAC", dst_mac="NEXT_MAC", pacote_dict=pacote)
                
                print(f"{C_GREEN}[ROUTER] Encaminhando {dst_vip} para {proximo_no} (TTL: {pacote['ttl']}){C_GREEN}")
                enviar_pela_rede_ruidosa(sock, novo_quadro.serializar(), proximo_no)
            else:
                print(f"{C_RED}[ROUTER] VIP {dst_vip} desconhecido.{C_RED}")
                
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()