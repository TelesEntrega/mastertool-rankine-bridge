# Modelo de segurança — documento consolidado

> **NORMATIVO E VIGENTE.** Esta página consolida, num só lugar, o modelo de
> segurança que hoje está espalhado por
> [`08-safety.md`](08-safety.md) (política), `config/safety-policy.yaml`
> (normativo, prevalece em divergência sobre a política escrita),
> [`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md)
> (contrato de escrita) e a implementação em
> `scripts/mastertool/common/safety.py`.
>
> Ela **não afrouxa nada** e não autoriza nenhuma escrita. Onde houver
> divergência entre esta página e o YAML, **o YAML prevalece**; onde houver
> divergência entre esta página e o código, **o código é o fato** e a página
> está com defeito.

---

## 1. As duas perguntas que este modelo responde

1. **O que o sistema nunca faz**, em nenhuma circunstância, com nenhuma flag.
2. **Sob que condições ele escreve**, quando escreve.

Tudo o mais é detalhe de implementação dessas duas respostas.

## 2. Proibições permanentes

Treze operações, registradas literalmente em `safety.py:22-36`
(`FORBIDDEN_OPERATIONS`) e espelhadas em `config/safety-policy.yaml`. Elas não
têm fase, não têm allowlist e não têm flag:

```text
modify_original_project              download_to_plc
go_online                            login_to_controller
start_controller                     stop_controller
reset_controller                     force_variables
write_physical_outputs               change_hardware_configuration
install_libraries_without_authorization
import_without_backup
apply_ai_changes_to_official_project
```

**Nenhuma delas entra em escopo em nenhuma fase deste roadmap, inclusive
v1.0.** Operação online e atuação sobre o CLP estão fora do produto por
decisão, não por imaturidade.

Três riscos adicionais, descobertos na W0 e proibidos pelo contrato `docs/28`:

| Proibido | Por quê |
|---|---|
| `ScriptPromptHandling.SuppressPrompts` | suprimir diálogo transforma pergunta do produto em silêncio, e silêncio vira sucesso |
| `download_missing_libraries` | baixar biblioteca é mudar a resolução de dependência sem declaração |
| `set_compilerversion_to_newest` | trocar o compilador por conta própria muda o artefato sem pedido |

## 3. A base é somente leitura, e continua sendo

`READ_ONLY_PHASE = True` (`safety.py:20`) e as sete operações legadas de
`WRITE_OPERATIONS` seguem bloqueadas. **Abrir uma fase de escrita controlada
não mexe nesse booleano.** Isso é deliberado: `READ_ONLY_PHASE = False`
autorizaria as sete de uma vez, que é exatamente a abertura genérica que o
contrato proíbe.

## 4. Escrita controlada — como uma operação chega a ser permitida

Quatro condições, todas necessárias:

1. **A operação está no registro literal de mutadores.** `safety.py:61-84`
   nomeia 41 operações mutáveis, uma a uma, sem curinga e sem prefixo:
   `create_*` não existe ali de propósito. **Nome desconhecido falha
   fechado.**
2. **Existe uma fase aberta.** `CONTROLLED_WRITE_PHASE` (`safety.py:312`)
   nomeia no máximo **uma** fase por vez, ou `None`. Hoje é `None`.
3. **A operação está na allowlist daquela fase.** `PHASE_ALLOWED_OPERATIONS`
   (`safety.py:322-446`) mapeia fase → conjunto de operações.
4. **A chamada passa pela porta certa** (§5).

> **Estar no mapa de allowlists ≠ estar autorizada.** As entradas permanecem no
> mapa depois que a fase fecha, como registro histórico. Quem autoriza é o
> ponteiro `CONTROLLED_WRITE_PHASE`. Esse erro de leitura já foi cometido neste
> projeto — ler sempre o ponteiro, nunca o mapa.

## 5. Duas portas, porque são dois modos de falha

| Porta | Cobre | Forma no AST | Falha típica |
|---|---|---|---|
| `assert_controlled_write_allowed` (`safety.py:483`) | chamada de método — `objeto.metodo(...)` | `Call` | método proibido levanta e a execução para |
| `assert_controlled_property_write_allowed` (`safety.py:535`) | atribuição a atributo — `objeto.campo = x` | `Assign` com alvo `Attribute` | atribuição que não pega **não levanta**: o campo simplesmente continua com o valor antigo, e o projeto compila limpo |

A segunda porta existe porque a primeira **não recusava** `task.interval = x` —
ela **não via**. Guarda de chamada procura `Call`; atribuição é outra forma
sintática. As propriedades têm registro próprio (`MASTERTOOL_PROPERTY_WRITES`,
`safety.py:111-113`) com prefixo `set:`, que não é decoração: ele impede que um
nome de propriedade colida com um nome de método dentro da mesma allowlist —
`add`, `replace`, `insert` e `remove` são métodos catalogados e seriam nomes
plausíveis de campo.

Consequência de método: **toda escrita de propriedade é relida depois de
escrita**, do objeto e depois do projeto salvo e reaberto. Um método que falha
levanta; um campo que falha fica quieto.

### Sem `setattr` no executor

Proibido, com teste de AST guardando. `getattr` continua permitido, com a
assimetria declarada: **leitura errada devolve dado errado; escrita errada muda
o produto.**

## 6. A cadeia obrigatória de uma escrita

Nenhuma escrita acontece fora desta sequência:

```text
spec JSON validada offline
  → planner (offline, fail-closed em field_proven)
  → plano literal com hashes, sem texto final
  → cópia descartável em diretório isolado
  → executor com allowlist da fase
  → save_as para caminho NOVO
  → reabertura independente
  → extração completa
  → diff estrutural e textual
  → build
  → relatório de evidências
  → aprovação humana
```

Invariantes que valem em todas as fases:

- **o arquivo de entrada permanece intacto byte a byte** — `save_as` não toca a
  entrada, e isso foi medido (mesmo SHA-256 antes e depois);
- **a saída nunca substitui a origem automaticamente**;
- **a reabertura é obrigatória** — persistir e verificar em memória não é
  verificação;
- **alteração inesperada invalida a execução**, mesmo que "inofensiva";
- **build com erro invalida o artefato**;
- **abrir projeto cria `.opt` irmãos**, por isso a cópia vai para diretório
  próprio e o diff estrutural compara o `.project`, nunca a pasta.

## 7. Níveis de risco e tratamento

Inalterados em relação a [`08-safety.md`](08-safety.md):

| Nível | Exemplos | Tratamento |
|---|---|---|
| Baixo | comentários, documentação, formatação, relatórios | aprovação humana simples |
| Médio | lógica interna, cálculos, refatoração sem saída física, GVL sem mapeamento físico | compilação + aprovação |
| Alto | máquinas de estado, permissivos, alarmes, timers de processo, sequenciamento, MES, OPC UA, intertravamentos, `RETAIN`/`PERSISTENT` | compilação + simulação + aprovação |
| Crítico | saídas físicas, `%Q`, segurança de máquina, parada de emergência, robô, válvulas, motores, inversores, hardware, redes industriais, download | **nunca automático**; processo manual com avaliação de risco documentada e aprovação sênior |

**Autoria ligada a função de segurança exige revisão humana especializada.** A
ferramenta gera e verifica estruturalmente; ela **não** declara que uma função
está certificada ou segura, e nenhuma versão futura fará isso.

## 8. O papel da IA — e o que ela nunca alcança

A separação é estrutural, não uma convenção de uso:

```text
IA propõe  →  validador determinístico  →  aprovação humana  →  planner  →  executor isolado
```

- ferramentas de **leitura** podem ser chamadas livremente;
- ferramentas de **proposta** produzem especificação, change set, plano,
  impacto, riscos e testes recomendados — nunca efeito;
- ferramentas de **execução nunca são chamadas pelo modelo**;
- **nenhuma string de script livre** chega ao executor: o vocabulário é um
  catálogo fechado de operações;
- os alertas heurísticos de `analysis/safety_checks.py` são **alertas para
  revisão humana**. Um agente nunca deve tratá-los como erro confirmado nem
  "corrigi-los" automaticamente.

## 9. Regras de evidência

Estas são regras de segurança, não de estilo: quase todo incidente registrado
neste projeto veio de violá-las.

- **Três estados, nunca dois:** presente, ausente, **não medido**. Ausência de
  mensagem nunca é aprovação — existe `no_build_messages` para isso.
- **Silêncio virando sucesso é o modo de falha recorrente deste projeto.**
  `print` num probe não vai para stdout: vai para o *message store* do
  MasterTool e some com a janela. Todo probe grava um marcador em disco como
  primeira ação, senão "nenhum artefato" fica ambíguo entre "não rodou" e
  "morreu antes de gravar".
- **O artefato de erro não pode depender de o plano estar certo:**
  `artifacts_dir` é fixado **antes** da validação, captura-se `BaseException` e
  o gravador do artefato fatal não depende de `common`.
- **Valor de teste igual ao default não é evidência.**
- **Teste verde não é evidência até falhar quando deve.** Guarda que nunca
  reprovou não é guarda.
- **Resultado científico inconclusivo ≠ falha operacional**, e **ausência de
  observação ≠ ausência de suporte**.
- **Nunca inventar API.** Só o que está em
  `docs/api/mastertool-api-observations.md`, em `docs/27`, nos stubs `.pyi` que
  o produto instala, ou observado em runtime.

## 10. Dado de cliente

Nunca entra no repositório: XML exportado, árvore de projeto, inventário de
dispositivo, nomes de equipamento, variáveis e lógica do cliente ficam fora.
Fixtures são sintéticas; de artefato real entra apenas o hash, que não é
reversível. A verificação é automatizada em `tools/check_repo_hygiene.py`.

## 11. Abertura de fase

Abrir uma fase de escrita é **decisão humana**, em **commit próprio e isolado**,
que não carrega implementação junto (`docs/28` §14). O commit que abre o gate
não é o commit que usa o gate.
