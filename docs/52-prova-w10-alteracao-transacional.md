# Execução W10 — alteração transacional de objeto preexistente

> Registro de execução. Run `w10-edit-existing-001`, uma execução em
> 2026-08-02, sobre a terceira spec canônica. **Documento de evidência: não é
> corrigido depois.**

## O que esta run fecha

Toda escrita provada até aqui — W1.1 a W9, e os dois lotes N=10 de `docs/50` e
`docs/51` — era escrita sobre objeto que o **próprio plano criou**. O `antes` de
um objeto recém-criado é trivial: não havia nada. A pergunta da fase R2 é outra:

> alterar um objeto que já existia, garantindo que ele não mudou desde que foi
> medido — e provando que **nada além dele** mudou.

Esta run responde as duas metades. A `UserPrg` vem do `TemplateExemplo v1.project`; o plano
não a cria, e o executor conferiu o sha256 do texto anterior **imediatamente
antes** de sobrescrever.

```text
1 run solicitada          1 iniciada         1 concluída
plan_executed             2 passos executados, 3 delegados, de 5
before_hash_verified      e3b0c442…b855, conferido no campo antes do replace
build_verified            0 erros, nenhum aviso de convenção do fabricante
factory_output_verified   1 de 1 objeto conferido, 42 nós
only_authorized_changed   42 nós idênticos; único texto alterado é o autorizado
sealed_complete           pacote de evidência com os 10 artefatos, sem faltas
```

## Entradas, congeladas por hash

| O quê | Valor |
|---|---|
| Spec | `C:\mastertool-x-r1\specs\w10-edit-existing-v1.json` |
| Spec sha256 | `2c2efcbdc4240eb83cde3a14d833d6800de8de6ad5185d65fcbc9f18f0933698` |
| Template | `TemplateExemplo v1.project`, sha256 `596625796e4e…815f5` |
| Alvo | `programs:UserPrg:implementation` — **preexistente no template** |
| `expected_before_sha256` | `e3b0c44298fc…852b855` |
| Procedência do `antes` | **medido**, nas dez runs de `docs/50` (`host_sha256_before`) |
| Fase de autoria | `W10_EDIT_EXISTING` |
| Fase de build | `W10_VERIFY_BUILD` |
| Saída | sha256 `17706120144074713653ce05c3406af5a39d05301f20fc2cfb8d997a425e66f8` |
| Pacote | `bundle_sha256` `6a15653057c1…4d1b74`, `sealed_complete` |

<caption>

**Como ler:** a linha que dá sentido a todas as outras é a *procedência do
antes*. `e3b0c442…b855` é o sha256 da string vazia — a `UserPrg` do template
tem implementação vazia. O valor não foi digitado por ser conhecido: ele foi
**lido do campo** em dez execuções independentes antes de virar precondição de
escrita. Um hash anterior escrito de memória autorizaria a escrita contra o que
o autor da spec *achava* que estava lá.

</caption>

## As duas metades, e como cada uma foi provada

| Metade | Instrumento | Resultado |
|---|---|---|
| o objeto não mudou desde a medição | `probes/46`, conferência do hash imediatamente antes do `replace` | `before_hash_verified` no `execution-steps.json` |
| nada além dele mudou | `check-unexpected-changes`, árvore ANTES × DEPOIS e textos ANTES × DEPOIS | `only_authorized_changed` |

<caption>

**Como ler:** as duas metades usam instrumentos diferentes de propósito. A
primeira roda **dentro** da sessão de escrita, no instante anterior à
sobrescrita, porque é lá que a garantia vale — conferir antes de abrir a janela
deixaria um intervalo em que o arquivo pode mudar. A segunda roda **fora**, com
o produto fechado, comparando duas medições read-only.

</caption>

O `antes` da árvore foi medido pelo `probes/21` sobre uma cópia do template,
com hash conferido antes e depois para provar que a leitura não escreveu. Esse
lançador **não existia**: o `probes/21` varre a árvore inteira desde a fase L0
e nunca teve wrapper, o que significa que qualquer `antes` até hoje seria
medição feita à mão. `run_readonly_tree_scan.ps1` fecha isso, e recusa rodar
com fase de escrita aberta — um `antes` medido com janela de escrita aberta não
serve de `antes`.

## Os três defeitos que esta run encontrou

A run só ficou verde na terceira tentativa. As duas primeiras recusas foram do
próprio mecanismo, e valem mais que o resultado.

| Onde | O que | Por que importa |
|---|---|---|
| `probes/46` | lista própria de fases aceitas, sem `W10_EDIT_EXISTING` | a dupla porta funcionando: estar no mapa de allowlists **não basta**, o executor também precisa ter sido ensinado |
| plano de build | `operation_id` gerado com `_` no lugar de `-` | erro meu, recusado pelo `probes/40`; a lista de `operation_id` aceitos é literal e fechada, e foi ela que pegou |
| `probes/47` | não sabia ler a chave `modify:familia:nome:campo`, e **descartava em silêncio** o que não entendia | o achado grave — ver abaixo |

### O `continue` mudo do verificador

`text_hashes` ganhou uma segunda forma de chave na fase R2: `modify:` na
frente, para objeto preexistente. O parser do `probes/47` só conhecia a forma
de três partes e pulava o resto com um `continue`.

Nesta run isso produziu `plano sem text_hashes: nao ha o que verificar` — um
diagnóstico enganoso, porque o plano **tinha** a entrada; o verificador é que
não sabia lê-la. O caso pior ainda não aconteceu: um plano com **uma criação e
uma alteração** teria conferido a criação, descartado a alteração e devolvido
`factory_output_verified` — verde, com metade do plano medida.

`expected_texts` agora devolve `(esperado, ilegíveis)`, e chave ilegível
**bloqueia** com mensagem própria. É o mesmo modo de falha que
`unknown_family` já bloqueava, chegando por outra porta.

## O que esta run NÃO estabelece

- **Não é `repeatable`.** É **uma** execução. `field_proven` exige uma cadeia
  que persistiu e compilou — isso está feito. `repeatable` exige dez
  independentes, e não há nenhuma medição de repetição aqui.
- **Não cobre alteração de propriedade de task.** `configure_existing_task`
  continua sem a metade do executor: falta a busca por task preexistente.
  `spec/task_property_source.py` e `verify-modifications` cobrem o lado do
  host; o produto nunca foi tocado por essa via.
- **Não cobre `rename_object`.** `rename` segue na lista de membros proibidos
  do executor.
- **A camada de texto da comparação cobre um objeto, não o projeto.** Os dois
  lados leem o mesmo conjunto — o objeto que o plano tocou — então a comparação
  é coerente, mas ela **não** afirma que nenhum outro texto do projeto mudou. O
  que cobre o projeto inteiro é a camada de árvore: 42 nós, nome e `type_guid`.
- **Não diz que o CLP executa.** O `.project` compila. Ninguém carregou nada.

## Limites

**O que a evidência comprova:** que o MasterTool X 4.1.0.11, dirigido por este
mecanismo, altera o texto de um objeto que já existia no projeto, recusando-se
a fazê-lo se o texto anterior divergir do medido; que a saída compila sem erro
e sem aviso de convenção do fabricante; que a árvore de 42 nós é idêntica antes
e depois; e que o único texto alterado é o autorizado.

**O que exige medição em campo:** repetição (dez execuções independentes);
alteração de propriedade de task preexistente; renomeação; e comparação textual
de cobertura ampla — hoje o `antes` textual cobre os objetos que o plano tocou,
porque é o que o inventário read-only mediu.
