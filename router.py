import socket
from protocol import Quadro, enviar_pela_rede_ruidosa

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
                print(f"[ROUTER] Erro de CRC de {addr}. Descartando.")
                continue

            pacote = quadro_dict['data']
            dst_vip = pacote['dst_vip']
            ttl = pacote['ttl']

            # Lógica de Roteamento (Fase 3)
            if ttl <= 0:
                print(f"[ROUTER] TTL expirado para {dst_vip}. Descartando.")
                continue

            if dst_vip in ROUTING_TABLE:
                pacote['ttl'] -= 1 # Decremento do TTL
                proximo_no = ROUTING_TABLE[dst_vip]
                
                # Re-encapsula (Novo salto na camada de enlace)
                novo_quadro = Quadro(src_mac="RT_01", dst_mac="SV_01", pacote_dict=pacote)
                
                print(f"[ROUTER] Encaminhando {dst_vip} para {proximo_no} (TTL: {pacote['ttl']})")
                enviar_pela_rede_ruidosa(sock, novo_quadro.serializar(), proximo_no)
            else:
                print(f"[ROUTER] VIP {dst_vip} desconhecido.")
                
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()