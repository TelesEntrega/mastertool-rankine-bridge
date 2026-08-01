# Inventário determinístico de configuração de dispositivo

`src/mastertool_bridge/inventory/device_inventory.py` mais o CLI
`tools/build_device_inventory.py` — constroem, **offline**, o inventário de
configuração a partir de exports por dispositivo (`probes/25`) e da topologia
(`probes/21`).

Não abre o MasterTool, não reexporta, não toca o repositório de dispositivos.

## Dados reais ficam fora do repositório

Os artefatos gerados carregam nomes de equipamento, endereços e configuração
de um projeto real. **Eles nunca entram na árvore do repo**, e o CLI recusa
`--output` apontando para dentro dele — com `exit 2`, antes de ler qualquer
coisa.

O que fica versionado é só o **método**: o parser, as regras, os testes com
fixtures sintéticas e esta documentação. Nenhuma fixture de teste contém IP,
nome de planta ou caminho local.

## Duas camadas, deliberadamente separadas

| Camada | O que é | Regra |
|---|---|---|
| **bruta** | uma ocorrência por `<Parameter>` | **nada é descartado**, nada é reinterpretado |
| **interpretada** | leitura técnica | só onde há evidência estrutural |

A bruta é o registro; a interpretada é a leitura. Misturá-las faria a leitura
apagar o registro — e um dia alguém precisaria justamente do parâmetro que a
regra da época achou irrelevante.

## Quatro estados de valor, nunca colapsados

```text
presente     ha texto util, INCLUSIVE "0"
estruturado  <Value> carrega elementos filhos (tipo struct)
vazio        <Value/> sem texto e sem filho
ausente      nao existe elemento <Value>
```

`0` é configuração legítima e não pode virar "vazio". E tratar `estruturado`
como vazio seria mentir: numa medição real, 984 de 1894 parâmetros tinham
`<Value>` com filhos — mais da metade teria virado "vazio" por engano. Foi um
defeito real, pego e corrigido antes de qualquer entrega.

## Hierarquia de evidência

```text
1. token semantico explicito no `type` ................... high
2. ParameterId conhecido CORROBORADO pelo nome esperado .. high
3. nome exato + forma do valor + contexto estrutural ..... medium
4. nome isolado .................. NAO interpreta -> unresolved
```

O contexto de protocolo vem de `DeviceIdentification/Type` e de
`Connector/@interface`. **O nome do dispositivo nunca é evidência** — é
convenção da planta e muda entre projetos.

Não existe nível `low`. Nome isolado virou candidato, não fato.

### Por que o `ParameterId` sozinho não basta

Ids como `0`, `1` e `2` existem em praticamente toda device description. Sem
corroboração pelo nome, um parâmetro de flags chamado `Supported Functions`
(id 0) foi classificado como `ip_address`, e um `Dummy Parameter` (id 1) como
`subnet_mask`. Falso positivo real, observado numa execução e corrigido — daí
a exigência do nome esperado, com teste dedicado.

### Por que a forma do valor entra na regra

`SubnetMask` com valor `0` não é máscara. A regra exige forma `ip4`
(`[a, b, c, d]`) para IP, máscara e gateway. Sem isso, parâmetros homônimos
de módulos de I/O locais entravam como configuração de rede.

## Inventário composto

Quando as runs vêm de **hashes de projeto diferentes** — por exemplo, quando
uma device description é instalada entre uma coleta e outra e dispositivos que
antes falhavam passam a exportar — o resultado **não é um snapshot único**.

```text
inventory_snapshot_kind = "single"     uma origem
inventory_snapshot_kind = "composite"  duas ou mais
```

Cada registro carrega `project_state`, `project_sha256`, `run_dir`,
`source_file` e `source_sha256`. A instalação de um EDS não apaga a
procedência dos exports anteriores.

Um inventário composto **não prova que os dispositivos coletados antes não
mudaram** entre os dois estados, e não deve ser usado como snapshot forense.
Isso fica declarado no manifesto, não escondido.

## Cobertura estrutural × cobertura de parâmetros

São coisas diferentes e o relatório separa as duas. Nós de barramento e slot
exportam com sucesso e trazem **zero** parâmetros — não é falha de cobertura.
Numa medição real: 35 dispositivos exportados, 29 com parâmetros, 6
barramentos/slots legítimos sem nenhum.

## Determinismo

Nenhum timestamp entra nas saídas. Duas execuções sobre as mesmas runs
produzem os sete arquivos byte a byte idênticos — verificado por SHA-256
arquivo a arquivo. O `manifest.json` é escrito por último e traz o hash das
demais saídas; ele não contém o próprio.

## Uso

```text
python tools/build_device_inventory.py \
    --run <run_dir>:<estado>:<sha256_do_projeto> \
    --run <outra_run>:<estado>:<sha256> \
    --topology <run_do_probe_21> \
    --output <diretorio_FORA_do_repositorio>
```

Quando o mesmo dispositivo aparece em mais de uma run, o CLI **recusa** por
padrão: escolher em silêncio qual versão vale seria decidir procedência sem
dizer. `--prefer-latest-run` torna a escolha explícita.

## Saídas

```text
parameters-raw.json / .csv        camada bruta, nada descartado
communication-inventory.json/.csv camada interpretada, com regra e evidencia
unresolved-parameters.json        o que nao foi interpretado, com motivo
device-coverage.json              cobertura, procedencia e validacoes
manifest.json                     regras usadas e hashes das saidas
```

## Achado registrado — adaptadores EtherNet/IP de inversor

Numa aplicação real, quatro adaptadores EtherNet/IP filhos do scanner não
exportavam (`No devdesc installed`). Instalada a device description, os quatro
passaram a exportar e revelaram **o mesmo produto**:

```text
Vendor Code 853   Product Type 2 (AC Drive)   Product Code 3072
Major.Minor Revision 4.1   Vendor WEG   Produto CFW500
Type=101   Id=853_2_3072_4
```

Dois pontos que a medição estabeleceu:

- **um único EDS resolveu os quatro** — eles eram o mesmo modelo, o que não
  era demonstrável antes: os prefixos de nome diferiam e só dois dos quatro
  apareciam na lógica da aplicação;
- a identidade do device description sai com confiança **alta**, mas os
  parâmetros de comunicação (IP, RPI, assemblies) ficam em **média**: vêm de
  estruturas com tipos genéricos (`ARRAY[0..3] OF BYTE`, `DWORD`) e contexto
  semântico indireto. Elevá-los a alta seria confortável e errado.

**Electronic Keying** representa a identidade *esperada e configurada pelo
scanner*. Não comprova, por si só, o modelo e a revisão do equipamento
fisicamente presente na rede.
