import socket

# Configuração
PORTA_ROUTER = 5000
BUFFER_SIZE = 4096

def main():
    print(f"--- ROTEADOR INICIADO NA PORTA {PORTA_ROUTER} ---")
    print("(Aviso: Lógica de roteamento será implementada na Fase 3)")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_ROUTER))

    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            print(f"[ROUTER] Recebido {len(data)} bytes de {addr}. (Descartado - Fase 1)")
            # Na Fase 3, aqui leremos o 'dst_vip' do pacote e encaminharemos
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()