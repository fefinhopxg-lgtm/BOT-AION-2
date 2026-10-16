# BOT-AION-2 — assistente de cura visual

Primeira versão de um aplicativo desktop para configurar até seis barras de vida,
medir sua área colorida e escolher membro e cura por vida restante. Interface em
português, simulação, recargas, intervalo entre ações e verificação de foco.
Steam é o lançador; o programa não usa API nem memória do Aion 2.

**Estado:** decisões e leitura de imagens são testáveis na nuvem. Integração com
Bazzite/Wayland, layout do Aion 2, teclas aceitas pelo jogo e curas reais ainda
precisam de validação no computador do jogador. Enviar uma tecla não confirma
que uma habilidade foi lançada: alcance, mana, seleção, conjuração e recarga do
jogo não são reconhecidos nesta versão. Confira as regras do jogo sobre automação.

## Bazzite com Wayland

O backend usa `xdg-desktop-portal` RemoteDesktop + ScreenCast, captura PipeWire e
teclado autorizado pelo compositor. Ao abrir a captura, autorize teclado e
compartilhe **um monitor**, aquele onde o jogo está. Não precisa executar como root.
O programa solicita a sessão com teclado inclusive para calibração/simulação,
mas o modo de simulação não envia eventos de teclado.

Requisitos do desktop:

- Python 3.10+ com Tkinter, venv, PyGObject (`gi`).
- GStreamer 1.0, introspecção Gst/GstVideo, plugins PipeWire e videoconvert.
- PipeWire, portal e backend do compositor com RemoteDesktop e ScreenCast.
- Para envio automático em Wayland: **KDE Plasma 6 e `kdotool`** no PATH, usado
  para identificar o processo da janela ativa. GNOME Wayland não tem integração
  de foco implementada: use apenas simulação nesta versão.

Diagnóstico no terminal do desktop (não no contêiner de desenvolvimento):

```bash
python3 -c 'import tkinter, gi; gi.require_version("Gst", "1.0"); from gi.repository import Gst, GstVideo; print("Bibliotecas disponíveis")'
gst-inspect-1.0 pipewiresrc
kdotool getactivewindow getwindowpid
```

Bazzite tem uma base imutável: não use `apt` nem instale dependências de desktop
em um venv esperando substituir bibliotecas do sistema. Componentes ausentes
devem ser instalados pelo mecanismo suportado pela sua edição do Bazzite.
As dependências nativas e permissões do portal precisam estar disponíveis no
ambiente que executa o aplicativo; um contêiner isolado não garante isso.
Documentação do kdotool: https://github.com/jinliu/kdotool

Extraia a pasta em `~/Desktop` ou `~/Área de Trabalho`, abra um terminal nela:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
bash iniciar.sh
```

O venv usa pacotes de sistema para acessar `gi`; ele não copia bibliotecas nem
instala pacotes na base do Bazzite. A localização da área de trabalho pode ser
consultada com `xdg-user-dir DESKTOP`. O ambiente em nuvem não grava no seu PC.

## Configurar e testar

1. Abra o jogo em janela sem borda, com equipe e barras visíveis. Use um monitor
   e escala de **100%** na calibração inicial; escalas diferentes e configurações
   de múltiplos monitores não foram validadas.
2. Com vida cheia, clique em **Selecionar** na linha do membro. Autorize o portal
   se solicitado; quando aparecer a imagem, arraste apenas o interior da barra,
   sem texto, bordas, retratos ou outros indicadores. Escape cancela a seleção.
3. Configure a tecla real para selecionar esse membro. `f1`…`f6` são exemplos,
   não mapeamentos confirmados do jogo. Membros sem seleção ficam desativados.
4. Ajuste as três regras, teclas de cura e recargas. Os padrões são exemplos:
   30% restante (70% perdido) → `1`; 60% → `2`; 80% → `3`. Sempre confira suas
   habilidades. O menor limite aplicável tem prioridade; se em recarga, tenta
   outra regra. O membro com menor vida válida é priorizado.
5. Deixe **Simulação** marcada, inicie e compare as porcentagens do registro com
   as barras reais. Pare antes de mudar qualquer configuração. Alterações feitas
   durante execução só valem na próxima inicialização.
6. Clique em detectar processo e então clique no jogo em até quatro segundos.
   Confira o nome detectado. O envio exige correspondência exata com o processo
   da janela ativa; Alt+Tab para outra janela suspende o envio.
7. Só depois de conferir as leituras e teclas, pare, desmarque simulação e inicie.
   Use **Parar** ou encerre o compartilhamento pela interface do desktop para
   interromper. Em X11 também vale o failsafe do PyAutoGUI (mouse no canto).

Salvar grava apenas as configurações em `~/.config/aion-healer/config.json`.
O modo de simulação volta ativado a cada abertura; o programa não inicia sozinho.
Se o portal for encerrado, feche e reabra o aplicativo para solicitar nova sessão.

## Limites da leitura visual

A estimativa requer barra de preenchimento contínuo da esquerda para a direita,
cor estável e fundo distinto. Barra vazia, cor incorreta ou fragmentação relevante
gera "sem leitura" e não seleciona aquele membro. A cor é calibrada pela mediana
da região cheia e usa tolerância RGB fixa; gradientes, mudanças de cor por vida,
escudos, texto sobreposto, animações e outras janelas podem distorcer a leitura.
Não é uma integração específica com a interface do Aion 2. Valide em simulação
após mudar resolução, escala, HUD ou tema. Não há detecção de morte/ressurreição,
alcance, mana, alvo selecionado ou confirmação de lançamento.

O controle de foco consulta o compositor antes da seleção e da cura; ainda existe
uma pequena janela entre consulta e envio em que a janela ativa pode mudar.
Não use enquanto alterna entre o jogo e outros aplicativos sensíveis.

## Desenvolvimento na nuvem

```bash
cd /workspace/BOT-AION-2
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Em um desktop X11 isolado com pelo menos 1000 × 720 pixels, também é possível
executar `.venv/bin/python -m tests.gui_smoke`. Esse teste abre uma barra artificial
e verifica captura, decisão em simulação e persistência, sem enviar teclas.
Use um perfil de usuário sem configuração anterior para esse teste. Resultados
da validação desta versão estão em [VALIDACAO.md](VALIDACAO.md).

Não há servidor nem credenciais a configurar. Para abrir a interface execute
`.venv/bin/python -m aion_healer.app` em um desktop. A captura Wayland e o envio
de teclas exigem sessão gráfica com consentimento, não disponíveis em uma tarefa
de nuvem sem compositor. Testes usam imagens geradas e interfaces simuladas;
não provam compatibilidade com o jogo, portal ou drivers da máquina do jogador.
