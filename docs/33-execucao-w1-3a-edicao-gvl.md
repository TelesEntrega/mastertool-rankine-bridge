# W1.3A — execução da edição textual de GVL

> Registro de execução, não plano. O contrato está em
> [`docs/31`](31-plano-w1-3-escrita-textual-controlada.md); o que segue é o que
> foi **medido** em 2026-07-31, com os números congelados para servir de
> baseline às fases seguintes.

## 1. Veredito

### `replace` sobre `IScriptTextDocument` cria texto que sobrevive a `save_as` e a uma reabertura independente

A capacidade está provada: o MasterTool X aceita substituição do documento
textual de uma GVL já existente por script, persiste o resultado em um arquivo
novo e devolve o mesmo texto quando o arquivo é reaberto em outra sessão. A
árvore não mudou — nenhum objeto foi acrescentado ou removido.

O que **não** está provado por esta execução: que o texto **compila**. W1.3A
verifica persistência, não semântica. O `build` entra em
[W1.4](32-plano-w1-4-integracao-e-build.md), e essa separação é deliberada —
um erro de compilação sobre texto corretamente persistido seria achado sobre o
conteúdo, não sobre a capacidade de escrever.

## 2. Cadeia de evidência

A sessão é `run-008`, precedida por um `PreflightOnly` isolado em `run-007`.

| Etapa | Modo | Projeto aberto | Artefato | Status |
| --- | --- | --- | --- | --- |
| 1 | `ValidateOnly` | nenhum | — | validação aprovada, nada aberto |
| 2 | preflight | cópia de trabalho | `w1-3a-preflight-completion.json` | `preflight_passed` |
| 3 | mutação | cópia de trabalho | `completion.json` | `saved_as` |
| 4 | postsave | **`W1-A3.project`** | `w1-3a-postsave-completion.json` | `postsave_verified` |

<caption>

**Como ler:** cada linha é um lançamento separado do `MT9000.exe`. A etapa 4
abre um arquivo **diferente** das etapas 2 e 3 — é isso que torna a
verificação independente: o texto é lido de volta de um processo novo, sobre o
arquivo salvo, sem nenhum estado em memória herdado da mutação.

</caption>

O veredito da sessão nunca vem do código de saída do launcher, que foi `0` nas
três execuções e não significa nada: quem decide é o **artefato de conclusão**
gravado pelo probe.

## 3. Números medidos

| Grandeza | Valor |
| --- | --- |
| Entrada (fixture imutável) | `W1-A1.project`, 287.824 bytes |
| SHA-256 da entrada, antes e depois | `a0460e8272b8e48604daedaebe3c20776daa0fd949f4ebdb12d242460dbe0614` |
| Saída | `W1-A3.project`, 288.256 bytes |
| SHA-256 da saída | `f7d9d81977e1a07808b7cc45d12dd13e4b4aa471694022e0e7152d3ebc9847a1` |
| Texto inicial (SHA-256) | `fd27fd816bdf9d2116403f691bcb84694119b3553b1067619bb9b96dd310affb` |
| Texto final (SHA-256) | `71f8079f6a8106315d4d5931ddd3fb247ad17c1fff374dbf6cdf79dd261a017c` |
| Container | `root/1/0/0`, `Application` |
| Filhos do container, antes e depois | 9 |
| Duração das três execuções | 20,1 s · 22,2 s · 19,1 s |

<caption>

**Como ler:** o SHA-256 da entrada aparece uma vez só porque é o **mesmo**
antes e depois — a cópia de trabalho não foi tocada por `save_as`, que escreve
em arquivo novo. `W1-A3.project` é 432 bytes maior que a entrada, e essa
diferença é o único efeito da sessão.

</caption>

Texto persistido, lido de `W1-A3.project` reaberto:

```iecst
{attribute 'qualified_only'}
VAR_GLOBAL
    g_xTesteCriacao : BOOL;
END_VAR
```

## 4. Critérios de aceitação, um a um

| Critério | Evidência | Resultado |
| --- | --- | --- |
| exatamente um `replace` | `journal.jsonl`, sequências 2–3 | 1 |
| exatamente um `save_as` | `journal.jsonl`, sequências 5–6 | 1 |
| nenhuma alteração estrutural | `structural_diff`: quatro listas vazias | confirmado |
| nenhuma outra GVL modificada | 9 filhos antes e depois; `GVL_AI_TESTE` único no container | confirmado |
| entrada intacta | SHA-256 idêntico antes e depois | confirmado |
| saída nova | `output_exists: false → true` no journal | confirmado |
| zero diálogos | `timed_out: false` nas três execuções | confirmado |
| zero órfãos | `orphan_ids: []` nas três; 0 processos ao final | confirmado |

<caption>

**Como ler:** cada critério aponta para um artefato gravado **pelo probe
dentro do MasterTool**, não para a saída do host. O host observa; o probe
mede. `timed_out: false` é a evidência de ausência de diálogo, porque um
diálogo aberto impede a janela de fechar e estoura o tempo — a ausência de
diálogo é inferida do fechamento limpo, não de alguém ter olhado a tela.

</caption>

`operations_executed == operations_requested == operations_authorized ==
["replace", "save_as"]`, e `no_other_mutator_requested: true`. As três listas
coincidirem é o que separa "fez o que foi pedido" de "fez o que foi pedido e
nada além".

## 5. O que a execução acrescentou ao conhecimento

**A árvore não muda quando só o texto muda.** O container tinha 9 filhos antes
do `replace` e 9 depois — registrado no journal como `state_before` e
`state_after`. Isso confirma que edição textual e criação de objeto são
efeitos disjuntos na API, e não duas faces da mesma operação.

**`save_as` não toca a entrada.** A cópia de trabalho manteve o SHA-256
original depois de uma sessão que a abriu, mutou em memória e salvou. A
mutação vive no arquivo de destino, e o arquivo de origem sai da sessão como
entrou — o que torna a cópia descartável reutilizável como evidência, e não
apenas como insumo.

**O pragma `qualified_only` sobrevive à substituição.** O texto final o
mantém, porque o `replace` recebe o documento inteiro e o texto canônico o
inclui. Isso importa para W1.4: a referência `GVL_AI_TESTE.g_xTesteCriacao`
continuará **obrigatoriamente** qualificada.

## 6. Defeito encontrado pela execução

`session-verdict.json` era gravado com `Out-File -Encoding utf8`, que no
PowerShell 5.1 escreve BOM. Ler o veredito de volta falhou com
`Unexpected UTF-8 BOM`. Os **quatro** wrappers de W1 tinham a mesma linha.
Corrigido em `bc23d4b`, com teste que varre o diretório em vez de uma lista
fixa.

O achado importa além do conserto: **2.220 testes passaram com o defeito no
lugar**, porque nenhum olhava a codificação do que o wrapper grava — só o que
ele decide. Um artefato que o próprio pipeline não consegue ler é evidência
que não pode ser consumida.

O `session-verdict.json` de `run-008` **continua com BOM**: é registro
histórico de uma execução feita com o código antigo, e reescrevê-lo seria
falsificar o registro. Foi lido com `utf-8-sig` na verificação.

## 7. Limites

**O que a evidência comprova:** que `replace` sobre `IScriptTextDocument`
persiste texto em uma GVL existente, através de `save_as`, e que o texto
sobrevive a uma reabertura independente sem alterar a árvore.

**O que exige medição em campo, e que esta execução não responde:**

- **Se o texto compila.** Nenhum `build` foi executado. Pertence a W1.4.
- **Se o mesmo vale sobre a base nova.** A entrada `W1-A1.project` descende do
  projeto-base **anterior**, sem cartões de I/O. O `node_path root/1/0/0` foi
  confirmado **para esta árvore**, e não para o `TemplateExemplo v1.project`. W1.4 parte da
  base nova e precisa de varredura própria (`probes/21`) antes de qualquer
  execução — um índice deslocado faria o preflight abortar em
  `container_not_found`, comportamento certo por motivo evitável.
- **Se `insert` e `append` funcionam.** Não foram chamados e continuam fora de
  qualquer allowlist. A capacidade provada é `replace`, e só ela.
- **Se vale para documento de implementação.** A GVL tem um documento; um
  PROGRAM tem dois. É o objeto de W1.3B, que segue preparado e bloqueado.
- **Se a ausência de diálogo é geral.** Ela foi inferida de três fechamentos
  limpos nesta sessão, com esta cópia. Não é propriedade do MasterTool.

## 8. Estado ao fim de W1.3A

A fase `W1_3A_EDIT_GVL` foi **encerrada** em commit próprio:
`CONTROLLED_WRITE_PHASE` volta a `None` e nenhuma escrita fica autorizada. A
entrada permanece no mapa de allowlists como registro histórico — estar no
mapa não autoriza nada.

`W1_3B_EDIT_PROGRAM` continua fechada, e só abre em decisão separada. Duas
fases mutáveis abertas ao mesmo tempo é o que o desenho de fase única existe
para impedir.
