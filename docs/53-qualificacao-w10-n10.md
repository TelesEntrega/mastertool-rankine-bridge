# Qualificação W10 — alteração transacional, N = 10

> Registro de execução. Lote `W10-EDIT-EXISTING-N10`, dez execuções
> independentes em 2026-08-02, sobre a terceira spec canônica. **Documento de
> evidência: não é corrigido depois.**

## O que este lote fecha

`docs/52` provou a alteração de objeto preexistente **uma vez**, e disse no
próprio texto que uma execução é `field_proven` e não `repeatable`. Este lote
mede a repetição.

Com ele, o `replace` passa a ter as **duas classes de alvo** medidas em N=10 —
objeto criado pelo plano (`docs/50`) e objeto preexistente (aqui) — e o gate da
R2 — *atômica, verificável, reprodutível e reversível* — tem três das quatro
palavras medidas.

A `CAPABILITY_MATRIX` **não ganhou linha nenhuma**: a linha do `replace` que já
existia passou a descrever as duas classes de alvo. O Template Profile deriva
grau por **operação**, e classe de alvo não é verbo novo. As vinte runs que
sustentam o grau estão no perfil, dez de cada lote — foi o guard
`test_grau_publicado_nunca_excede_o_que_o_PERFIL_deriva` que recusou a primeira
tentativa, em que uma linha separada trazia grau sem lastro no perfil.

```text
10 runs solicitadas       10 iniciadas         10 concluídas
10 plan_executed          2 passos executados, 3 delegados, de 5 (em todas)
10 before_hash_verified   e3b0c442…b855 conferido no campo nas dez
10 build_verified         0 erros, 0 aviso de convenção do fabricante
10 factory_output_verified  1 de 1 objeto em cada
10 only_authorized_changed  42 nós idênticos em cada
10/10 equivalentes        independência limpa nos 45 pares
10 template intacto       596625…815f5 antes e depois, nas dez
10 sealed_complete        dez pacotes de evidência, nenhuma falta
```

## Entradas, congeladas por hash

| O quê | Valor |
|---|---|
| Spec | `C:\mastertool-x-r1\specs\w10-edit-existing-v1.json` |
| Spec sha256 | `2c2efcbdc424…f0933698` |
| Template | `TemplateExemplo v1.project`, sha256 `596625796e4e…815f5` |
| Alvo | `programs:UserPrg:implementation` — **preexistente** |
| `expected_before_sha256` | `e3b0c44298fc…852b855`, **medido** (`docs/50`) |
| Fase de autoria | `W10_EDIT_EXISTING` |
| Fase de build | `W10_VERIFY_BUILD` |
| Lote | `C:\mastertool-x-r1\qualificacao-w10-n10` |
| Preflight | `preflight-w10-n10-plan.json` / `-build.json`, ambos liberados |
| `HEAD` na abertura | `fd09efa`, árvore limpa |

<caption>

**Como ler:** o `plan_sha256` é o **mesmo** nas dez (`c75592f5…9721ab`), e o
relatório o classifica como volátil permitido com *um* valor distinto. Isso é o
esperado e não é redundância: mesma spec e mesmo planner offline têm que
produzir o mesmo plano. O que varia entre as runs é a saída — dez `.project`
distintos, porque o arquivo carrega GUID e timestamp.

</caption>

## Os três volumes de variação, e por que nenhum reprova

| Campo | Valores distintos em 10 | Leitura |
|---|---|---|
| `plan_sha256` | 1 | o planner é determinístico; qualquer outro número seria o achado |
| `generated_at` | 10 | relógio — variação obrigatória |
| `output_project_path` | 10 | cada run tem diretório próprio, por construção do lote |

<caption>

**Como ler:** a equivalência é de **conteúdo**, não de bytes. Comparar o
`.project` inteiro reprovaria sempre, e por motivo nenhum: o formato carrega
identificadores sorteados a cada gravação. O que o comparador confere é o que a
alteração deveria ter produzido.

</caption>

## Reversibilidade, e o que dela está medido

O gate da R2 pede *reversível*. O que este lote mede é a metade estrutural
dela: **o arquivo de entrada fica intacto byte a byte**, conferido por sha256
antes e depois, nas dez. O executor nunca chama `save()` — só `save_as` — então
desfazer é descartar a saída, e o original nunca esteve em risco.

O que **não** está medido é a reversão de uma alteração já aceita: aplicar o
texto anterior de volta sobre a saída, com o mesmo rigor de `expected_before`.
Isso é uma execução que ninguém fez, e o pacote de evidência guarda o texto
anterior por hash, não por conteúdo — reverter a partir dele exigiria o texto,
que não está no pacote. Fica registrado como pendência (`r2-reversao-medida`).

## O que este lote NÃO estabelece

- **Não promove `template_qualified`.** As duas lacunas do perfil seguem
  abertas: inventário de dispositivos e library lock.
- **Não cobre `configure_existing_task` nem `rename_object`.** As duas
  operações que a R2 lista continuam sem metade do caminho — a primeira sem a
  busca por task preexistente no executor, a segunda proibida nominalmente.
- **Não amplia a cobertura textual da comparação.** Os dois lados leem o mesmo
  conjunto — o objeto que o plano tocou. A camada de árvore cobre o projeto
  inteiro (42 nós); a de texto, não.
- **Não mede um alvo com texto não vazio.** A `UserPrg` do template tem
  implementação vazia, e `e3b0c442…b855` é o sha256 da string vazia. A
  conferência do "antes" foi exercida contra esse valor; um alvo com conteúdo
  real exercitaria o mesmo código com outro dado, e ninguém fez isso ainda.
- **Não diz que o CLP executa.**

## Limites

**O que a evidência comprova:** que a alteração de um objeto preexistente é
reprodutível no MasterTool X 4.1.0.11 sobre o `TemplateExemplo v1.project` — dez execuções
independentes, dez conferências do hash anterior no campo, dez builds sem erro
e sem aviso de convenção, dez verificações aprovadas, dez comparações
antes×depois sem mudança não autorizada, e o template intacto nas dez.

**O que exige medição em campo:** reversão medida de uma alteração aceita;
alvo com texto anterior não vazio; alteração de propriedade de task
preexistente; renomeação; inventário textual de cobertura ampla; e outra
versão do produto, outro template, outra máquina.
