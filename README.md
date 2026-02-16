# 🌐 Mini-NET: Emulação de Pilha de Protocolos

Este projeto consiste na implementação de uma rede emulada com quatro camadas (Aplicação, Transporte, Rede e Enlace) operando sobre o protocolo UDP. O sistema utiliza um simulador de canal físico que introduz **20% de probabilidade de perda** e **20% de corrupção de bits** para testar a resiliência dos protocolos.

## 📋 Pré-requisitos

* **Python 3.x** instalado.
* Todos os arquivos (`client.py`, `server.py`, `router.py`, `protocolo.py`) devem estar localizados no mesmo diretório.

## 🚀 Como Executar

Para que a rede funcione corretamente, os terminais devem ser iniciados na ordem abaixo. Abra **três instâncias** do seu terminal:

1. **Terminal 1 (Servidor):** Destino final das mensagens e arquivos.
   ```bash
   python server.py

2. **Terminal 2 (Roteador):** Intermediário responsável pelo endereçamento lógico (VIP) e controle de salto (TTL).
   ```bash
   python router.py

3. **Terminal 3 (Cliente):** Interface gráfica (GUI) para interação do usuário.
   ```bash
   python client.py
