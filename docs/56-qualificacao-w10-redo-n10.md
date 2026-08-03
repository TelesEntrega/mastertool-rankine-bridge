# Qualificação W10-REDO — desfazer a reversão, N = 10

> Registro de execução. Lote `W10-REDO-N10`, dez execuções independentes em
> 2026-08-02. **Documento de evidência: não é corrigido depois.**

## O que este lote fecha

`docs/55` deixou a pendência `r2-reverter-a-reversao`: as dez specs inversas
das reversões estavam emitidas e guardadas nos pacotes, e nenhuma tinha sido
executada. Este lote as executa.

```text
10 plan_executed          10 before_hash_verified em e3b0c442…b855 (vazio)
10 build_verified         0 erros, 0 aviso de convenção do fabricante
10 factory_output_verified   1/1 em cada
10/10 UserPrg = 278101576eb1     o texto da W10 de volta, nas dez
10 only_authorized_changed       contra o TEMPLATE: "autorizado e alterado"
10/10 equivalentes        independência limpa nos 45 pares
10 sealed_complete        cada pacote com `rollback/` cheia
```

O ciclo completo, medido:

```text
TEMPLATE     596625…815f5   UserPrg = e3b0c442…b855   (vazio)
  ↓ alteração (docs/53, N=10)         antes: e3b0c442…b855
ALTERADO                      UserPrg = 278101576eb1
  ↓ reversão  (docs/55, N=10)         antes: 278101576eb1
REVERTIDO                     UserPrg = e3b0c442…b855   ← igual ao template
  ↓ redo      (este lote, N=10)       antes: e3b0c442…b855
RE-ALTERADO                   UserPrg = 278101576eb1   ← igual ao alterado
```

Cada seta é uma execução de campo com o hash anterior conferido no instante
anterior à escrita. As quatro linhas de `UserPrg` alternam entre exatamente
dois valores, e nenhum passo os declarou: todos foram medidos.

## O achado: desfazer a reversão NÃO é operação nova

A spec inversa de uma reversão tem `expected_before` = o texto **vazio** e
`text` = o texto da W10. Isso é, termo a termo, a alteração original — sobre
outra base.

Por isso este lote roda sob `W10_EDIT_EXISTING`, e não sob uma fase
`W10_REVERT2`. Dar-lhe fase própria faria a volta seguinte pedir
`W10_REVERT3`, e a seguinte `W10_REVERT4`: o ciclo passaria a ser descrito por
uma cadeia infinita de fases, quando ele é fechado por **duas** operações.

<caption>

**Como ler:** isto abranda uma leitura de uma decisão anterior. Quando
`W10_REVERT` ganhou fase própria (`docs/54`), o argumento foi que desfazer não
pode ficar indistinguível de fazer no registro. O argumento vale para o *undo*
— que restaura um texto medido antes — e **não** se estende ao *redo*, que é a
alteração. O que separa as runs no registro não é o nome da fase: são o hash da
spec, o do plano e o do alvo, todos gravados.

</caption>

## O que distingue este lote dos outros dois

| Lote | Antes conferido | Texto escrito | Contra o template |
|---|---|---|---|
| `docs/53` alteração | `e3b0c442…` (vazio) | o da W10 | `autorizado e alterado` |
| `docs/55` reversão | `278101576eb1` | vazio | `autorizado e SEM efeito` |
| **este, redo** | `e3b0c442…` (vazio) | o da W10 | `autorizado e alterado` |

<caption>

**Como ler:** a primeira e a terceira linha são a **mesma** transformação, e é
por isso que compartilham fase e `operation_id`. O que muda é a base: uma parte
do template, a outra parte de um projeto que já foi alterado e revertido duas
vezes. Que as duas produzam o mesmo texto final é o resultado — não a premissa.

</caption>

## O que este lote NÃO estabelece

- **Não promove `template_qualified`.** As duas lacunas do perfil seguem
  abertas: inventário de dispositivos e library lock.
- **Não mede um ciclo mais longo.** Foram três voltas
  (alterar → reverter → re-alterar). Nada aqui diz o que acontece na décima.
- **Não cobre reversão de criação nem reversão parcial.**
- **Não mede alvo com texto anterior não vazio.** As duas pontas do ciclo
  continuam sendo o texto vazio e o texto da W10.
- **Não diz que o CLP executa.**

## Limites

**O que a evidência comprova:** que o ciclo alterar → reverter → re-alterar
fecha nas duas direções no MasterTool X 4.1.0.11 sobre o `TemplateExemplo v1.project`, com
o hash anterior conferido no campo em cada passo, build verde e sem aviso de
convenção em todos, e o texto final medido igual ao esperado nas trinta
execuções dos três lotes.

**O que exige medição em campo:** ciclos mais longos; alvo com texto anterior
não vazio; reversão de criação; reversão parcial; e as fronteiras de sempre —
outra versão do produto, outro template, outra máquina.
