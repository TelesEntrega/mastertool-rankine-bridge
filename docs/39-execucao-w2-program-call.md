# W2 — execução do Program Call

> Registro de execução. `run-021`, sobre a saída aprovada de W1.4
> (`W1-A5.project`). É o marco que separa "o projeto compila" de "o CLP
> executa" — e o que ele encontrou muda o desenho da fábrica.

## 1. Veredito

### O vínculo funciona, persiste e compila — e o fabricante diz que o padrão é outro

`MainTask.pous.add("PRG_AI_TESTE")` seguido de `save_as` produziu um projeto
que reabre com o vínculo intacto e compila com **zero erros**. A capacidade
está provada.

Mas o build devolveu um aviso que nenhum plano previa:

> *"A tarefa MainTask deveria conter apenas a chamada do programa MainPrg.
> Chamadas adicionais de outros programas…"*

O caminho idiomático da Altus é chamar os demais POUs **de dentro** do
programa de entrada, e não acrescentá-los à lista da task. Isso é achado sobre
**convenção**, não sobre capacidade — e é a diferença entre "funcionou" e
"está certo".

## 2. Números medidos

| Grandeza | Valor |
| --- | --- |
| Entrada | `W1-A5.project`, `6b3d11d1…e6b34cda` — **intacta** ao fim |
| Saída | `W2-A6.project`, `525cd792…c3fd947d` |
| Mutações | **1** `add` + **1** `save_as` |
| `pous` antes → depois | `["MainPrg"]` → `["MainPrg", "PRG_AI_TESTE"]` |
| Posição do novo | 1 (acrescentado ao fim) |
| Task | `MainTask`, `root/1/0/0/3/0`, achada por `is_task` |
| Reabertura independente | `binding_verified`, `bound: true` |
| Build | `build_verified` — **0 erros**, 1 aviso, 8 informações |
| Output alterado pelo build | **não** |

<caption>

**Como ler:** `MainPrg` aparecer nas duas colunas é o que torna o critério
"nenhuma outra chamada alterada" verificável. Uma lista que fosse de vazia
para um item não distinguiria "acrescentou" de "substituiu".

</caption>

## 3. Os seis critérios de `docs/38`

| # | Critério | Resultado |
| --- | --- | --- |
| 1 | exatamente um `add` | journal, seq. 2–3 |
| 2 | exatamente um `save_as` | journal, seq. 5–6 |
| 3 | entrada intacta | SHA-256 idêntico |
| 4 | **o vínculo persiste** | `binding_verified` em processo separado |
| 5 | **o build continua verde** | `build_verified`, 0 erros |
| 6 | nenhuma outra chamada alterada | `MainPrg` preservado na posição 0 |

## 4. Três defeitos que a execução expôs

### O artefato de erro dependia do plano estar certo

O plano trazia `path` na operação `save_as`; o probe recusa campo desconhecido.
A recusa estava certa. O problema é o que veio depois: `validate_plan` reprovava
e retornava **antes** de `result["artifacts_dir"]` ser preenchido, então
`write_artifacts` não tinha para onde escrever. A sessão terminava sem **nenhum**
arquivo.

**Um relatório de erro que depende de o plano estar certo não relata justamente
o caso em que ele está errado.** O destino dos artefatos passou a ser fixado
antes da validação.

### "Nenhum artefato" tinha duas leituras incompatíveis

Sem arquivo algum, não havia como distinguir *"o probe não rodou"* de *"rodou e
morreu antes de gravar"* — e as duas pedem investigações opostas. `print` num
probe do MasterTool **não vai para stdout**: vai para o *message store* do
produto e some com a janela.

Agora o probe grava `bind-started.json` como primeira ação, usando só `open` e
`os` — nada de `common`, porque uma falha ao importar `common` é justamente uma
das hipóteses que o marcador precisa distinguir.

### A rede de exceções não pegava o que escapava

Mover o import para dentro do `try` não bastou: o sintoma persistiu, o que
prova que **o que escapava não era `Exception`**. A captura passou a ser
`BaseException`, e o gravador do artefato fatal deixou de depender de `file_io`.

Capturar tão largo seria ruim num programa comum. Aqui é o contrário: o
artefato é o **único canal de evidência**, e um erro que escapa sem deixar
arquivo obriga quem lê a adivinhar.

## 5. Verificar ganhou fase própria

`docs/38` já exigia que o build rodasse em fase separada, e a execução mostrou
por quê na prática: o probe 40 recusou rodar sob `W2_BIND_PROGRAM_CALL`.

Foi criada `W2_VERIFY_BUILD`, com **uma** operação — `build` — e nenhuma
escrita. Juntar `build` na allowlist de W2 teria alargado a fase da **mutação**
para cobrir uma **verificação**, e verificar não é autoria.

O probe 40 passou a aceitar um conjunto **literal e fechado** de fases
(`ACCEPTED_BUILD_PHASES`). Um probe que aceitasse "a fase que o plano disser"
não teria fase alguma.

## 6. Limites

**O que a evidência comprova:** que um PROGRAM existente pode ser vinculado a
uma task existente por script, que o vínculo persiste através de `save_as` e
reabertura independente, e que a compilação continua sem erros.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Vínculo persistido e build verde são condição
  necessária. Execução real exigiria download e online, permanentemente
  proibidos. A afirmação máxima honesta é *"o projeto declara execução cíclica
  do PROGRAM"*.
- ~~**Que este é o padrão correto.**~~ **RESPONDIDO em `docs/41`.** O fabricante
  avisa que não é, e o caminho que ele indica foi executado em W3: a chamada
  dentro de `UserPrg` compila com **zero** avisos, contra **um** aqui. A fábrica
  deve gerar por aquele caminho, não por este.
- **Que criar task funciona.** `create_task` ficou fora da allowlist e não foi
  exercido.
- **Que os parâmetros da task servem à aplicação.** `priority`, `interval` e
  `watchdog` foram **lidos**, nunca alterados nem validados contra requisito de
  máquina.
- **Determinismo do vínculo.** A operação `add` não foi repetida sobre cópias
  novas. O determinismo medido em `docs/40` cobre a cadeia de W1.4, e não
  este marco.

## 7. Estado

`W2_BIND_PROGRAM_CALL` e `W2_VERIFY_BUILD` foram **encerradas** em commit
próprio. `CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**W1 e W2 completos.** Oito fases abertas e fechadas, cada uma com abertura e
fechamento em commit isolado.
