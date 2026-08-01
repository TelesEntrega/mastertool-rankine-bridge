<#
.SYNOPSIS
    Host supervisionado de W1.1 -- criar UMA GVL vazia e persistir por save_as.

.DESCRIPTION
    FAIL-CLOSED. Tres modos MUTUAMENTE EXCLUSIVOS, e o default nao muta nada:

        -ValidateOnly    (DEFAULT) so valida o plano. Nao abre o MasterTool,
                         nao cria copia, nao gera .opt
        -PreflightOnly   abre o MasterTool e roda o probe 28 em modo preflight,
                         somente leitura. Prova que o container expoe
                         create_gvl SEM invocar
        -ExecuteMutation roda validacao + preflight + probe 27 (mutacao) +
                         probe 28 em modo postsave sobre o arquivo salvo

    O probe 27 e alcancavel APENAS pelo ramo -ExecuteMutation. Em
    -ValidateOnly e -PreflightOnly ele nao e referenciado.

    Nunca usa --noUI. Nunca aceita fallback de executavel (4.0.0 ou MT8500).
    Nunca mata processo antes de preservar artefatos. Nunca trata exit code
    zero do launcher como sucesso: quem decide sao os arquivos de conclusao.

.PARAMETER Plan
    Caminho absoluto, sem espacos, do plano JSON real. Fora do repositorio.

.EXAMPLE
    .\run_w1_1_create_gvl.ps1 -Plan C:\mastertool-x-w0\w1\plan.json
    .\run_w1_1_create_gvl.ps1 -Plan C:\mastertool-x-w0\w1\plan.json -PreflightOnly
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [switch]$ValidateOnly,
    [switch]$PreflightOnly,
    [switch]$ExecuteMutation,

    [string]$Exe = 'C:\Program Files\Altus\MT9000 4.1.0\MT9000\Common\MT9000.exe',
    [string]$ExpectedExeVersion = '4.1.0.11',
    [string]$RepoRoot = 'C:\Pasta Com Espacos\mastertool-rankine-bridge',

    [int]$TimeoutSeconds = 600,
    [switch]$AllowRunningInstance
)

$ErrorActionPreference = 'Stop'

function Write-Section($text) {
    Write-Host ''
    Write-Host ('=' * 72)
    Write-Host $text
    Write-Host ('=' * 72)
}
function Fail($message) {
    Write-Host "[BLOQUEADO] $message" -ForegroundColor Red
    exit 2
}

# --- modo: exatamente um, e o default nao muta ------------------------------
$selectedModes = @()
if ($ValidateOnly)    { $selectedModes += 'ValidateOnly' }
if ($PreflightOnly)   { $selectedModes += 'PreflightOnly' }
if ($ExecuteMutation) { $selectedModes += 'ExecuteMutation' }
if ($selectedModes.Count -gt 1) {
    Fail ("Modos mutuamente exclusivos: " + ($selectedModes -join ', ') +
          ". Escolha um.")
}
if ($selectedModes.Count -eq 0) {
    # Default explicito, nunca implicito para execucao.
    $Mode = 'ValidateOnly'
    Write-Host '[INFO] Nenhum modo informado: assumindo -ValidateOnly (default).'
}
else { $Mode = $selectedModes[0] }

$ProcessPattern = [IO.Path]::GetFileNameWithoutExtension($Exe) + '*'   # MT9000*

Write-Section "W1.1 -- criar GVL -- modo '$Mode'"

# =============================================================================
# BLOCO 1 -- VALIDACAO. Roda em TODOS os modos, sem abrir o MasterTool.
# =============================================================================

if (-not (Test-Path -LiteralPath $Plan)) { Fail "Plano inexistente: $Plan" }
if (-not [IO.Path]::IsPathRooted($Plan)) { Fail "Plano deve ser caminho absoluto: $Plan" }
if ($Plan -match '\s') { Fail "Plano em caminho com espaco: $Plan" }

$planText = Get-Content -LiteralPath $Plan -Raw
try { $planData = $planText | ConvertFrom-Json }
catch { Fail "Plano nao e JSON valido: $($_.Exception.Message)" }

$planSha = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Plano       : $Plan"
Write-Host "[OK] SHA256 plano: $planSha"

# --- schema basico -----------------------------------------------------------
foreach ($campo in @('schema_version','operation_id','phase','gvl_name','run_id',
                     'input_project','output_project','artifacts_dir','container',
                     'mastertool','operations')) {
    if (-not $planData.PSObject.Properties.Name -contains $campo) {
        Fail "Plano sem campo obrigatorio: $campo"
    }
}
if ($planData.schema_version -ne '1.0') { Fail "schema_version inesperado: $($planData.schema_version)" }
if ($planData.phase -ne 'W1_1_CREATE_GVL') { Fail "phase inesperada: $($planData.phase)" }
if ($planData.gvl_name -ne 'GVL_AI_TESTE') { Fail "gvl_name inesperado: $($planData.gvl_name)" }

# --- operacoes: exatamente duas, na ordem ------------------------------------
$kinds = @($planData.operations | ForEach-Object { $_.kind })
if ($kinds.Count -ne 2 -or $kinds[0] -ne 'create_gvl' -or $kinds[1] -ne 'save_as') {
    Fail ("Plano deve declarar exatamente create_gvl, save_as -- recebido: " +
          ($kinds -join ', '))
}
Write-Host "[OK] Operacoes   : $($kinds -join ', ')"

# --- caminhos ----------------------------------------------------------------
$basePath   = $planData.input_project.base_path
$copyPath   = $planData.input_project.path
$outputPath = $planData.output_project.path
$artifacts  = $planData.artifacts_dir
$sessionDir = Split-Path -Parent $copyPath

foreach ($par in @(@{n='input_project.base_path';v=$basePath},
                   @{n='input_project.path';v=$copyPath},
                   @{n='output_project.path';v=$outputPath},
                   @{n='artifacts_dir';v=$artifacts})) {
    if ([string]::IsNullOrWhiteSpace($par.v)) { Fail "$($par.n) vazio" }
    if (-not [IO.Path]::IsPathRooted($par.v)) { Fail "$($par.n) deve ser absoluto: $($par.v)" }
    if ($par.v -match '\s') { Fail "$($par.n) contem espaco: $($par.v)" }
}
if ([IO.Path]::GetFullPath($copyPath) -eq [IO.Path]::GetFullPath($outputPath)) {
    Fail 'input_project.path e output_project.path sao o mesmo arquivo'
}
if ([IO.Path]::GetFullPath($basePath) -eq [IO.Path]::GetFullPath($copyPath)) {
    Fail 'a copia nao pode ser o proprio projeto-base'
}
$repoFull = [IO.Path]::GetFullPath($RepoRoot)
foreach ($par in @(@{n='output_project.path';v=$outputPath}, @{n='artifacts_dir';v=$artifacts})) {
    if ([IO.Path]::GetFullPath($par.v).StartsWith($repoFull, [StringComparison]::OrdinalIgnoreCase)) {
        Fail "$($par.n) aponta para dentro do repositorio"
    }
}
if (Test-Path -LiteralPath $outputPath) { Fail "output_project.path ja existe: $outputPath" }

# --- projeto-base -------------------------------------------------------------
if (-not (Test-Path -LiteralPath $basePath)) { Fail "Projeto-base inexistente: $basePath" }
$baseSha = (Get-FileHash -LiteralPath $basePath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $basePath"
Write-Host "[OK] SHA256 base : $baseSha"
if ($planData.input_project.sha256 -ne $baseSha) {
    Fail ("SHA-256 do projeto-base diverge do plano. Plano espera " +
          "$($planData.input_project.sha256), medido $baseSha")
}

# --- diretorio de sessao isolado ---------------------------------------------
if (Test-Path -LiteralPath $sessionDir) {
    $ocupado = @(Get-ChildItem -LiteralPath $sessionDir -File -ErrorAction SilentlyContinue)
    if ($ocupado.Count -gt 0) {
        Fail ("Diretorio da copia nao esta isolado/vazio: $sessionDir. " +
              "Abrir um projeto cria .opt irmaos, e eles precisam ficar contidos.")
    }
}

# --- instalacao exata ---------------------------------------------------------
if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel nao encontrado: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
if ($exeVersion -ne $ExpectedExeVersion) {
    Fail ("FileVersion inesperada: '$exeVersion' (esperada '$ExpectedExeVersion'). " +
          "Sem fallback para MT9000 4.0.0 nem para MT8500.")
}
if ($planData.mastertool.version -ne $ExpectedExeVersion) {
    Fail "mastertool.version do plano ($($planData.mastertool.version)) difere de $ExpectedExeVersion"
}
Write-Host "[OK] Executavel  : $Exe ($exeVersion)"

# --- nenhuma instancia aberta --------------------------------------------------
$running = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $AllowRunningInstance) {
    Fail ("Ha $($running.Count) instancia(s) do MasterTool X aberta(s): " +
          (($running | ForEach-Object { $_.Id }) -join ', '))
}
Write-Host '[OK] Nenhuma instancia do MasterTool X aberta.'

# --- gate de escrita ainda coerente --------------------------------------------
$safetyFile = Join-Path $RepoRoot 'scripts\mastertool\common\safety.py'
if (-not (Select-String -LiteralPath $safetyFile -Pattern '^READ_ONLY_PHASE\s*=\s*True' -Quiet)) {
    Fail 'READ_ONLY_PHASE deixou de ser True'
}
if (-not (Select-String -LiteralPath $safetyFile -Pattern 'CONTROLLED_WRITE_PHASE\s*=\s*"W1_1_CREATE_GVL"' -Quiet)) {
    Fail 'CONTROLLED_WRITE_PHASE nao e W1_1_CREATE_GVL'
}
Write-Host '[OK] Gate: READ_ONLY_PHASE=True, fase W1_1_CREATE_GVL'

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'Nada foi aberto, nenhuma copia criada, nenhum artefato gerado.'
    Write-Host 'Proximo passo: repetir com -PreflightOnly.'
    exit 0
}

# =============================================================================
# BLOCO 2 -- PREFLIGHT. Abre o MasterTool, SOMENTE LEITURA.
# =============================================================================

$probe28 = Join-Path $RepoRoot 'scripts\mastertool\probes\28_verify_gvl_w1_1_readonly.py'
if (-not (Test-Path -LiteralPath $probe28)) { Fail "Probe 28 nao encontrado: $probe28" }

function Invoke-MasterTool {
    param(
        [Parameter(Mandatory=$true)][string]$ProjectPath,
        [Parameter(Mandatory=$true)][string]$ProbePath,
        [Parameter(Mandatory=$true)][string]$ScriptArgs,
        [Parameter(Mandatory=$true)][string]$StageDir,
        [Parameter(Mandatory=$true)][string]$Label
    )
    New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
    $argList = @(
        ('--project="' + $ProjectPath + '"'),
        ('--runscript="' + $ProbePath + '"'),
        ('--scriptargs:"' + $ScriptArgs + '"')
    )
    Write-Section "Lancando MasterTool -- $Label"
    Write-Host ($argList -join ' ')
    Write-Host '[LEMBRETE] UI VISIVEL. Diante de qualquer dialogo: CANCELE e registre.' -ForegroundColor Yellow

    $startedAt = Get-Date
    $stdout = Join-Path $StageDir 'stdout.txt'
    $stderr = Join-Path $StageDir 'stderr.txt'
    $proc = Start-Process -FilePath $Exe -ArgumentList $argList -PassThru `
                          -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-Host "[INFO] PID: $($proc.Id)"

    # PERGUNTAR AO PROCESSO, e nao a excecao. `Wait-Process -Id` LANCA quando
    # o processo ja encerrou e foi reciclado -- e o `catch` chamava isso de
    # timeout, relatando o MELHOR desfecho (a janela fechou sozinha) como o
    # PIOR ("provavelmente ha um dialogo aberto"). Um aviso que dispara no
    # caso limpo ensina o leitor a ignorar o aviso.
    try { Wait-Process -Id $proc.Id -Timeout $TimeoutSeconds -ErrorAction Stop } catch { }
    try { $proc.Refresh() } catch { }
    $timedOut = -not $proc.HasExited
    $elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)

    $launcherExit = $null
    if (-not $timedOut) { try { $launcherExit = $proc.ExitCode } catch { $launcherExit = $null } }
    Write-Host "[INFO] duracao: $elapsed s; exit do launcher: $launcherExit"
    Write-Host '[INFO] O exit code do launcher NAO decide nada: o veredito vem do artefato.'

    Start-Sleep -Seconds 2
    $orphans = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
    return [pscustomobject]@{
        started_at = $startedAt; elapsed_seconds = $elapsed; pid = $proc.Id
        timed_out = $timedOut; launcher_exit_code = $launcherExit
        orphan_ids = @($orphans | ForEach-Object { $_.Id })
        stdout_path = $stdout; stderr_path = $stderr
        arguments = $argList
    }
}

function Read-Completion {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json) }
    catch { return $null }
}

# --- copia descartavel --------------------------------------------------------
New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
Copy-Item -LiteralPath $basePath -Destination $copyPath
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base. Abortado.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

$preflightDir = Join-Path $artifacts 'preflight'
$obs1 = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe28 `
    -ScriptArgs ("--mode=preflight --plan=" + $Plan + " --output=" + $preflightDir) `
    -StageDir $preflightDir -Label 'preflight (somente leitura)'

$preflight = Read-Completion (Join-Path $preflightDir 'preflight-completion.json')
if ($null -eq $preflight) {
    Fail ("preflight-completion.json ausente ou ilegivel. Sem artefato de " +
          "conclusao nao ha veredito -- e o exit code do launcher nao substitui.")
}
Write-Host "[INFO] preflight status: $($preflight.status)"
if ($preflight.status -ne 'preflight_passed') {
    Fail ("Preflight NAO passou: $($preflight.status). " +
          ($preflight.errors -join ' | '))
}
if (-not $preflight.create_gvl_member_present -or -not $preflight.create_gvl_member_callable) {
    Fail 'Preflight passou mas o membro create_gvl nao esta utilizavel. Abortado.'
}
$copyShaAfterPreflight = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfterPreflight -ne $copySha) {
    Fail 'A copia MUDOU durante o preflight somente-leitura. Abortado.'
}
$optFiles = @(Get-ChildItem -LiteralPath $sessionDir -File -Filter '*.opt' -ErrorAction SilentlyContinue |
              ForEach-Object { $_.Name })
Write-Host "[OK] .opt confinados no diretorio da sessao: $($optFiles -join ', ')"
if ($obs1.orphan_ids.Count -gt 0) { Fail "Processos orfaos apos o preflight: $($obs1.orphan_ids -join ', ')" }

Write-Section 'PREFLIGHT APROVADO'
if ($Mode -eq 'PreflightOnly') {
    Write-Host 'O container expoe create_gvl e o nome alvo esta livre.'
    Write-Host 'Nenhuma mutacao ocorreu. A copia pode ser descartada.'
    exit 0
}

# =============================================================================
# BLOCO 3 -- MUTACAO. Alcancavel SOMENTE por -ExecuteMutation.
# =============================================================================

$probe27 = Join-Path $RepoRoot 'scripts\mastertool\probes\27_create_gvl_w1_1.py'
if (-not (Test-Path -LiteralPath $probe27)) { Fail "Probe 27 nao encontrado: $probe27" }

$planShaFrozen = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
if ($planShaFrozen -ne $planSha) { Fail 'O plano mudou durante a sessao. Abortado.' }

$mutationDir = Join-Path $artifacts 'mutation'
$obs2 = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe27 `
    -ScriptArgs ("--plan=" + $Plan) -StageDir $mutationDir -Label 'MUTACAO (probe 27)'

$completion = Read-Completion (Join-Path $artifacts 'completion.json')
if ($null -eq $completion) {
    $completion = Read-Completion (Join-Path $mutationDir 'completion.json')
}
if ($null -eq $completion) {
    Fail ("completion.json ausente. A copia esta em estado DESCONHECIDO e deve " +
          "ser descartada; nao ha rollback transacional.")
}
Write-Host "[INFO] status do probe 27: $($completion.status)"
if ($completion.status -ne 'saved_as') {
    Fail ("Mutacao nao terminou em saved_as: $($completion.status). " +
          "DESCARTE a copia inteira: $copyPath")
}
$inputShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($inputShaAfter -ne $copySha) {
    Fail "A copia de ENTRADA foi modificada (save no lugar de save_as?). Descarte tudo."
}
if (-not (Test-Path -LiteralPath $outputPath)) { Fail 'save_as declarou sucesso e o arquivo de saida nao existe.' }
$outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Saida       : $outputPath"
Write-Host "[OK] SHA256 saida: $outputSha"
if ($obs2.orphan_ids.Count -gt 0) { Fail "Processos orfaos apos a mutacao: $($obs2.orphan_ids -join ', ')" }

# =============================================================================
# BLOCO 4 -- POSTSAVE. Segunda abertura, somente leitura, sobre o SALVO.
# =============================================================================

$postsaveDir = Join-Path $artifacts 'postsave'
$baselineTree = Join-Path $preflightDir 'preflight-tree.json'
$obs3 = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe28 `
    -ScriptArgs ("--mode=postsave --plan=" + $Plan + " --output=" + $postsaveDir +
                 " --baseline=" + $baselineTree + " --output-sha256=" + $outputSha) `
    -StageDir $postsaveDir -Label 'postsave (somente leitura, arquivo salvo)'

$postsave = Read-Completion (Join-Path $postsaveDir 'postsave-completion.json')
if ($null -eq $postsave) { Fail 'postsave-completion.json ausente. Veredito indefinido.' }
Write-Host "[INFO] postsave status: $($postsave.status)"
if ($obs3.orphan_ids.Count -gt 0) { Fail "Processos orfaos apos o postsave: $($obs3.orphan_ids -join ', ')" }

$verdict = 'REPROVADO'
if ($postsave.status -eq 'postsave_verified') { $verdict = 'APROVADO' }
elseif ($postsave.status -eq 'text_read_gap') { $verdict = 'PENDENTE DE REVISAO HUMANA' }

$sessionReport = [ordered]@{
    verdict = $verdict
    plan = $Plan; plan_sha256 = $planSha
    base_project = $basePath; base_sha256 = $baseSha
    working_copy = $copyPath; working_copy_sha256_before = $copySha
    working_copy_sha256_after = $inputShaAfter
    output_project = $outputPath; output_sha256 = $outputSha
    preflight_status = $preflight.status
    mutation_status = $completion.status
    postsave_status = $postsave.status
    structural_diff = $postsave.structural_diff
    opt_files = $optFiles
    executions = @($obs1, $obs2, $obs3)
}
# `Out-File -Encoding utf8` grava BOM no PowerShell 5.1, e um leitor JSON
# estrito recusa o proprio relatorio da sessao com "Unexpected UTF-8 BOM".
# Achado na execucao real de W1.3A (run-008), lendo o veredito de volta.
# UTF8Encoding($false) = UTF-8 sem BOM.
[System.IO.File]::WriteAllText(
    (Join-Path $artifacts 'session-verdict.json'),
    ($sessionReport | ConvertTo-Json -Depth 8),
    (New-Object System.Text.UTF8Encoding($false)))

Write-Section "VEREDITO DA SESSAO: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"
Write-Host '[LEMBRETE] Anote o que VOCE VIU na tela. Nenhum script captura isso.'
if ($verdict -ne 'APROVADO') { exit 3 }
exit 0
