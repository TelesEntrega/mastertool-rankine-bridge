# Qualificação read-only do `TemplateExemplo v1.project`

> Registro de execução. Duas sessões: `run-010`, que mediu e **revelou dois
> defeitos de contrato de artefato**, e `run-011`, que repetiu a medição sobre
> cópia nova com os defeitos corrigidos. A `run-010` é preservada como registro
> do achado — reescrevê-la apagaria a evidência de que os defeitos existiram.

## 1. Veredito

### O `TemplateExemplo v1.project` está MEDIDO e NÃO está ELEGÍVEL para autoria

A árvore foi varrida por inteiro, o `Application` foi resolvido por busca, e
não há conflito de nome com os objetos que W1.4 pretende criar. Nada disso
autoriza escrever nele: **dois campos não são mensuráveis com a superfície de
API catalogada**, e cada um bloqueia a elegibilidade.

A distinção é a que o contrato determina:

```text
template qualificado ESTRUTURALMENTE  ≠  template ELEGÍVEL PARA AUTORIA
```

Um template com lacuna pode ser inspecionado e registrado. O que ele não pode
é ser selecionado por um executor mutável.

## 2. O que foi medido

| Grandeza | Valor |
| --- | --- |
| Projeto original | 503.040 bytes, `596625796e4e…d1d815f5` |
| Original, depois da sessão | **idêntico** — nunca foi aberto |
| Cópia, antes e depois | **idêntica** ao original nas duas medições |
| Árvore | 3 raízes, **42 nós** |
| `persistent_tree_sha256` | `162d4fd747532bc0d9a6f22dc12eeaabcf59397ec4210e6787f68f1edf89f647` |
| `Application` | `root/1/0/0`, `639b491f-…`, **match único** |
| Tasks | `MainTask` (`root/1/0/0/3`) |
| Conflito de nome | **nenhum** — `GVL_AI_TESTE` e `PRG_AI_TESTE` não existem |
| `.opt` | 2, confinados no diretório da sessão |
| Diálogos · órfãos · mutadores | 0 · 0 · 0 |

<caption>

**Como ler:** o hash do original aparece uma vez porque é o **mesmo** antes e
depois — a proteção não vem de atributo de arquivo, vem de o wrapper copiar e
nunca abrir o original. `persistent_tree_sha256` carrega ressalva no próprio
artefato: cobre a árvore inteira, não só os objetos persistentes, porque o
scanner reaproveitado não lê `is_transient_object` por nó.

</caption>

### `root/1/0/0` continua valendo — e isso foi medido, não presumido

O node_path do `Application` é o mesmo da base anterior, apesar dos cartões de
I/O. **Presumir isso teria dado certo por sorte.** `node_path` é caminho de
índices, e cartões de I/O mudam a árvore sob o `Device`; o probe resolve o
container por **busca** (nome + `type_guid`) e reporta o que achou, em vez de
receber o caminho pronto. Foi por isso que a medição respondeu à pergunta em
vez de confirmar uma suposição.

### Inventário por `type_guid`

| Classificação | Contagem |
| --- | --- |
| dispositivo/hardware | 11 |
| GVL | 7 |
| POU ou DUT (indistinguíveis) | 4 |
| `Application` | 1 |
| **não catalogado** (`e9159722-…`) | **5** |
| outros não catalogados | 8 |

<caption>

**Como ler:** "POU ou DUT indistinguíveis" não é imprecisão do inventário — o
`type_guid` `6f9dac99-…` é o mesmo para `PROGRAM`, `FUNCTION_BLOCK` e
`FUNCTION`, medido desde W1.2. Os 13 nós não catalogados são hardware e nós de
configuração cujos GUIDs nunca entraram em `docs/27`; ficam listados como
`unclassified` em vez de omitidos.

</caption>

## 3. Os dois bloqueadores

### `compiler_version_unresolved`

`IScriptProjectSettings2.get_compilerversion()` **está** catalogado, mas
**nenhum membro catalogado devolve uma instância de `IScriptProjectSettings2`**
a partir de `IScriptProject` ou `IScriptApplication`. Falta o acessor, não o
método. O artefato registra a lacuna com status, origem e razão, em vez de um
`None` que o próximo leitor teria de interpretar.

### `libraries_unresolved`

O nó "Library Manager" **foi alcançado** — `root/1/0/0/0`, status `resolved` —
e devolveu **zero filhos**, num projeto industrial com cartões de I/O. Zero
biblioteca ali é implausível: bibliotecas não são expostas como filhos daquele
nó via `get_children`.

Uma lista vazia lê como "medido: nenhuma biblioteca". O que se tem é "não
mensurável por este caminho". São conclusões opostas para quem decide, e a
diferença só existe se alguém escrever — agora o campo sai como
`resolved_but_empty` com a lacuna anexada.

## 4. Os dois defeitos que a run-010 revelou

Ambos da mesma família: **campo que se apresenta como resultado quando é
lacuna**.

**O artefato de conclusão se contradizia.** `qualify-completion.json` trazia
`status: "qualified"` e não carregava `authoring_eligible`,
`qualification_status` nem `blocking_issues` — eles existiam no `analysis` e no
`registry-candidate`, mas não no arquivo que o wrapper lê para dar veredito. A
`run-010` imprimiu **"VEREDITO: APROVADO"** para um template inelegível.

`status` responde "a varredura deu certo?"; elegibilidade responde "dá para
escrever neste template?". Colapsar as duas numa palavra só produziu a
contradição. Um artefato de conclusão que precisa de outro arquivo ao lado
para não ser lido errado não está concluindo nada.

**A lista de bibliotecas vazia**, descrita acima, foi o segundo.

Correção em `3e0434a`, com código de saída por camada:

| exit | significado |
| --- | --- |
| `0` | varredura ok **e** template elegível |
| `4` | varredura ok, template **não** elegível |
| `3` | varredura reprovada |

<caption>

**Como ler:** o `4` existe para que "medi tudo mas não posso escrever" não se
confunda com "a varredura falhou". As duas situações exigem ações opostas: uma
manda medir o que falta, a outra manda investigar a varredura.

</caption>

## 5. Limites

**O que a evidência comprova:** que a árvore do `TemplateExemplo v1.project` é varrível por
inteiro sem tocar o arquivo; que o `Application` resolve em `root/1/0/0` com
match único **neste arquivo, identificado por sha256**; que não há conflito com
os nomes que W1.4 pretende criar; e que a sessão read-only não altera original
nem cópia.

**O que exige medição em campo:**

- **A compiler version.** Falta o acessor catalogado (§3).
- **As bibliotecas.** Falta o caminho de API que as exponha (§3).
- **Se `root/1/0/0` continua valendo depois de qualquer edição do template.**
  O node_path está amarrado ao `sha256` **deste** arquivo, e o registry recusa
  usá-lo com outro — mudar o template invalida a medição.
- **O que são os 13 nós não catalogados.** Estão contados e classificados como
  `unclassified`, não omitidos, mas ninguém sabe o que são.
- **Se `persistent_tree_sha256` distingue persistente de transiente.** Não
  distingue hoje, e a ressalva viaja no próprio campo.

## 6. Estado

`W1_4_INTEGRATED_BUILD` **não existe** e não pode ser aberta sobre este
template enquanto houver bloqueio. `CONTROLLED_WRITE_PHASE = None`,
`READ_ONLY_PHASE = True`.

O próximo passo não é W1.4: é **transformar o `TemplateExemplo v1.project` de template
medido em template elegível**, resolvendo os dois acessores — por inspeção das
assemblies do ScriptEngine, e, se ela não bastar, por reconhecimento read-only
próprio.
