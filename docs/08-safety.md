# Política de segurança

Arquivo normativo: [`config/safety-policy.yaml`](../config/safety-policy.yaml).
Este documento explica a política; em divergência, o YAML prevalece.

## Proibições permanentes (sem flag, sem exceção)

- Alterar o projeto original do MasterTool;
- Download para o CLP; modo online; login no NX3008;
- Start/stop/reset do controlador; forçar variáveis; escrever em saídas físicas;
- Alterar configuração de hardware automaticamente;
- Instalar bibliotecas sem autorização explícita;
- Importar sem backup; aplicar alterações de IA diretamente no projeto oficial.

Implementação: `scripts/mastertool/common/safety.py` (fail closed, dentro do
MasterTool) e `src/mastertool_bridge/changes/validator.py` (camada externa).

## Portas obrigatórias para escrita futura (Fase 4)

1. cópia de trabalho → 2. backup → 3. diff textual → 4. validação estrutural
→ 5. compilação → 6. **aprovação humana registrada**.

## Níveis de risco

| Nível | Exemplos | Tratamento |
|-------|----------|------------|
| Baixo | comentários, documentação, formatação, relatórios, código externo | aprovação humana simples |
| Médio | lógica interna de função, cálculos, refatoração sem saída física, diagnóstico, GVL sem mapeamento físico | compilação + aprovação |
| Alto | máquinas de estado, permissivos, alarmes, timers de processo, sequenciamento, MES, OPC UA, intertravamentos, RETAIN/PERSISTENT | compilação + simulação + aprovação |
| Crítico | saídas físicas, `%Q`, segurança de máquina, parada de emergência, robô, válvulas, motores, inversores, hardware, redes industriais, download | **nunca automático**; processo manual com avaliação de risco documentada e aprovação sênior |

## Alertas heurísticos

As verificações de `analysis/safety_checks.py` (escrita dupla de saída, `%Q`
direto, FOR com limite calculado, índices computados, ponteiros, RETAIN etc.)
são **alertas para revisão humana**. Um agente de IA nunca deve tratá-los como
erro confirmado nem "corrigi-los" automaticamente.

## Logging

Toda execução gera log estruturado (JSON Lines) com: timestamp, level, script,
operation, project, object, result, error, duration_ms, read_only. **Nunca**
registrar senhas, tokens, credenciais ou conteúdo sensível.
