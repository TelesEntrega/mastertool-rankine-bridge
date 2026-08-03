# run_repeatability_batch.ps1 -- o LOTE da fase R1: a mesma spec, N vezes.
#
# Contrato: docs/ROADMAP.md secao R1. Mecanismo e veredito:
# `src/mastertool_bridge/automation/repeatability.py` e
# `generation_equivalence.compare_many`.
#
# O QUE ESTE WRAPPER FAZ, E O QUE ELE NAO FAZ
# ===========================================
# Ele repete a fabrica N vezes, cada execucao em diretorio proprio, e no fim
# chama o host para julgar o LOTE. Ele nao decide se o lote qualifica -- quem
# decide e `mastertool-bridge qualify-repeatability`, que le o que ficou em
# disco. A separacao e a de sempre: quem executa e a sessao supervisionada,
# quem verifica e o host.
#
# FAIL-CLOSED: sem -Execute ele PLANEJA e mostra o que faria, sem abrir nada.
# O modo padrao e o seco, porque um wrapper que executa por omissao transforma
# engano de digitacao em sessao de escrita.
#
# POR QUE CONTINUAR DEPOIS DE UMA FALHA
# ====================================
# Parar na primeira run que falha economiza tempo e destroi a evidencia que
# justifica o lote existir. Continuar mostra a diferenca entre falha isolada,
# falha sistematica, falha dependente da ordem e falha intermitente. O lote
# reprova de qualquer forma: uma run inconsistente reprova a qualificacao
# mesmo com as outras nove aprovadas.
#
# PILOTO ANTES DA QUALIFICACAO
# ============================
# Rodar -Runs 3 primeiro. Um erro mecanico de empacotamento descoberto na
# decima execucao desperdicou dez sessoes de campo sem acrescentar evidencia;
# descoberto na terceira, custou tres.

param(
    [Parameter(Mandatory = $true)]
    [string]$Spec,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [int]$Runs = 3,

    # DOIS ESTAGIOS, e nao um. `run_project_factory.ps1` tem modos mutuamente
    # exclusivos, e -ExecutePlan e -ExecuteBuild rodam sob FASES DIFERENTES
    # (`W7_FACTORY_FULL` e `W7_VERIFY_BUILD`). Nao da para fazer os dois numa
    # passada sem trocar o gate no meio do lote.
    #
    # ACHADO que motivou isto: a VERIFICACAO (probe 47) roda dentro do
    # -ExecuteBuild, nao do -ExecutePlan. Um lote so de planos nao produz
    # `verificacao/`, e o comparador nao teria o que comparar -- o veredito
    # sairia "arvore ausente ou ilegivel" para um lote perfeitamente bom.
    #
    #   plan   -> N execucoes do plano, sob a fase de autoria
    #   build  -> N builds + verificacao, sob a fase de build, e AI o veredito
    [ValidateSet('plan', 'build')]
    [string]$Stage = 'plan',

    # Sem isto, o script so planeja. Ver o cabecalho.
    [switch]$Execute,

    [string]$TemplateProject,
    [string]$TemplateQualification,

    # SEM DEFAULT, de proposito. Doze wrappers deste repositorio fixam o
    # caminho de instalacao do MT9000 e a raiz do repositorio, e isso esta
    # registrado como divida na catraca de `tools/check_repo_hygiene.py`. Um
    # wrapper novo com os mesmos literais faria a divida CRESCER -- e a catraca
    # existe justamente para que ela so encolha. Aqui: `-Exe` so e repassado
    # quando o operador informa (a fabrica tem o proprio default, que e a
    # divida ja registrada), e `RepoRoot` e DERIVADO deste arquivo.
    [string]$Exe,
    [string]$RepoRoot,

    [int]$TimeoutSeconds = 900,
    [switch]$AutoCloseWindow,

    # Piso de execucoes independentes para o veredito. Padrao: o da norma,
    # lido pelo proprio host. Um valor menor aqui NAO afrouxa a fase -- ele
    # documenta um ensaio, e o relatorio registra o piso usado.
    [int]$Minimum = 0,

    # IDENTIDADE DA FASE DE BUILD, no plano gerado. O probe 40 valida os dois
    # contra listas FECHADAS (`ACCEPTED_OPERATION_IDS`,
    # `ACCEPTED_BUILD_PHASES`), entao um valor errado reprova la, e nao aqui.
    #
    # O padrao e o par da fabrica completa porque foi o primeiro lote a rodar.
    # Um lote com spec que CRIA task usa `w9-prove-task-timing` /
    # `W9_VERIFY_BUILD` -- e a fase de autoria correspondente
    # (`W9_PROVE_TASK_TIMING`) e quem autoriza `create_task`, `add` e as quatro
    # escritas de propriedade.
    [string]$OperationId = 'w7-factory-full',
    [string]$BuildPhase = 'W7_VERIFY_BUILD'
)

$ErrorActionPreference = 'Stop'

# Raiz derivada, nunca fixada: este arquivo esta em <repo>/scripts/mastertool/.
if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

function Write-Section($text) {
    Write-Host ''
    Write-Host ('=' * 72)
    Write-Host $text
    Write-Host ('=' * 72)
}

Write-Section "Lote de repetibilidade -- estagio '$Stage', N = $Runs"

if ($Runs -lt 2) {
    Write-Host '[RECUSADO] repetibilidade exige ao menos duas execucoes.'
    exit 2
}

if (-not (Test-Path $Spec)) {
    Write-Host "[RECUSADO] spec nao encontrada: $Spec"
    exit 2
}

if ($Stage -eq 'plan') {
    # Saida preexistente RECUSA antes da primeira execucao. Reaproveitar saida
    # transformaria "N execucoes" em "uma execucao e N-1 leituras do mesmo
    # resultado" -- a mesma regra que `repeatability.execute_qualification`
    # aplica do lado do host.
    if (Test-Path $OutputRoot) {
        $ocupados = Get-ChildItem -Path $OutputRoot -Directory -Filter 'run-*' -ErrorAction SilentlyContinue
        if ($ocupados) {
            Write-Host "[RECUSADO] $OutputRoot ja contem diretorio(s) run-*."
            Write-Host '           Reaproveitar saida nao e repetir execucao.'
            exit 2
        }
    } else {
        if ($Execute) { New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null }
    }
} else {
    # No estagio `build` a saida TEM de existir: ele opera sobre o que o
    # estagio `plan` produziu. Exigir ausencia aqui seria a regra do estagio
    # errado.
    $existentes = @()
    if (Test-Path $OutputRoot) {
        $existentes = @(Get-ChildItem -Path $OutputRoot -Directory -Filter 'run-*' -ErrorAction SilentlyContinue)
    }
    if ($existentes.Count -lt $Runs) {
        Write-Host ("[RECUSADO] estagio 'build' precisa de $Runs diretorio(s) " +
                    "run-* ja produzidos pelo estagio 'plan'; encontrei " +
                    $existentes.Count + '.')
        exit 2
    }
}

$fabrica = Join-Path $PSScriptRoot 'run_project_factory.ps1'
if (-not (Test-Path $fabrica)) {
    Write-Host "[FALHOU] wrapper da fabrica nao encontrado: $fabrica"
    exit 1
}

$plano = @()
for ($i = 1; $i -le $Runs; $i++) {
    $runId = 'run-{0:d3}' -f $i
    $plano += [pscustomobject]@{
        RunId   = $runId
        WorkDir = (Join-Path $OutputRoot $runId)
    }
}

Write-Host "spec        : $Spec"
Write-Host "saida       : $OutputRoot"
Write-Host "execucoes   : $Runs"
Write-Host "fabrica     : $fabrica"
Write-Host ''
foreach ($vaga in $plano) { Write-Host ("  {0} -> {1}" -f $vaga.RunId, $vaga.WorkDir) }

if (-not $Execute) {
    Write-Host ''
    Write-Host '[SECO] nada foi executado. Repita com -Execute para rodar o lote.'
    exit 0
}

$resultados = @()
foreach ($vaga in $plano) {
    Write-Section ("Executando " + $vaga.RunId)
    New-Item -ItemType Directory -Path $vaga.WorkDir -Force | Out-Null

    $argumentos = @{
        Spec           = $Spec
        WorkRoot       = $vaga.WorkDir
        TimeoutSeconds = $TimeoutSeconds
        RepoRoot       = $RepoRoot
    }
    if ($Stage -eq 'plan') {
        $argumentos['ExecutePlan'] = $true
    } else {
        # O `-BuildPlan` NAO e o plano de autoria.
        #
        # ACHADO do piloto de 2026-08-02: passar `authoring-plan.json` aqui
        # reprovou as tres runs. O probe 40 espera um plano de BUILD -- outro
        # documento, com `operations: [{kind: build}]`, a fase propria e o
        # caminho do projeto de saida --, e o wrapper compara
        # `output_project.path` com o que a execucao produziu.
        #
        # Historicamente esses arquivos eram escritos A MAO, um por run
        # (`plano-build-034.json`, marcado "NAO versionar"). Num lote de N
        # execucoes isso seria N arquivos manuais, e cada um uma chance de
        # apontar para a run errada. Aqui ele e GERADO da propria run.
        $saidaDaRun = Join-Path $vaga.WorkDir 'saida\FABRICA.project'
        if (-not (Test-Path $saidaDaRun)) {
            Write-Host ("[FALHOU] " + $vaga.RunId + ": saida nao encontrada em " +
                        $saidaDaRun + '. O estagio `plan` rodou?')
            $resultados += [pscustomobject]@{ RunId = $vaga.RunId; ExitCode = 2 }
            continue
        }

        $artefatosDaRun = Join-Path $vaga.WorkDir 'artefatos'
        $planoDeBuild = Join-Path $artefatosDaRun 'build-plan.json'

        # `container.node_path` continua POSICIONAL aqui porque o probe 40
        # ainda resolve assim -- ele nao foi migrado na R0b, e o piloto e que
        # tornou isso visivel. Fica registrado como divida, e nao silenciado:
        # o valor vale para ESTE template, cujo `root/1/0/0` foi medido.
        $conteudoBuild = [ordered]@{
            schema_version = '1.0'
            operation_id   = $OperationId
            phase          = $BuildPhase
            run_id         = ($vaga.RunId + '-build')
            output_project = [ordered]@{ path = $saidaDaRun }
            artifacts_dir  = $artefatosDaRun
            container      = [ordered]@{
                node_path          = 'root/1/0/0'
                expected_name      = 'Application'
                expected_type_guid = '639b491f-5557-464c-af91-1471bac9f549'
            }
            mastertool     = [ordered]@{ version = '4.1.0.11'; script_engine = '4.2.0.0' }
            operations     = @([ordered]@{ kind = 'build' })
            notes          = 'Gerado por run_repeatability_batch.ps1. NAO versionar.'
        }
        [System.IO.File]::WriteAllText(
            $planoDeBuild,
            ($conteudoBuild | ConvertTo-Json -Depth 6),
            (New-Object System.Text.UTF8Encoding($false)))
        Write-Host ("[INFO] plano de build gerado: " + $planoDeBuild)

        $argumentos['ExecuteBuild'] = $true
        $argumentos['BuildPlan'] = $planoDeBuild
    }
    if ($Exe) { $argumentos['Exe'] = $Exe }
    if ($TemplateProject)       { $argumentos['TemplateProject'] = $TemplateProject }
    if ($TemplateQualification) { $argumentos['TemplateQualification'] = $TemplateQualification }
    if ($AutoCloseWindow)       { $argumentos['AutoCloseWindow'] = $true }

    $codigo = 0
    try {
        & $fabrica @argumentos
        $codigo = $LASTEXITCODE
    } catch {
        Write-Host ("[FALHOU] " + $vaga.RunId + ": " + $_.Exception.Message)
        $codigo = 1
    }

    # Continua mesmo com falha -- ver o cabecalho.
    $resultados += [pscustomobject]@{ RunId = $vaga.RunId; ExitCode = $codigo }
    if ($codigo -ne 0) {
        Write-Host ("[FALHOU] " + $vaga.RunId + " terminou com codigo " + $codigo + '. O lote continua.')
    }
}

Write-Section 'Resumo das execucoes'
foreach ($r in $resultados) {
    $rotulo = if ($r.ExitCode -eq 0) { 'ok     ' } else { 'FALHOU ' }
    Write-Host ("  {0} {1} (exit {2})" -f $rotulo, $r.RunId, $r.ExitCode)
}

if ($Stage -eq 'plan') {
    Write-Section 'Estagio `plan` encerrado'
    Write-Host 'NAO ha veredito ainda, e isso nao e omissao.'
    Write-Host ''
    Write-Host 'A VERIFICACAO (probe 47) roda dentro do -ExecuteBuild, entao um'
    Write-Host 'lote so de planos nao produz `verificacao/` -- o comparador nao'
    Write-Host 'teria o que comparar. Feche a fase de autoria, abra a fase de'
    Write-Host 'build, e rode o mesmo comando com -Stage build.'
    exit 0
}

Write-Section 'Veredito do LOTE (host, offline)'

$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

$relatorio = Join-Path $OutputRoot 'qualification-report.json'
$argsCli = @('-m', 'mastertool_bridge.cli', 'qualify-repeatability',
             '--runs-root', $OutputRoot, '--layout', 'factory',
             '--output', $relatorio)
if ($Minimum -gt 0) { $argsCli += @('--minimum', "$Minimum") }

$env:PYTHONPATH = (Join-Path $RepoRoot 'src')
& $python @argsCli
$vereditoCodigo = $LASTEXITCODE

Write-Host ''
Write-Host "relatorio: $relatorio"

# O codigo de saida do lote e o do VEREDITO, e nao o da ultima execucao: um
# lote em que todas as runs terminaram bem e cujo conjunto diverge continua
# sendo um lote reprovado.
exit $vereditoCodigo
