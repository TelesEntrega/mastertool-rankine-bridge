# Contrato de W2 — Task e Program Call

> Documento normativo. **Não abre gate nenhum.** `READ_ONLY_PHASE` continua
> `True` e `CONTROLLED_WRITE_PHASE` continua `None`. Autorizar
> `W2_BIND_PROGRAM_CALL` é ato à parte, em commit isolado, com o rito de
> [`docs/28`](28-contrato-escrita-controlada-mastertool-x.md) §14.

## 1. O que este marco resolve

### Separa "o projeto compila" de "o CLP executa"

[`docs/37`](37-execucao-w1-4-autoria-integrada.md) provou que o sistema cria,
preenche, persiste e **compila** um projeto ST. O que ele não provou — e está
escrito na seção "Limites" de lá — é que o `PRG_AI_TESTE` seria **executado**.
Ele compila porque é sintaticamente válido; nada o vincula a uma task, e um
PROGRAM sem Program Call é código que o CLP carrega e nunca chama.

Um build verde é condição necessária e **não suficiente** para um projeto
funcional. Este marco fecha essa distância.

## 2. A API, e de onde ela veio

Fonte: stub oficial versionado pelo produto,
`MT9000\ScriptLib\Stubs\scriptengine\ScriptTaskConfigObject.pyi`.

| Membro | Linha | Papel |
| --- | --- | --- |
| `ScriptTaskConfigObjectMarker.is_task_configuration` | L21-22 | localiza o container **por tipo** |
| `ScriptTaskObjectMarker.is_task` | L39-40 | localiza cada task **por tipo** |
| `ScriptTaskConfigObject.create_task(name)` | L57 | cria task — **não usado neste marco** |
| `ScriptTaskObject.pous` → `ScriptPouObjectCollection` | L218-226 | onde vive o Program Call |
| `ScriptPouObjectCollection.add(pou_name, comment=None)` | L294 | **é este o Program Call** |
| `.priority`, `.interval`, `.interval_unit`, `.watchdog`, `.kind_of_task` | L84-160 | propriedades da task |

<caption>

**Como ler:** os dois marcadores existem porque nó do MasterTool tem de ser
localizado **por tipo**, nunca por nome — nome é rótulo de interface e depende
de idioma. Foi o mesmo raciocínio que resolveu o inventário de bibliotecas,
onde `is_libman` substituiu a busca pelo texto "Library Manager".

</caption>

## 3. A estratégia, e a razão dela

### Vincular a uma task existente, e não criar task

O `TemplateExemplo v1.project` já tem `MainTask`, medido nas runs 011 e 018. Reutilizá-la
reduz a superfície mutável de duas operações para **uma**:

```text
task.pous.add("PRG_AI_TESTE")   →   save_as
```

Criar task fica instrumentado e **não exercido** neste marco. A ordem de
preferência é: acrescentar Program Call a task existente; criar task só se não
houver; criar Task Configuration só se ela não existir.

Isso não é economia por conveniência — é a mesma regra que manteve `create_pou`
fora de W1.2 quando `create_program` bastava: **allowlist que cresce por
precaução deixa de descrever o que está em uso**.

## 4. A armadilha central

### `ScriptPouObjectCollection` **herda de `list`**

Em `ScriptTaskConfigObject.pyi` L288: `class ScriptPouObjectCollection(list)`.
Portanto `add`, `insert`, `remove` e `replace` não são apenas homônimos de
métodos de lista — são **os mesmos nomes numa subclasse real de `list`**.

Consequência para a verificação: **o nome do método não decide nada; o receptor
decide.** Um `.add` num `set` Python e um `.add` na coleção de POUs da task são
indistinguíveis por texto, e só a análise por receptor na AST os separa.

É a terceira vez que esse padrão aparece — antes foi `insert`/`append` de
`IScriptTextDocument` colidindo com `list`, e depois `add_library` convivendo
com a leitura na mesma interface. Aqui a colisão é a mais forte das três,
porque é herança e não coincidência.

**`add` já está** em `MASTERTOOL_MUTATING_OPERATIONS` desde `b8ad7bb`, junto de
`insert`, `remove` e `replace`. Nada precisa ser acrescentado ao registro.

## 5. Fase controlada

### `W2_BIND_PROGRAM_CALL`

```text
add        save_as
```

Duas operações, e nenhuma além. **`create_task` fica fora**, porque não é
chamado; **`insert`, `replace` e `remove` ficam fora**, porque acrescentar ao
fim é o que o marco pede e allowlist não antecipa operação que ninguém usa.

`build` **não entra**. Ele foi autorizado uma vez, em W1.4, e a verificação de
compilação deste marco usa `probes/40`, que roda em **fase própria** — o build
é etapa separada, como já era em W1.4.

## 6. Critério de aprovação

Vincular não basta. O marco só fecha com as seis condições:

| # | Critério | Como se mede |
| --- | --- | --- |
| 1 | exatamente um `add` | journal, por receptor |
| 2 | exatamente um `save_as` | journal |
| 3 | entrada intacta | SHA-256 antes e depois |
| 4 | **o vínculo persiste** | reabertura independente lê `pous` com o PROGRAM |
| 5 | **o build continua verde** | `probes/40` sobre o arquivo salvo, 0 erros |
| 6 | nenhuma outra task alterada | comparação da lista de tasks e dos `pous` de cada uma |

<caption>

**Como ler:** o critério 4 é o que separa este marco de um `add` bem-sucedido
em memória. O critério 5 existe porque um Program Call para POU inexistente ou
mal-formado quebra a compilação — e um vínculo que quebra o build é pior que
vínculo nenhum, porque parece progresso.

</caption>

## 7. Fault injection

| Ponto | Estado esperado | Consequência sobre a cópia |
| --- | --- | --- |
| Task Configuration não encontrada | `task_config_not_found` | nada mutado; cópia reutilizável |
| Nenhuma task marcada por `is_task` | `no_task_found` | nada mutado; cópia reutilizável |
| Task alvo ambígua (duas com o nome) | `task_ambiguous` | nada mutado; cópia reutilizável |
| PROGRAM alvo ausente no projeto | `program_not_found` | nada mutado; cópia reutilizável |
| Program Call **já existe** | `already_bound` | nada mutado; **não é sucesso** |
| `add` levanta | `add_failed` | **descartar a cópia** |
| `add` não levanta mas `pous` não muda | `bind_not_observed` | **descartar a cópia** |
| `save_as` levanta | `save_as_failed` | **descartar a cópia** |
| `save_as` silencioso sem arquivo | `save_as_silent` | **descartar a cópia** |
| reabertura falha | `reopen_failed` | **descartar a cópia** |
| vínculo não persiste | `bind_not_persisted` | **descartar a cópia** |
| build passa a falhar | `build_regressed` | **descartar a cópia** |

<caption>

**Como ler:** a linha divisória é a primeira mutação. Antes dela, a cópia
continua limpa e pode ser reusada; depois dela, **a unidade descartada é a
cópia inteira** — `add` insere na coleção e não existe rollback transacional.
`already_bound` merece atenção: é o único caso em que nada falhou e mesmo assim
não é sucesso, porque medir um vínculo que já existia não prova que sabemos
criá-lo.

</caption>

## 8. Limites

**O que este marco vai comprovar, se aprovado:** que um PROGRAM existente pode
ser vinculado a uma task existente por script, que o vínculo persiste através
de `save_as` e reabertura, e que a compilação continua verde.

**O que ele NÃO comprova, e não deve ser afirmado:**

- **Que o CLP executa.** Vínculo persistido e build verde são condição
  necessária; execução real exigiria download e online, ambos permanentemente
  proibidos por `docs/28`. A afirmação máxima honesta é *"o projeto declara
  execução cíclica do PROGRAM"*.
- **Que os parâmetros da task estão certos** para a aplicação. `priority`,
  `interval` e `watchdog` são **lidos** no reconhecimento e **não alterados**;
  nada aqui os valida contra requisito de máquina.
- **Que criar task funciona.** `create_task` fica fora da allowlist e não é
  exercido.
- **Que a ordem de execução entre POUs é a desejada.** `add` acrescenta ao fim
  da coleção; ordem relativa a outros POUs não é objeto deste marco.
- **Determinismo.** (Para W1.4 isto foi medido em `docs/40`; para este marco,
  não.) A mesma operação não foi repetida sobre cópias novas para
  comparar.

## 9. Estado

Nenhuma fase aberta por este documento. Os instrumentos — `probes/42`
(reconhecimento read-only) e `probes/43` (vínculo) — falham fechado enquanto
`W2_BIND_PROGRAM_CALL` não existir em `PHASE_ALLOWED_OPERATIONS`, e esse é o
comportamento correto até a abertura.
