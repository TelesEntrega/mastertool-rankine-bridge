# Visão geral

> **HISTÓRICO — SUPERADO.** Este documento descreve um estado que já não é o
> vigente. Ele é preservado sem alteração como registro do que se sabia na
> época. O estado corrente está em [`CURRENT_STATUS.md`](CURRENT_STATUS.md);
> o plano corrente, em [`ROADMAP.md`](ROADMAP.md).
>
> **O que mudou:** a tabela de fases desta página diz que a compilação não foi implementada e que a importação está bloqueada. As duas afirmações foram superadas: o `build` do MasterTool X é executado e verificado desde a W1.4, e a autoria controlada foi comprovada em campo de W1 a W9.

O **mastertool-rankine-bridge** cria uma ponte auditável entre o MasterTool IEC XE 3.63
(CLPs Altus Nexto, especialmente NX3008) e o ecossistema Python 3 / Git / agentes de IA.

```text
MasterTool IEC XE 3.63
        │
        │ IronPython / ScriptEngine
        ▼
Exportação estruturada do projeto
        │
        ▼
Repositório textual versionável
        │
        ├── Git
        ├── agentes de IA (Codex, Claude, ...)
        ├── analisadores estáticos
        ├── documentação automática
        └── comparação entre versões
```

## Fases

| Fase | Nome | Estado |
|------|------|--------|
| 0 | Descoberta do ambiente | scripts prontos, aguardando execução no MasterTool |
| 1 | Exportação somente leitura | parcial (árvore); exportador completo pendente |
| 2 | Análise externa | base implementada |
| 3 | Compilação e validação | não implementada |
| 4 | Importação controlada | bloqueada por política |

## Princípio central

Nada escreve no projeto original, no CLP ou em hardware. O fluxo completo é:

```text
descoberta → exportação → validação → análise → documentação → compilação → alteração controlada
```

Cada etapa só é liberada quando a anterior está testada e aprovada por humano.
Detalhes de segurança: [08-safety.md](08-safety.md).
