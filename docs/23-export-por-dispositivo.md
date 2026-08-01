# Exportação PLCopen dispositivo a dispositivo

`probes/25_export_devices_individually.py` — exporta cada dispositivo da
árvore num arquivo próprio, para que uma subárvore que o serializador recusa
não destrua a exportação de todas as outras.

## O problema

O `export_xml` do projeto inteiro é um **serializador monolítico**. Num
projeto industrial real, duas exportações independentes — modos diferentes,
42 minutos de intervalo — abortaram **no mesmo nó**, nenhuma fechando
`</project>`. O arquivo de 9 MB parecia pronto e não era.

O que se perdia junto: servidor e cliente MODBUS, sete escravos Modbus, todos
os adaptadores EtherNet/IP e duas interfaces de rede. Reexportar do mesmo
jeito não resolve: o defeito é reprodutível.

## A saída

`export_xml` vive em `IScriptObject` — ou seja, em **qualquer nó da árvore**,
não só no projeto. Exportando um dispositivo por vez, a subárvore problemática
falha sozinha.

Resultado no mesmo projeto: **35 dispositivos, 31 exportados, todos os 31
fechando `</project>`, zero truncados**, e **1742 elementos `<Parameter>`
recuperados** — mais do que os 1636 que o export monolítico truncado chegou a
escrever antes de morrer.

## A causa-raiz, que só o isolamento revelou

As 4 falhas são idênticas e nomeadas:

```text
Exception("No devdesc installed for '<nome>'")
```

São os quatro adaptadores EtherNet/IP, filhos do scanner — exatamente o nó
onde o export monolítico morria. **A device description deles não está
instalada nesta instalação do MasterTool.** O serializador monolítico bateu
nisso e abortou o arquivo inteiro sem reportar; o export por dispositivo
transforma a mesma falha em quatro erros isolados e salva os outros 31.

Um erro isolado de dispositivo **não invalida** os XML completos já
exportados. Ele reduz a cobertura — e a cobertura é declarada.

## Invocação

Idêntica à comprovada pelo probe 19 (reflexão) e exercitada pelo probe 20
(invocação real):

```text
target.export_xml(st_path, recursive, False, False)
```

Quatro argumentos explícitos, sobrecarga **sem** `IExportReporter`. Nunca
`MethodInfo.Invoke()`. Nunca `import_xml`, que segue permanentemente fora de
escopo.

### Diferença de perfil em relação ao probe 20

O probe 20 autoriza **exatamente uma** invocação. Este autoriza **uma por
dispositivo** da lista fechada. A contenção muda de "uma escrita" para "N
escritas, cada uma num diretório próprio, vazio, criado por este probe dentro
da sua run, com o caminho de destino inexistente antes da chamada". Nenhuma
escrita fora da run. Nenhum arquivo sobrescrito, nunca.

Isso está declarado no cabeçalho do probe e na `safety_declaration` do
manifesto, não escondido.

## Argumentos

| Argumento | Default | Observação |
|---|---|---|
| `--output` | — | **obrigatório**, sem espaço, fora do repositório |
| `--node-ids` | — | **obrigatório**, lista fechada separada por vírgula |
| `--recursive` | `0` | `1` exporta a subárvore de cada dispositivo |

**Não existe lista default de dispositivos.** Uma lista embutida seria a
estrutura de um projeto específico dentro do repositório. Os `node-id` são
caminhos de índices produzidos pela varredura do probe 21 —
`root/1/1/0/2/0`, nunca nomes: nome depende de encoding e do idioma do
projeto, e o mesmo nome repete em ramos diferentes.

## O que é medido por dispositivo

Arquivo criado, tamanho, SHA-256, e se o conteúdo **fecha `</project>`** —
assinatura direta do truncamento. Um export que não fecha é registrado como
truncado, jamais apresentado como completo.

| Status | Quando | Exit |
|---|---|---|
| `complete` | todos exportaram e fecharam | 0 |
| `complete_with_export_errors` | erros isolados; os demais válidos | 0 |
| `truncated_outputs` | **qualquer** arquivo sem fechar | 2 |
| `fatal` | não foi possível exportar | 1 |

`truncated_outputs` tem **precedência sobre erro isolado**.

## O que o export por dispositivo entrega, e o que não entrega

Entrega os parâmetros com valor: `<Parameter ParameterId type IndexInDevDesc>`
com filhos `<Value>`, `<Name>`, `<Description>`, `<Unit>`. Foi assim que
saíram IP, máscara, gateway, porta TCP, Unit ID dos escravos Modbus, timeouts
e ciclos de tarefa.

Não entrega nada dos dispositivos sem device description instalada. Enquanto
houver um deles, **o inventário não é completo** e não deve ser apresentado
como tal.

## Por que não pela API de parâmetros

Porque não funciona neste projeto. Ver
[24-investigacao-api-de-parametros.md](24-investigacao-api-de-parametros.md).

## Execução

Sobre **cópia descartável**, offline, UI visível, sem salvar:

```text
MT8500.exe --project="<...>\_descartavel\<Projeto> COPIA.project"
           --runscript="<repo>\scripts\mastertool\probes\25_export_devices_individually.py"
           --scriptargs:"--output=C:\saida-export --recursive=0 --node-ids=root/1/1/0,root/1/1/0/2"
```

O caminho de saída não pode conter espaço, e a lista de `--node-ids` também
não — o MT8500 quebra o valor de `--scriptargs` em espaço em branco.

## Observação sobre reprodutibilidade

Duas execuções do mesmo probe sobre o mesmo projeto produzem exports que
diferem em **exatamente uma linha**: o `creationDateTime` do `<fileHeader>`,
que o MasterTool carimba com fração de segundo de largura variável. Todo o
resto é byte a byte idêntico. Um diff entre exportações deve ignorar essa
linha, ou toda comparação acusará mudança que não existe.

A lógica testável — slug ASCII, detecção de truncamento, classificação de
status — vive em `common/device_export_inspection.py`, com testes em
`tests/unit/test_device_export_inspection.py`.
