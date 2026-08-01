# W3 — a chamada idiomática

> Registro de execução. `run-026`, sobre a saída aprovada de W1.4
> (`W1-A5e.project`). Responde ao achado de `docs/39`: o fabricante avisou que
> o padrão de W2 não é o correto. Este marco mede o padrão que ele indica.

## 1. Veredito

### O aviso do fabricante desaparece quando a chamada sai da task e vai para dentro da POU de perfil

A mesma cadeia, o mesmo compilador, a mesma instalação `4.1.0.11` — e a única
diferença sendo **onde a chamada mora**:

| Marco | Onde a chamada foi parar | Avisos do fabricante |
| --- | --- | --- |
| W2 (`run-021`) | acrescentada à lista da `MainTask` | **1** |
| W3 (`run-026`) | dentro de `UserPrg` | **0** |

<caption>

**Como ler:** as duas linhas compilaram com zero erros. O que muda entre elas
não é se funciona — é se está certo segundo quem fabrica o CLP.

</caption>

O aviso de W2, na íntegra:

> *"A tarefa MainTask deveria conter apenas a chamada do programa MainPrg.
> Chamadas adicionais de outros programas devem ser realizadas a partir das
> POUs correspondentes do Perfil de Projeto (StartPrg, UserPrg, ActivePrg e
> NonSkippedPrg)"*

## 2. Números medidos

| Grandeza | Valor |
| --- | --- |
| Entrada | `W1-A5e.project`, `2e9ebb77…f477ed326` — **intacta** ao fim |
| Saída | `W3-A7.project`, `7c639b3e…3d251a44e` |
| Mutações | **1** `replace` + **1** `save_as` |
| POU hospedeira | `UserPrg`, achada por **nome e tipo** |
| Perfil presente no template | `StartPrg`, `UserPrg` |
| Perfil **ausente** no template | `ActivePrg`, `NonSkippedPrg` |
| `UserPrg` antes | **vazia** — 0 caracteres |
| `UserPrg` depois | comentário de origem + `PRG_AI_TESTE();` |
| Build | `build_verified` — 0 erros, **0 avisos**, 5 informações |
| Saída alterada pelo build | **não** |
| Postsave | `postsave_verified` |

<caption>

**Como ler:** "5 informações" são as cinco linhas do compilador, já descontado
o banner do próprio probe — três mensagens que caem no mesmo *message store*
(ver `docs/40` §5).

</caption>

## 3. Como a POU foi encontrada

### Nome sozinho não distingue objeto algum; tipo sozinho não distingue perfil

O nome entra porque **a convenção do fabricante é por nome** — o aviso cita as
quatro POUs textualmente. O `type_guid` entra porque uma *pasta* chamada
`UserPrg` casaria com o nome. Só o par decide, e há teste para cada metade.

Duplicata **não é desempatada**: com dois candidatos válidos, o probe recusa e
registra. Escolher por ordem de varredura seria acertar por sorte, e a mutação
iria para o objeto errado sem ninguém perceber.

Ausência é registrada como ausência: `ActivePrg` e `NonSkippedPrg` não existem
no `TemplateExemplo v1.project`. Omiti-las faria a lista parecer completa — o aviso cita o
perfil **inteiro** da Altus, e o template implementa parte dele.

## 4. `replace` substitui o documento inteiro

### Não existe "acrescentar" na API, e é isso que dá forma à cadeia

O preflight **lê** e registra o texto do fabricante com SHA-256; o host o grava
em arquivo e confere que o que gravou é o que o probe leu; a mutação só roda se
o texto entregue conferir, e recusa com `text_drifted` se o projeto mudou no
meio.

Nesta execução `UserPrg` estava **vazia**, então nada foi preservado porque não
havia nada. A maquinaria continua necessária e correta: ela é o que garante que
a próxima geração, sobre um template onde a POU tenha código, não o apague.

O texto final registra a própria origem:

```
(* chamada acrescentada por mastertool-rankine-bridge (W3) *)
PRG_AI_TESTE();
```

Um projeto gerado que não diz que foi gerado obriga o próximo engenheiro a
adivinhar.

## 5. Dois defeitos que a execução expôs

### O host anunciou o resultado que o marco procurava, sobre um build que não aconteceu

A primeira tentativa de build reprovou em `precondition_failed` — o plano não
trazia o bloco `container`. E o wrapper imprimiu:

> `[OK] O aviso do fabricante sobre chamadas na task NAO aparece.`

Claro que não aparecia: **a compilação nunca rodou**. É o mesmo modo de falha
que o probe 40 combate com `no_build_messages`, reaparecido no host, num bloco
escrito no mesmo dia em que essa armadilha foi documentada.

A correção são **três estados, e não dois**: presente, ausente, **não medido**.
No artefato, `vendor_warning_present` é `null` quando não medido — `false`
seria uma afirmação sobre uma compilação que talvez não tenha existido.

### O plano do build precisava ser outro

O build de W3 roda sob `W3_VERIFY_BUILD`, e o plano da mutação declara
`W3_IDIOMATIC_CALL`. Um plano só teria de declarar uma das duas, e a outra
etapa rodaria sob uma fase que o plano não declara — exatamente o que a
separação entre mutar e verificar existe para impedir.

O `-BuildPlan` também confere que aponta para a **mesma** saída que a mutação
produziu. Sem isso, um plano apontado para outro arquivo compilaria outra coisa,
e o veredito seria sobre um artefato que a sessão nunca produziu.

## 6. A cadeia esperada do build passou a ser por fase

Havia uma tupla só — a de W1.4 — exigida de **todo** plano de build. Foi por
isso que o plano de build de W2 teve de declarar `create_gvl, create_program,
replace, replace, replace, save_as, build` para compilar a saída de `add` +
`save_as`: passava na validação e **mentia** sobre o que produziu o artefato.

`W2_VERIFY_BUILD` fica com a cadeia antiga de propósito — é o registro do que a
`run-021` executou, e reescrever invalidaria um plano já documentado. Corrigir
para frente, sem reescrever história. Fase sem cadeia declarada **reprova**, em
vez de cair no padrão de W1.4.

## 7. Limites

**O que a evidência comprova:** que um PROGRAM existente pode ser chamado de
dentro de uma POU do Perfil de Projeto por script, que a chamada persiste
através de `save_as` e reabertura independente, que a compilação fica sem erros
**e sem o aviso de convenção**, e que o texto anterior da POU é preservado pela
construção do texto final.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Continua valendo o limite de `docs/39`: download e
  online são permanentemente proibidos. A afirmação máxima honesta é *"o projeto
  declara execução cíclica do PROGRAM, pelo caminho que o fabricante indica"*.
- **Que a preservação de texto funciona sobre POU com código.** `UserPrg` estava
  vazia. A função de montagem tem teste com texto não vazio, mas **em campo** só
  foi exercida sobre o vazio.
- **Que `StartPrg` serve igualmente.** Só `UserPrg` foi exercida. `StartPrg` roda
  na partida, não ciclicamente — a escolha foi deliberada e não medida contra a
  alternativa.
- **Que `ActivePrg` e `NonSkippedPrg` funcionam.** Não existem neste template.
- **Determinismo de W3.** A operação não foi repetida sobre cópias novas. O que
  `docs/40` mediu foi a cadeia de W1.4.
- **Que a ordem da chamada dentro da POU importa.** A chamada foi ao fim do
  texto; nenhuma alternativa foi medida.

## 8. Estado

`W3_IDIOMATIC_CALL` e `W3_VERIFY_BUILD` foram **encerradas**, cada uma em
commit próprio. `CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**W1, W2 e W3 completos.** Dez fases abertas e encerradas; uma delas
(`W1_4_INTEGRATED_BUILD`) reaberta uma vez, com a mesma allowlist, para medir
determinismo.
