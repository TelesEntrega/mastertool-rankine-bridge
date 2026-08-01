# W1.3B — execução da edição textual de PROGRAM ST

> Registro de execução, não plano. O contrato está em
> [`docs/31`](31-plano-w1-3-escrita-textual-controlada.md); o precedente de um
> documento só está em [`docs/33`](33-execucao-w1-3a-edicao-gvl.md). O que
> segue é o que foi **medido** em 2026-07-31, na `run-009`.

## 1. Veredito

### Os dois documentos de um PROGRAM são editáveis na mesma sessão, e ambos persistem

`replace` aplicado à declaração **e** à implementação do mesmo `PROGRAM`,
seguido de um único `save_as`, produz um arquivo cujo reabrir independente
devolve os dois textos exatos. A árvore não mudou.

Isso fecha a lacuna que W1.3A não podia fechar: lá havia um documento, e o
estado "um gravado e o outro não" era logicamente impossível. Aqui ele era
possível — e não ocorreu.

**Dois dos quinze critérios não foram verificados.** Não falharam: não há
evidência de nenhum lado. Estão na §6, nomeados, e a §7 explica por que um
deles é hoje inverificável com a superfície de API catalogada.

## 2. Cadeia de evidência

| Etapa | Modo | Projeto aberto | Status |
| --- | --- | --- | --- |
| 1 | `ValidateOnly` | nenhum | validação aprovada, nada aberto |
| 2 | preflight | cópia de trabalho | `preflight_verified` |
| 3 | mutação | cópia de trabalho | `saved_as` |
| 4 | postsave | **`W1-A4.project`** | `postsave_verified` |

<caption>

**Como ler:** cada linha é um lançamento separado do `MT9000.exe`. A etapa 4
abre arquivo **diferente** das etapas 2 e 3 — é isso que torna a verificação
independente. O código de saída do launcher foi `0` nas três execuções e não
decidiu nada: quem decide é o artefato de conclusão gravado pelo probe.

</caption>

## 3. Números medidos

| Grandeza | Valor |
| --- | --- |
| Entrada (fixture imutável) | `W1-A2.project`, `67092e58…a1e2a1` |
| SHA-256 da entrada, antes e depois | idêntico — `67092e58…a1e2a1` |
| Saída | `W1-A4.project`, 288.656 bytes, `b220611e…a2076176` |
| Declaração, antes → depois | `6a2401fa…435841` → `6e4b13ab…dfa80f5` |
| Implementação, antes → depois | `e3b0c442…7852b855` → `313cdb1f…1347d517` |
| Container | `root/1/0/0`, `Application` |
| Filhos do container, antes e depois | 9 |
| Duração das três execuções | 25,9 s · 29,3 s · 33,0 s |

<caption>

**Como ler:** os hashes "antes" não são suposição — foram lidos pelo preflight
**nesta sessão**, sobre esta cópia, e coincidem com os congelados em W1.2.
`e3b0c442…7852b855` é o SHA-256 da **string vazia**: a implementação de um
PROGRAM recém-criado nasce vazia, e é isso que o valor significa.

</caption>

Textos persistidos, lidos de `W1-A4.project` reaberto:

```iecst
PROGRAM PRG_AI_TESTE
VAR
    xLocal : BOOL;
END_VAR
```

```iecst
xLocal := FALSE;
```

## 4. As três mutações, na ordem

```text
seq 2-3  replace  declaration_document      probes/34::replace_declaration_guarded
seq 4    verificação intermediária (o texto novo está lá, em memória)
seq 5-6  replace  implementation_document   probes/34::replace_implementation_guarded
seq 7    verificação intermediária
seq 8-9  save_as  project                   probes/34::save_as_guarded
```

Cada `mutation_attempt` é gravado **antes** do efeito e cada `mutation_done`
**depois**. Uma exceção entre os dois deixaria no journal um `attempt` sem
`done` — que é a assinatura de "a cópia está em estado desconhecido, descarte".
Não ocorreu.

`operations_executed == operations_requested == operations_authorized`, e
`no_other_mutator_requested: true`.

## 5. Critérios de aceitação verificados

| Critério | Evidência | Resultado |
| --- | --- | --- |
| duas substituições no journal | seq. 2–3 e 5–6 | 2 |
| um `save_as` | seq. 8–9 | 1 |
| entrada byte a byte intacta | SHA-256 idêntico antes e depois | confirmado |
| output novo | `output_exists: false → true` | confirmado |
| reabertura independente | processo separado sobre `W1-A4.project` | confirmado |
| declaração persistida | `6e4b13ab…dfa80f5` no arquivo reaberto | confirmado |
| implementação persistida | `313cdb1f…1347d517` no arquivo reaberto | confirmado |
| type GUID inalterado | `6f9dac99…443b7d08` antes e depois | confirmado |
| árvore estrutural inalterada | 9 filhos; cinco listas de diff vazias; **segunda leitura independente** dos arquivos de árvore crus | confirmado |
| zero diálogos | `timed_out: false` nas três | confirmado |
| zero órfãos | `orphan_ids: []` nas três; 0 processos ao final | confirmado |
| veredito JSON sem BOM | primeiros bytes `123 13 10`; abre com `utf-8` estrito | confirmado |
| completion válida | `status: saved_as`, `errors: []` | confirmado |

<caption>

**Como ler:** "segunda leitura independente" quer dizer que a igualdade da
árvore foi recalculada fora do probe, a partir dos arquivos de varredura crus.
O `structural_diff` do próprio probe também diz "nada mudou", mas um diff
calculado pelo mesmo código que fez a mutação é testemunha de si mesmo.

</caption>

## 6. Os dois critérios NÃO verificados

### `nenhum outro PROGRAM alterado` — verificado só um nível

`enumerate_children` usa `container.get_children(False)`: **apenas filhos
diretos**. A comparação cobre os 9 filhos do `Application`, entre eles
`PRG_AI_TESTE`. Os POUs que vivem **dentro** de `UserPOUs` e `SystemPOUs` não
entraram na comparação.

O que sustenta a afirmação mais fraca, e verdadeira: nenhum objeto entrou,
saiu ou trocou de `type_guid` no nível do `Application`, e as três mutações do
journal têm por receptor os dois documentos de `PRG_AI_TESTE` e o projeto.
Para afirmar o critério como escrito seria preciso varredura recursiva —
`probes/21` já a implementa, com limite de profundidade e de nós.

### `linguagem continua ST` — inverificável hoje, e não apenas esquecido

Nenhum dos dois probes lê a linguagem do objeto em runtime. Pior: `probes/33`
**define** `EXPECTED_ST_LANGUAGE_GUID` e **nunca a usa** — constante morta.
Uma constante que aparenta verificar algo e não verifica é pior que ausente,
porque lê como cobertura. Em `probes/34` o GUID é usado apenas para conferir
que o valor **declarado no plano** coincide com a constante do módulo; isso
valida o plano, não o objeto.

A causa raiz não é descuido de instrumentação. **A superfície catalogada não
oferece leitura de linguagem**: `docs/27` registra `language` como parâmetro
de **entrada** de `create_pou`/`create_program`/`create_function`/
`create_function_block`, e `IScriptImplementationLanguages` como fonte de
`Guid` por linguagem. Não há propriedade catalogada que devolva a linguagem de
um objeto existente. Ler de volta exigiria API não catalogada, e inventar API
é proibido por contrato.

O caminho certo não é forçar essa leitura: é o **`build` de W1.4**. ST que
compila é ST, e isso prova mais do que um rótulo conferido.

## 7. O que a execução acrescentou ao conhecimento

**Dois documentos, uma persistência.** As duas edições foram para o mesmo
`save_as`. O modelo é "documento mutado em memória, projeto persistido de uma
vez", e não "cada documento se salva". Isso importa para W1.4, onde serão
cinco mutações antes de um único `save_as`.

**A verificação intermediária entre as duas edições funcionou.** Depois de
editar a declaração, o probe releu e conferiu antes de tocar na implementação
(seq. 4). É esse passo que torna distinguíveis "a primeira falhou" e "a
segunda falhou" — sem ele, um texto divergente no fim não diria qual.

**A correção do BOM foi validada em campo.** `bc23d4b` mudou os quatro
wrappers para `UTF8Encoding($false)`; esta foi a primeira execução real depois
disso, e o `session-verdict.json` abriu com `utf-8` estrito. Em `run-008` o
mesmo arquivo exigia `utf-8-sig`.

## 8. Limites

**O que a evidência comprova:** que os dois documentos textuais de um `PROGRAM`
existente podem ser substituídos na mesma sessão por `replace`, persistidos por
um único `save_as`, e recuperados idênticos em reabertura independente, sem
alteração estrutural no nível do `Application`.

**O que exige medição em campo:**

- **Se o texto compila.** Nenhum `build` foi executado. É W1.4.
- **Se a linguagem continua ST.** Inverificável com a API catalogada (§6).
  Descobrir se existe leitura de linguagem é reconhecimento read-only próprio,
  e não deve ser feito por tentativa dentro de uma fase mutável.
- **Se nenhum POU aninhado mudou.** Exige varredura recursiva (§6).
- **Se vale sobre a base nova.** `W1-A2.project` descende do projeto-base
  **anterior**, sem cartões de I/O. `root/1/0/0` foi confirmado **para esta
  árvore**. W1.4 parte do `TemplateExemplo v1.project` e exige qualificação própria.
- **Se `insert`, `append` e `replace_line` funcionam.** Não foram chamados e
  seguem fora de toda allowlist.

## 9. Estado ao fim de W1.3B

A fase `W1_3B_EDIT_PROGRAM` foi **encerrada** em commit próprio:
`CONTROLLED_WRITE_PHASE` volta a `None`. A entrada permanece no mapa como
registro histórico — estar no mapa não autoriza nada.

Com W1.1, W1.2, W1.3A e W1.3B encerrados, **W1.3 está completo**: criar e
preencher objetos IEC está provado para GVL e PROGRAM. O que falta para
encerrar W1 é [W1.4](32-plano-w1-4-integracao-e-build.md) — a cadeia integrada
com `build`, sobre o projeto-base novo, que ainda precisa ser qualificado.
