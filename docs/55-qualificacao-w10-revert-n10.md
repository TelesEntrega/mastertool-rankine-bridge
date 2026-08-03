# Qualificação W10-REVERT — reversão, N = 10

> Registro de execução. Lote `W10-REVERT-N10`, dez reversões independentes em
> 2026-08-02. **Documento de evidência: não é corrigido depois.**

## O que este lote fecha

`docs/54` provou a reversão **uma vez** e nomeou a pendência: repeti-la não era
rodar o lote existente, porque cada reversão amarra o `expected_before` a uma
saída específica. Este lote constrói o mecanismo que faltava e mede a repetição.

```text
10 alterações            10 saídas DISTINTAS, 10 textos anteriores capturados
10 specs inversas        emitidas, uma por run — nenhuma escrita à mão
10 qualificações de alvo cada uma conferida CONTRA O PRÓPRIO ARQUIVO
10 plan_executed         10 before_hash_verified em 278101576eb1
10 build_verified        0 erros, 0 aviso de convenção do fabricante
10 factory_output_verified   1/1 em cada
10/10 UserPrg = e3b0c442…b855   o texto ORIGINAL de volta, nas dez
10 only_authorized_changed      contra o TEMPLATE: "autorizado e SEM efeito"
10/10 equivalentes       independência limpa nos 45 pares
10 sealed_complete       cada pacote com a seção `rollback/` cheia
```

## Por que este lote não podia ser o lote de repetibilidade

`run_repeatability_batch.ps1` manda **uma** spec para as N execuções, porque
numa qualificação de repetibilidade a entrada tem de ser idêntica — é o ponto
dela.

Reversão não aceita isso. Dez alterações produziram dez saídas distintas
(`15a8c65d…`, `9e522df9…`, `63775060…`, …), e o `expected_before_sha256` de
cada reversão vale para **um** desses arquivos. Rodar as dez contra uma spec
única não seria um lote de reversões: seria a mesma reversão reprovando nove
vezes por `before_hash_mismatch` — que é a conferência funcionando.

`run_rollback_batch.ps1` faz o que o outro não faz: emite uma spec inversa por
run (chamando `emit-rollback-spec`, nunca montando a spec) e qualifica cada
alvo separadamente.

<caption>

**Como ler:** as dez specs inversas compartilham o `expected_before`
(`278101576eb1…`, porque o mesmo texto foi escrito nas dez) e diferem no alvo.
É exatamente essa assimetria que impede uma spec de servir dez runs.

</caption>

## Uma diferença de experimento que precisa ser dita

Em `docs/53` o `plan_sha256` era **um** valor nas dez: mesma spec, mesmo
planner, mesmo plano. Aqui são **dez**, porque cada plano carrega o hash do seu
alvo.

Isso significa que este lote não é o mesmo experimento. `docs/53` mediu
"entrada idêntica → saída equivalente". Este mede "dez entradas **de conteúdo
idêntico e bytes distintos** → dez saídas equivalentes". A segunda é a única
forma que a pergunta admite — não existem dez alterações com a mesma saída em
bytes — e chamá-la de repetibilidade sem essa nota seria emprestar a força de
um experimento a outro.

## Os dois defeitos que este lote encontrou

### A qualificação não dizia de qual arquivo falava

Montar a qualificação por alvo expôs que a fábrica **nunca** conferia isso.
`qualify-analysis.json` — o artefato que ela lê — trazia `authoring_eligible` e
nenhuma identidade; o `sha256` do projeto existia só no
`qualify-completion.json`, que a fábrica não lê. A qualificação de um projeto
autorizava escrita em outro, e nada detectava.

Neste lote o atalho teria sido reusar uma qualificação para os dez alvos, e o
lote inteiro pareceria conferido de ponta a ponta.

O `probes/35` passou a copiar a medição **que já fazia** para o artefato onde a
decisão é tomada, e a fábrica recusa divergência — e recusa ausência, porque
não saber de que arquivo o artefato fala não é o mesmo que ele falar deste.

### A obrigatoriedade condicional não chegava ao selo

`ROADMAP` §2.7 e o commit que criou a seção `rollback/` afirmavam: plano **com**
alteração e sem os artefatos de reversão sela `sealed_incomplete`. **Não era
verdade.** A condição vivia em `evidence/from_run.py` e só chegava ao stdout do
comando; quem decide o status é `BUNDLE_LAYOUT`, e `rollback/` não tem arquivo
obrigatório.

Os dez primeiros pacotes deste lote selaram `sealed_complete` com
`[FALTANDO] rollback/rollback-spec.json` impresso três linhas acima.

`seal()` passou a aceitar `extra_missing`, porque nem toda obrigatoriedade é
estática: o layout sabe o que **toda** execução deve carregar, e não pode saber
que uma execução que ALTEROU objeto preexistente também deve trazer o texto
anterior — isso depende do plano. O manifesto agora registra
`plan_has_modifications`, para que quem ler o pacote saiba por que `rollback/`
era exigido sem reabrir o plano.

Prosa que o código não cumpre é o modo de falha que este projeto persegue.
Aqui ele foi meu.

## O que este lote NÃO estabelece

- **Não promove `template_qualified`.** As duas lacunas do perfil seguem
  abertas: inventário de dispositivos e library lock.
- **Não mede reversão da reversão.** As dez specs inversas das reversões foram
  emitidas e estão nos pacotes; nenhuma foi executada.
- **Não cobre reversão de criação.** Exigiria `delete`/`remove`, fora do
  `EXECUTOR_CONTRACT` e sem fase.
- **Não cobre reversão parcial.** A spec inversa desfaz todas as alterações do
  plano.
- **Não mede alvo com texto anterior não vazio.** `e3b0c442…b855` continua
  sendo o sha256 da string vazia.
- **Não diz que o CLP executa.**

## Limites

**O que a evidência comprova:** que desfazer uma alteração aceita de objeto
preexistente é reprodutível no MasterTool X 4.1.0.11 sobre o `TemplateExemplo v1.project` —
dez reversões independentes, dez conferências do hash anterior no campo, dez
builds sem erro e sem aviso de convenção, dez verificações aprovadas, e nas dez
o texto de volta ao valor que o template entrega, com o projeto indistinguível
do template em árvore (42 nós) e no texto alterado.

**O que exige medição em campo:** reversão da reversão; reversão de criação;
reversão parcial; alvo com texto anterior não vazio; e as fronteiras de sempre
— outra versão do produto, outro template, outra máquina.
