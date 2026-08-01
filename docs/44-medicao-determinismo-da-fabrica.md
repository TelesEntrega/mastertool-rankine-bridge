# Determinismo da fábrica — medição

> Registro de execução. `run-029` e `run-030`, a mesma spec sobre cópias novas
> do mesmo template. Fecha a lacuna que `docs/42` §6 nomeou: *"a spec não foi
> executada duas vezes sobre cópias novas"*.

## 1. Veredito

### A mesma spec produz o mesmo projeto — e nunca o mesmo arquivo

| Grandeza | `run-029` | `run-030` |
| --- | --- | --- |
| Plano (SHA-256) | `16a3584b…` | **o mesmo** |
| Objetos criados | `GVL_FABRICA`, `PRG_BOMBA`, `PRG_PRESSAO` | os mesmos |
| Nós na árvore | 45 | 45 |
| Build | `build_verified`, 0 erros, 0 avisos | idem |
| Verificação | 3 de 3 objetos | idem |
| **`.project` (SHA-256)** | `83338ce0…` | **`a62822b8…`** |

<caption>

**Como ler:** a última linha é a única que difere, e é a que **não** é critério.
O `.project` carrega GUID de objeto e timestamp; comparar o arquivo reprovaria
sempre, e reprovar sempre não distingue nada.

</caption>

O plano ter o **mesmo hash** nas duas execuções é resultado à parte: o planner é
determinístico e offline, então a mesma spec produz o mesmo plano byte a byte.
A variação nasce só do produto.

## 2. Duas camadas comparadas, uma declarada ausente

| Camada | Resultado |
| --- | --- |
| Texto relido do disco | idêntico |
| Árvore persistida (45 nós) | idêntica |
| Diff estrutural | **ausente neste layout** |

<caption>

**Como ler:** a fábrica não parte de árvore-base conhecida — ela parte de um
template que a spec nomeia —, então a terceira camada de `docs/40` não existe
aqui. Ela é registrada em `layers_absent`, e **não** somada a `layers_compared`:
somá-la faria o resultado alegar três camadas tendo medido duas.

</caption>

**Contraprova de independência:** 5 `object_guid` diferem entre as execuções. Se
fossem iguais, eu estaria comparando a mesma execução com ela mesma e chamando a
tautologia de determinismo.

## 3. O `verify` existia no plano e não era executado

O plano declara `reopen`, `build` e `verify`; o executor registrava os três como
`delegated`. **`build` tinha destinatário — os outros dois não.** "Delegado" sem
destinatário é só um jeito educado de dizer "não feito", e o artefato dizia isso
desde a `run-027` sem que eu tivesse olhado.

O `probes/47` fecha isso, e responde o que o executor **não pode** responder: o
executor sabe o que **escreveu**; ele não sabe o que ficou no arquivo. Ele
afirma sobre a memória da sessão que mutou. O verificador reabre a saída numa
sessão nova e lê do disco.

Três camadas: cada objeto declarado existe **com o tipo certo**; o texto relido
tem o hash que o **plano** autorizou (não o que a spec diz — conferir contra a
spec mediria a spec contra ela mesma); e a árvore inteira, achatada, com os
mesmos campos que o comparador usa.

## 4. Limites

**O que a evidência comprova:** que duas execuções da mesma spec, sobre cópias
novas do mesmo template, na mesma máquina e instalação `4.1.0.11`, produzem
projetos de conteúdo idêntico nas duas camadas medidas, e arquivos que nunca são
iguais byte a byte.

**O que NÃO está comprovado:**

- **Determinismo entre máquinas ou instalações.** As duas rodaram na mesma.
- **Determinismo de specs com FB e FUNCTION.** A spec medida tem 1 GVL e 2
  PROGRAMs. A `run-028` provou FB e FUNCTION, mas não foi repetida.
- **`n=2`.** `docs/40` mediu cinco gerações da cadeia de W1.4; aqui são duas.
- **Specs grandes.** Três objetos. O limite do executor é 512 passos.
- **Que a árvore de 45 nós esteja completa.** O verificador varre até
  `MAX_TOTAL_NODES = 2048` e `MAX_DEPTH = 10`; nada mediu se o template real
  cabe folgado nesses limites ou se está perto deles.
- **Que `type_guid` distinga as famílias de POU.** Não distingue (`docs/35` §4):
  o verificador consegue dizer *"é uma POU"*, nunca *"é um FUNCTION_BLOCK"*.

## 5. Estado

Nenhuma fase aberta. `CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.
As duas execuções rodaram sob `W4_EXECUTE_PLAN` e `W4_VERIFY_BUILD`, as mesmas
fases de `docs/42`, com as mesmas allowlists — reabrir sem alterar é o que torna
a comparação com a `run-027` legítima.
