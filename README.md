# Integrantes e Matrícula do grupo
CLEIVER BATISTA DA SILVA JUNIOR - 202403899

FREDERICO BARBOSA RELVAS - 202403902

IGOR DIAS AGUIAR - 202403907 

# 🟢 WhatsFake: Emulação de Pilha de Protocolos

Este projeto consiste na implementação de uma rede emulada com quatro camadas (Aplicação, Transporte, Rede e Enlace) operando sobre o protocolo UDP. O sistema utiliza um simulador de canal físico que introduz **20% de probabilidade de perda** e **20% de corrupção de bits** para testar a resiliência dos protocolos.

## 🎥 Demonstração

https://github.com/igorgynIA/Redes_de_computadores/raw/main/midia/redes.mp4

*(Caso o player não carregue, [clique aqui para visualizar o vídeo](midia/redes.mp4))*

## 📋 Pré-requisitos

* **Python 3.x** instalado.
* Biblioteca **CustomTkinter** (`pip install customtkinter`).
* Todos os arquivos (`client.py`, `server.py`, `router.py`, `protocolo.py`, `main.py`) devem estar localizados no mesmo diretório.

## 🚀 Como Executar

Para facilitar o teste, utilize o script de automação que inicia todos os componentes na ordem correta:

1. **Terminal Único:** Execute o inicializador:
   ```bash
   python main.py

Na interface aberta após nomear o client.py, digite suas mensagens na área de texto e visualize as tentativas de comunicação da rede. Os logs em vermelho indicam erros como alteração dos bits e perda de pacotes, cor amarela indica a retransmissão dos pacotes e cor verde indica que o processo está andando conforme o planejado.

Essa interface é criada no estilo de bate-papo em grupo, de modo que todos os participantes tem acesso às mensagens, arquivos e emojis enviados pelos demais, assim como o horário de envio.
