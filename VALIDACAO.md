# Validação desta versão

- Instalação de dependências Python: concluída em venv, Python 3.12.
- Instalação editável do projeto: concluída.
- `python -m unittest discover -s tests -v`: 21 testes, todos passaram.
- Interface Tkinter: aberta e encerrada em Xorg com driver dummy, 1280 × 900.
- `python -m tests.gui_smoke`: passou. Captura real desse desktop virtual,
  barra gerada de 25%, decisão de cura em simulação, salvamento e leitura
  de configuração temporária. Não enviou teclas.
- Negação de autorização, resposta antecipada do portal, liberação de tecla
  cancelada e foco ausente: cobertos por interfaces simuladas nos testes.
- Portal RemoteDesktop/ScreenCast, PipeWire, kdotool e integração com Bazzite:
  **não executados em uma sessão Wayland real**.
- Aion 2/Steam, seleção de membros e lançamento real de curas: **não testados**.

O resultado é um protótipo para calibração e teste local, não uma confirmação de
automação funcional dentro do Aion 2. O ambiente de desenvolvimento Python está
preparado; a integração de desktop depende dos componentes descritos no README.
