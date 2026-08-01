# Compatibilidade entre versões e o defeito do serializador monolítico

Achados de campo em MasterTool IEC XE **3.70**, comparados com o 3.63 que o
projeto usava até então. Nenhum dado de projeto real aparece aqui.

## A API de scripting não mudou entre 3.63 e 3.70

Medido por reflection somente-metadados, sem abrir o MasterTool:

| O que | Resultado |
|---|---|
| Assemblies de scripting | idênticos: `ScriptEngine.plugin`, `ScriptEngine3`, `ScriptDriverProjects`, `ScriptDriverSystem`, `ScriptDriverDeviceObject`, `ScriptDriverOnline` — todos `4.1.0.0` |
| Catálogo estático dos tipos que usamos | **byte a byte idêntico**, normalizando apenas o caminho de instalação |
| `ScriptDriverDeviceObject` | **859 membros públicos, mesmas chaves** nas duas versões |

A preocupação com a troca de versão ficou resolvida por medição, não por
suposição. O que muda entre versões é o **repositório de dispositivos**, não a
API.

### Uma diferença real, pequena e útil

O banner de `sys.version` mudou:

```text
3.63   "MT8500.exe MasterTool IEC XE, ScriptEngine.plugin 4.1.0.0"
3.70   "MT8500.exe MasterTool IEC XE 3.70, ScriptEngine.plugin 4.1.0.0"
```

Em 3.70 o banner **carrega o número da versão**; em 3.63 não carregava. A
matriz de compatibilidade registra que `sys.version` devolve banner de produto
e não versão de Python — isso continua verdade, mas a partir do 3.70 dá para
extrair a versão do produto dele.

## O repositório de dispositivos é por versão

```text
C:\ProgramData\MT8500 <versao>\Devices\<Type>\<Id>\<Version>\
```

Cada versão instalada tem o **seu** repositório, independente. Uma device
description importada no 3.63 **não** está disponível no 3.70. Numa máquina
com dez versões instaladas, a mesma máquina pode simultaneamente conseguir e
não conseguir abrir o mesmo dispositivo, dependendo da versão usada.

O `Id` do diretório codifica a identidade CIP quando o dispositivo veio de um
EDS importado:

```text
Id = VendorID _ DeviceType _ ProductCode _ MajorRevision
```

Isso torna o repositório **indexável por identidade numérica** — e permite
cruzar, offline, o que um projeto referencia contra o que está instalado.

## O defeito: o serializador monolítico perde tudo por uma falha localizada

`export_xml` sobre o projeto inteiro é **monolítico**. Observado num projeto
real: duas exportações independentes, modos diferentes, 42 minutos de
intervalo, **abortaram no mesmo nó**, nenhuma fechando `</project>`.

Um arquivo de 9 MB parecia pronto e não era. Iam junto: servidor e cliente
MODBUS, sete escravos, todos os adaptadores EtherNet/IP e duas interfaces de
rede — **1636 elementos `<Parameter>` perdidos por causa de quatro
dispositivos**.

### A causa, que só o isolamento revelou

Exportando **um dispositivo por vez** (`probes/25`), a mesma falha vira quatro
erros isolados e nomeados:

```text
Exception("No devdesc installed for '<nome>'")
```

Quatro adaptadores cuja device description não estava instalada **naquela
versão**. O serializador monolítico bateu nisso e abortou o arquivo inteiro
sem reportar nada; o export por dispositivo salvou os outros 31 e disse
exatamente o que faltava.

Depois de instalada a descrição, os quatro passaram a exportar e o total subiu
para 1894 parâmetros — **mais do que o export monolítico chegou a escrever
antes de morrer**.

## Consequências práticas

1. **Nunca confie num export monolítico sem verificar o fechamento do
   elemento raiz.** Um arquivo grande e plausível pode estar truncado, e nada
   avisa. `probes/25` mede isso por dispositivo.
2. **Uma device description ausente é falha localizada, não do projeto.** O
   isolamento por dispositivo transforma um bloqueio total numa lacuna de
   cobertura declarada.
3. **Diff entre exportações precisa ignorar `creationDateTime`** do
   `<fileHeader>` — o MasterTool o carimba com fração de segundo de largura
   variável, e duas exportações idênticas diferem nessa única linha.
4. **`object_guid` não é identidade estável entre sessões** para nós de
   referência de POU sob Task Configuration nem para `__VisualizationStyle`
   (ver `docs/22`). Comparar varreduras por ele produz mudança fantasma.

## Onde o caminho pela API de parâmetros falha

Registrado em [24-investigacao-api-de-parametros.md](24-investigacao-api-de-parametros.md):
`device_parameters` existe, é alcançável e tem o tipo correto — e vem
**vazio** para todos os dispositivos, enquanto o export XML dos mesmos
dispositivos, no mesmo instante, traz milhares de parâmetros com valor.

O mecanismo efetivo para configuração de dispositivo é o **export XML por
dispositivo**, não a API de parâmetros.
