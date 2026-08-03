# Execução W10-REVERT — reversão medida de uma alteração aceita

> Registro de execução. Par `w10-rev-001` (alteração) + `w10-rev-002`
> (reversão), 2026-08-02. **Documento de evidência: não é corrigido depois.**

## O que este par fecha

`docs/53` deixou uma pendência com nome: `r2-reversao-medida`. O gate da R2 pede
que uma alteração seja *atômica, verificável, reprodutível e **reversível***, e
a quarta palavra estava medida pela metade — o arquivo de entrada sobrevivia
byte a byte, mas **ninguém tinha desfeito uma alteração aceita**, e o pacote de
evidência guardava o texto anterior por `sha256`, não por conteúdo. Hash não
reconstrói texto.

Este par mede a volta.

```text
TEMPLATE            596625…815f5    UserPrg.implementation = e3b0c442…b855 (vazio)
   ↓ alteração (W10_EDIT_EXISTING)  antes conferido no campo: e3b0c442…b855
ALTERADO            b64c5d87…d276d  UserPrg.implementation = 27810157…b22b48
   ↓ reversão (W10_REVERT)          antes conferido no campo: 27810157…b22b48
REVERTIDO           aced6153…5fe089 UserPrg.implementation = e3b0c442…b855

revertido × template  →  only_authorized_changed, "autorizado e SEM efeito"
```

A última linha é o fecho: comparado com o template **original**, o projeto
revertido não mudou em nada — 42 nós idênticos, e o texto autorizado de volta
ao valor de origem.

## As quatro coisas que tiveram de existir para isso ser uma prova

| # | O quê | Por que sem isso não valeria |
|---|---|---|
| 1 | o executor passou a gravar o **conteúdo** anterior, não só o hash | ele já lia esse texto — para hasheá-lo — e o descartava. Reverter a partir do hash é impossível |
| 2 | a spec inversa é **emitida**, não escrita à mão | `expected_before_sha256` da reversão é o `planned_after_sha256` do plano da ida. Digitá-lo reintroduziria o hash de memória que a fase R2 existe para eliminar |
| 3 | fases próprias (`W10_REVERT`, `W10_REVERT_VERIFY_BUILD`) com allowlist **idêntica** à da alteração | idêntica porque reverter por um caminho mais curto provaria a reversibilidade de outra coisa. Próprias porque uma reversão autorizada pela fase da ida poderia rodar dentro dela, e "alterou e desfez" ficaria indistinguível de "alterou" no registro |
| 4 | o alvo da reversão é a **saída**, não o template | um hash anterior só vale para o arquivo onde foi medido, e o template não contém o texto que se quer desfazer |

<caption>

**Como ler:** nenhum dos quatro é sobre "guardar um backup". Copiar o arquivo
antes de escrever seria trivial e provaria só que existe uma cópia. O que o
gate pede é que a alteração seja desfeita **pelo mesmo mecanismo que a fez**,
com o mesmo rigor de conferência — e é isso que os quatro constroem.

</caption>

## Entradas, congeladas por hash

| O quê | Valor |
|---|---|
| Template | `TemplateExemplo v1.project`, `596625796e4e…815f5` |
| Spec da ida | `w10-edit-existing-v1.json`, `2c2efcbdc424…f0933698` |
| Saída da ida | `b64c5d87c5a7133003bcc34bb1873d5de05b9d14ce1e3a3a21934b9311ed276d` |
| **Spec da volta** | `w10-rollback-001.json`, `c9f76edd2e9328b5ec59c67f0b7915a469a63664ab41647b71c957b20b5f6bbb` — **emitida** por `emit-rollback-spec` |
| `expected_before` da volta | `278101576eb1…3fb22b48` (o `planned_after_sha256` da ida) |
| Texto da volta | `""` — a implementação vazia que o template entrega |
| Saída da volta | `aced6153e2c9c4a11e634f20d0c51ee06de4aac4e5aa8c5ead4183ffc65fe089` |
| Fases | `W10_EDIT_EXISTING` → `W10_VERIFY_BUILD` → `W10_REVERT` → `W10_REVERT_VERIFY_BUILD`, cada uma aberta e fechada em commit isolado |
| Pacotes | `w10-rev-001-alteracao` e `w10-rev-002-reversao`, ambos `sealed_complete`, ambos com seção `rollback/` |

<caption>

**Como ler:** o `expected_before` da volta não foi digitado — ele veio do plano
da ida, que o computou do texto que ele mesmo autorizou. Se a saída não
contivesse exatamente aquele texto, a reversão teria parado com
`before_hash_mismatch`, e isso é o desejado: significaria que alguém mexeu no
arquivo entre as duas operações.

</caption>

## Os dois builds

| Run | Build | Verificação | Nós |
|---|---|---|---|
| `w10-rev-001` (alterado) | `build_verified`, 0 erros, **0 aviso de convenção** | `factory_output_verified`, 1/1 | 42 |
| `w10-rev-002` (revertido) | `build_verified`, 0 erros, **0 aviso de convenção** | `factory_output_verified`, 1/1 | 42 |

<caption>

**Como ler:** a verificação do revertido confere o texto contra o que o plano
da **volta** autorizou — que é o texto original. `factory_output_verified` ali
significa, literalmente, que o projeto revertido contém o que o template
continha.

</caption>

## O que a reversão NÃO devolve, e isso é correto

O `.project` revertido **não** é byte a byte igual ao template:
`aced6153…5fe089` ≠ `596625796e4e…815f5`. O formato carrega GUID e timestamp,
e uma reversão que produzisse bytes idênticos exigiria que o produto não
registrasse ter sido aberto — o que ele registra.

A reversibilidade medida aqui é **de conteúdo**, e é o mesmo critério que
sustenta o determinismo desde `docs/40`: comparar o arquivo reprova sempre, e
reprova por motivo nenhum.

## O que este par NÃO estabelece

- **A reversão tem `n = 1`.** É `field_proven`, não `repeatable`. E repeti-la
  em N=10 **não é rodar o lote existente**: cada reversão tem `expected_before`
  amarrado a uma saída específica, então dez reversões exigem dez specs
  inversas distintas e dez qualificações de alvo. O lote atual recebe **uma**
  spec para todas as runs. Falta mecanismo, e ele está nomeado
  (`r2-repetir-reversao-n10`).
- **A reversão da reversão não foi executada.** A spec inversa dela existe
  (`w10-rollback-002.json`, emitida e guardada no pacote) e ninguém a rodou.
- **Não cobre reversão de criação.** Desfazer um objeto criado exigiria
  `delete`/`remove`, que não está no `EXECUTOR_CONTRACT` e não tem fase.
- **Não cobre reversão parcial.** A spec inversa desfaz **todas** as alterações
  do plano; escolher um subconjunto é outro problema, e ninguém o escreveu.
- **Não diz que o CLP executa.**

## Limites

**O que a evidência comprova:** que uma alteração aceita de objeto preexistente
pode ser desfeita pelo mesmo mecanismo que a fez, com a mesma conferência de
hash anterior no campo; que o projeto resultante compila sem erro e sem aviso
de convenção do fabricante; e que ele é, contra o template original,
indistinguível em árvore (42 nós) e no texto alterado.

**O que exige medição em campo:** repetição da reversão (N=10, e ela precisa de
mecanismo de lote que hoje não existe); reversão da reversão; reversão de
criação; reversão parcial; e as mesmas fronteiras de sempre — outra versão do
produto, outro template, outra máquina.
