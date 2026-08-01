# Investigação: a API de parâmetros de dispositivo não substitui o export XML

Registro de um caminho investigado e **descartado com evidência**. Ele existe
para que ninguém refaça a investigação supondo que ela nunca foi feita, e para
que a conclusão negativa não seja confundida com "não tentamos".

## A pergunta

Onde a API de scripting expõe o **valor configurado** de um parâmetro de
dispositivo — IP do scanner, Unit ID de um escravo Modbus, mapeamento de canal?

## O que a evidência estática mostrou

`ScriptDriverDeviceObject.plugin` v4.1.0.0 tem **859 membros públicos**, e a
superfície é **byte a byte idêntica** entre MasterTool 3.63 e 3.70 (mesmas 859
chaves de `(tipo declarador, membro, categoria, assinatura, getter, setter,
origem)`). As interfaces reais vivem em `ScriptEngine3`, não no plugin.

A cadeia declarada é completa:

```text
no da arvore (IScriptObject)
  -> IScriptDeviceObject3.device_parameters { get; }
  -> IScriptDeviceParameterSet   (by_id, contains, Item, get_device_object, enumeravel)
  -> IScriptDeviceParameter      E-UM IScriptDataElement
  -> IScriptValueDataElement.value { get; set; }      valor configurado
     IScriptValueDataElement.default_value { get; }   padrao do device description
     read_online_value(Int32 nTimeOut)                ONLINE — fora de escopo
```

`IScriptDeviceParameter` **estende** `IScriptDataElement`: um parâmetro **é**
um data element, não há passo de navegação entre eles.

## O que a execução real mostrou

**Fase 0** (`probes/22_probe_device_parameter_set_link.py`) — o elo existe:
`node.device_parameters` devolve `ScriptMappableDeviceParameterSet`,
implementando `IScriptDeviceParameterSet` e `IScriptMappableDeviceParameterSet`.
O padrão de extensão que **falhou** para Ladder (probe 18: `Extender` devolve o
mesmo `ScriptObject`, não um provider) **funciona** para device.

**Fase 1** (`probes/23_inventory_device_parameters_readonly.py`) — e aqui o
caminho morre:

```text
20 dispositivos    16 com device_parameters do tipo correto    4 sem o membro
parametros lidos: 0        Count = 0 em TODOS os 16
```

No mesmo projeto e no mesmo instante, o export XML continha **1742 elementos
`<Parameter>` com valor**. Os parâmetros existem; `device_parameters` não os
expõe.

## Conclusão

**Resultado vazio não significa ausência de configuração no projeto.** Significa
que este caminho de API não a alcança. A configuração de fieldbus vive no blob
de extensão do fornecedor (`configurations > addData > data`), que apenas o
serializador XML escreve.

Caminhos alternativos verificados estaticamente, todos negativos:

| Caminho | Resultado |
|---|---|
| `connectors` → `IScriptDeviceConnector` | as interfaces não declaram membro próprio |
| `get_device_communication_settings()` → `IScriptCommunicationSettings` | 15 getters, mas de **gateway IDE↔CLP** (`device_address`, `prompt_at_login`, `secure_online_mode`), não de fieldbus |
| `IScriptGateway.perform_network_scan()` | varredura de rede ativa — proibido |

O mecanismo efetivo é o export XML **por dispositivo**, documentado em
[23-export-por-dispositivo.md](23-export-por-dispositivo.md).

## Riscos registrados desta superfície

- **Leitura e destruição no mesmo objeto.** `ScriptDeviceParameterSet` expõe
  `Add`, `Clear`, `Insert`, `RemoveAt` ao lado dos getters; `IScriptDeviceObject`
  carrega `unplug()`, `update()` e doze sobrecargas de
  `set_gateway_and_ip_address(...)`. Qualquer probe aqui precisa de **whitelist
  literal de nomes**, nunca `dir()`, nunca `getattr` com nome computado.
- **Ausência de setter não é ausência de efeito colateral.** `IScriptOnlineDevice`
  1–7 vive no mesmo assembly, e `device_repository` está marcado em
  `common/compatibility.py` como capaz de iniciar comunicação ao ter
  propriedades lidas.
- `value` é `{ get; set; }` — o único membro que responderia a pergunta é
  também o único com setter.

## Fase 2 não foi aprovada como caminho operacional

Um probe de leitura explícita de `parameter.value` chegou a ser escrito, com
allowlist literal e acesso escrito no código. **Nunca foi executado** — a Fase 1
mostrou que não há parâmetro nenhum para ler — e **não está versionado**. Ele
foi preservado fora do Git como histórico.

Versioná-lo daria a impressão de um caminho suportado onde há um beco sem saída
já medido.

## Escopo dos dois probes versionados

Ambos são **experimentais e documentados**, não fluxo de produção:

- `22_probe_device_parameter_set_link.py` — comprova o elo, lê **nenhum** valor,
  lista fechada de dois candidatos com acesso literal, e o `Count` como único
  getter escalar. Vale como evidência de que a extensão de device chega ao
  objeto Python.
- `23_inventory_device_parameters_readonly.py` — inventário getter-only,
  isolamento por dispositivo. Vale como **evidência negativa reproduzível**:
  rodar de novo deve dar `Count = 0` outra vez, e se um dia der diferente, isso
  é achado.

Nenhum dos dois traz lista default de dispositivos: `--node-id`/`--node-ids` são
obrigatórios e vêm da varredura do probe 21. Uma lista embutida seria a
estrutura de um projeto específico dentro do repositório.
