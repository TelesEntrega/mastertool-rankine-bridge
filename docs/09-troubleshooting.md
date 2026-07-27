# Solução de problemas

## Scripts internos (MasterTool)

### "Nenhum global do ScriptEngine encontrado"
- O script foi executado fora do MasterTool (ex.: python do Windows). Os
  scripts 00-03 só funcionam pelo menu de scripting do MasterTool.
- Se ocorreu DENTRO do MasterTool: registre em `docs/03-scripting-discovery.md`;
  o host pode injetar globais com outros nomes — a saída do script lista o que
  encontrou.

### "Projeto primário NAO encontrado"
- Nenhum projeto aberto → abra um projeto e re-execute.
- `projects` existe mas sem `primary` → o smoke test imprime os membros
  disponíveis; registrar em `docs/api/mastertool-api-observations.md`.

### Erro de sintaxe ao carregar o script
- Provável incompatibilidade IronPython 2.7 (f-string, pathlib etc.).
  Isso é bug nosso: os scripts internos devem ser 2.7-compatíveis — reportar.

### Acentos corrompidos na saída
- IronPython + console Windows. Os arquivos gerados são UTF-8; confie nos
  arquivos, não no painel. Evitar acentos em caminhos do repositório ajuda.

### Log não é criado em workspace/logs
- Se `__file__` não estiver disponível no host, o script usa o diretório de
  trabalho atual e imprime um `[WARN]` com o caminho usado.

## Camada externa

### `mastertool-bridge: command not found`
- Ative o venv e rode `pip install -e .`, ou use `python -m mastertool_bridge`.

### `validate-export` falha com "Manifesto não encontrado"
- O diretório apontado não é um export completo (os scripts 01-03 da Fase 0
  geram apenas artefatos de descoberta; o manifesto completo virá com o
  `04_export_project.py` na segunda entrega).

### `SafetyPolicyViolation`
- Comportamento correto (fail closed): a operação exige feature desabilitada
  ou viola `config/safety-policy.yaml`. Não contorne; discuta a habilitação.
