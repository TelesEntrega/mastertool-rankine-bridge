<#
.SYNOPSIS
    Host supervisionado de W1.3B -- editar o PROGRAM PRG_AI_TESTE (replace da
    declaracao, replace da implementacao) e persistir por save_as.

.DESCRIPTION
    FAIL-CLOSED. Tres modos MUTUAMENTE EXCLUSIVOS; o default nao muta nada:

        -ValidateOnly    (DEFAULT) so valida o plano. Nao abre o MasterTool
        -PreflightOnly   abre o MasterTool e roda o probe 33 em modo
                         preflight, somente leitura. Prova que o PROGRAM
                         existe, unico, com os DOIS textos iniciais exatos
        -ExecuteMutation validacao + preflight + probe 34 (mutacao) + probe
                         33 em modo postsave sobre o arquivo salvo

    O probe 34 e alcancavel APENAS pelo ramo -ExecuteMutation.

    FECHAMENTO DE JANELA: com -AutoCloseWindow, o host fecha a janela por
    CloseMainWindow() -- o equivalente a clicar no X -- depois que o artefato
    de conclusao aparece. NUNCA Stop-Process: matar processo violaria docs/28
    secao 7 e poderia interromper gravacao de artefato. Se a janela nao
    fechar (tipicamente porque ha um dialogo aberto), o host REPORTA e nao
    insiste.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso.
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
    [int]$ArtifactWaitSeconds = 240,
    [switch]$AutoCloseWindow,
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

$selectedModes = @()
if ($ValidateOnly)    { $selectedModes += 'ValidateOnly' }
if ($PreflightOnly)   { $selectedModes += 'PreflightOnly' }
if ($ExecuteMutation) { $selectedModes += 'ExecuteMutation' }
if ($selectedModes.Count -gt 1) {
    Fail ("Modos mutuamente exclusivos: " + ($selectedModes -join ', '))
}
if ($selectedModes.Count -eq 0) {
    $Mode = 'ValidateOnly'
    Write-Host '[INFO] Nenhum modo informado: assumindo -ValidateOnly (default).'
}
else { $Mode = $selectedModes[0] }

$ProcessPattern = [IO.Path]::GetFileNameWithoutExtension($Exe) + '*'

Write-Section "W1.3B -- editar PROGRAM PRG_AI_TESTE -- modo '$Mode'"

# =============================================================================
# BLOCO 1 -- VALIDACAO
# =============================================================================

if (-not (Test-Path -LiteralPath $Plan)) { Fail "Plano inexistente: $Plan" }
if (-not [IO.Path]::IsPathRooted($Plan)) { Fail "Plano deve ser absoluto: $Plan" }
if ($Plan -match '\s') { Fail "Plano em caminho com espaco: $Plan" }

$planText = Get-Content -LiteralPath $Plan -Raw
try { $planData = $planText | ConvertFrom-Json }
catch { Fail "Plano nao e JSON valido: $($_.Exception.Message)" }
$planSha = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Plano       : $Plan"
Write-Host "[OK] SHA256 plano: $planSha"

if ($planData.schema_version -ne '1.0') { Fail "schema_version inesperado" }
if ($planData.phase -ne 'W1_3B_EDIT_PROGRAM') { Fail "phase inesperada: $($planData.phase)" }
if ($planData.program_name -ne 'PRG_AI_TESTE') { Fail "program_name inesperado" }

$kinds = @($planData.operations | ForEach-Object { $_.kind })
if ($kinds.Count -ne 3 -or $kinds[0] -ne 'replace' -or $kinds[1] -ne 'replace' -or
    $kinds[2] -ne 'save_as') {
    Fail ("Plano deve declarar exatamente replace, replace, save_as -- recebido: " +
          ($kinds -join ', '))
}
$targets = @($planData.operations | Select-Object -First 2 | ForEach-Object { $_.target })
if ($targets[0] -ne 'textual_declaration' -or $targets[1] -ne 'textual_implementation') {
    Fail ("Os dois replace devem visar, na ordem, textual_declaration e " +
          "textual_implementation -- recebido: " + ($targets -join ', '))
}
Write-Host "[OK] Operacoes   : $($kinds -join ', ')"

$basePath   = $planData.input_project.base_path
$copyPath   = $planData.input_project.path
$outputPath = $planData.output_project.path
$artifacts  = $planData.artifacts_dir
$sessionDir = Split-Path -Parent $copyPath

foreach ($par in @(@{n='base_path';v=$basePath}, @{n='input path';v=$copyPath},
                   @{n='output path';v=$outputPath}, @{n='artifacts_dir';v=$artifacts})) {
    if ([string]::IsNullOrWhiteSpace($par.v)) { Fail "$($par.n) vazio" }
    if (-not [IO.Path]::IsPathRooted($par.v)) { Fail "$($par.n) deve ser absoluto" }
    if ($par.v -match '\s') { Fail "$($par.n) contem espaco: $($par.v)" }
}
if ([IO.Path]::GetFullPath($copyPath) -eq [IO.Path]::GetFullPath($outputPath)) {
    Fail 'entrada e saida sao o mesmo arquivo'
}
$repoFull = [IO.Path]::GetFullPath($RepoRoot)
foreach ($p in @($outputPath, $artifacts)) {
    if ([IO.Path]::GetFullPath($p).StartsWith($repoFull, [StringComparison]::OrdinalIgnoreCase)) {
        Fail "caminho dentro do repositorio: $p"
    }
}
if (Test-Path -LiteralPath $outputPath) { Fail "output ja existe: $outputPath" }
if (-not (Test-Path -LiteralPath $basePath)) { Fail "Projeto-base inexistente: $basePath" }

$baseSha = (Get-FileHash -LiteralPath $basePath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $basePath"
Write-Host "[OK] SHA256 base : $baseSha"
if ($planData.input_project.sha256 -ne $baseSha) {
    Fail "SHA-256 do projeto-base diverge do plano"
}

if (Test-Path -LiteralPath $sessionDir) {
    $ocupado = @(Get-ChildItem -LiteralPath $sessionDir -File -ErrorAction SilentlyContinue)
    if ($ocupado.Count -gt 0) { Fail "Diretorio da copia nao esta isolado/vazio: $sessionDir" }
}

if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel nao encontrado: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
if ($exeVersion -ne $ExpectedExeVersion) {
    Fail ("FileVersion inesperada: '$exeVersion'. Sem fallback para MT9000 4.0.0 " +
          "nem para MT8500.")
}
Write-Host "[OK] Executavel  : $Exe ($exeVersion)"

$running = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $AllowRunningInstance) {
    Fail ("Ha $($running.Count) instancia(s) aberta(s): " +
          (($running | ForEach-Object { $_.Id }) -join ', '))
}
Write-Host '[OK] Nenhuma instancia do MasterTool X aberta.'

$safetyFile = Join-Path $RepoRoot 'scripts\mastertool\common\safety.py'
if (-not (Select-String -LiteralPath $safetyFile -Pattern '^READ_ONLY_PHASE\s*=\s*True' -Quiet)) {
    Fail 'READ_ONLY_PHASE deixou de ser True'
}
Write-Host '[OK] READ_ONLY_PHASE = True'

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'Nada foi aberto, nenhuma copia criada.'
    exit 0
}

# =============================================================================
# BLOCO 2 -- PREFLIGHT (somente leitura)
# =============================================================================

$probe33 = Join-Path $RepoRoot 'scripts\mastertool\probes\33_verify_program_edit_w1_3b_readonly.py'
if (-not (Test-Path -LiteralPath $probe33)) { Fail "Probe 33 nao encontrado" }

function Invoke-MasterTool {
    param(
        [Parameter(Mandatory=$true)][string]$ProjectPath,
        [Parameter(Mandatory=$true)][string]$ProbePath,
        [Parameter(Mandatory=$true)][string]$ScriptArgs,
        [Parameter(Mandatory=$true)][string]$StageDir,
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string]$CompletionPath
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
    $proc = Start-Process -FilePath $Exe -ArgumentList $argList -PassThru
    Write-Host "[INFO] PID: $($proc.Id)"

    # Conclusao pelo ARTEFATO, nunca pelo exit code do launcher.
    $limite = (Get-Date).AddSeconds($ArtifactWaitSeconds)
    while (-not (Test-Path -LiteralPath $CompletionPath) -and (Get-Date) -lt $limite) {
        Start-Sleep -Seconds 3
        if ($proc.HasExited) { break }
    }
    $artefatoPresente = Test-Path -LiteralPath $CompletionPath
    Write-Host "[INFO] artefato de conclusao presente: $artefatoPresente"

    $fechadoPeloHost = $false
    if ($AutoCloseWindow -and -not $proc.HasExited) {
        # CloseMainWindow = o mesmo que clicar no X. NUNCA Stop-Process: matar
        # violaria docs/28 secao 7 e poderia interromper gravacao de artefato.
        Write-Host '[INFO] Fechando a janela (CloseMainWindow, equivalente ao X)...'
        try { $null = $proc.CloseMainWindow(); $fechadoPeloHost = $true } catch { }
    }

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
    Write-Host '[INFO] O exit code do launcher NAO decide nada.'
    if ($timedOut) {
        Write-Host '[TIMEOUT] A janela nao fechou. Provavelmente ha um dialogo aberto.' -ForegroundColor Yellow
        Write-Host '          Este host NAO mata processo. Verifique a tela.' -ForegroundColor Yellow
    }

    Start-Sleep -Seconds 2
    $orphans = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
    return [pscustomobject]@{
        started_at = $startedAt; elapsed_seconds = $elapsed; pid = $proc.Id
        timed_out = $timedOut; launcher_exit_code = $launcherExit
        artifact_present = $artefatoPresente; closed_by_host = $fechadoPeloHost
        orphan_ids = @($orphans | ForEach-Object { $_.Id })
        arguments = $argList
    }
}

function Read-Completion {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json) }
    catch { return $null }
}

New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
Copy-Item -LiteralPath $basePath -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

$preflightDir = Join-Path $artifacts 'preflight'
$preflightCompletion = Join-Path $preflightDir 'w1-3b-preflight-completion.json'
$obs1 = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe33 `
    -ScriptArgs ("--mode=preflight --plan=" + $Plan + " --output=" + $preflightDir) `
    -StageDir $preflightDir -Label 'preflight (somente leitura)' `
    -CompletionPath $preflightCompletion

$preflight = Read-Completion $preflightCompletion
if ($null -eq $preflight) { Fail 'w1-3b-preflight-completion.json ausente. Sem veredito.' }
Write-Host "[INFO] preflight status: $($preflight.status)"
if ($preflight.status -ne 'preflight_verified') {
    Fail "Preflight NAO passou: $($preflight.status). $($preflight.errors -join ' | ')"
}
$copyShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfter -ne $copySha) { Fail 'A copia MUDOU durante o preflight read-only.' }
if ($obs1.orphan_ids.Count -gt 0) { Fail "Orfaos apos preflight: $($obs1.orphan_ids -join ', ')" }

Write-Section 'PREFLIGHT APROVADO'
if ($Mode -eq 'PreflightOnly') {
    Write-Host 'PRG_AI_TESTE existe, unico, com os dois textos iniciais exatos.'
    Write-Host 'Nenhuma mutacao ocorreu.'
    exit 0
}

# =============================================================================
# BLOCO 3 -- MUTACAO (somente -ExecuteMutation)
# =============================================================================

$probe34 = Join-Path $RepoRoot 'scripts\mastertool\probes\34_edit_program_w1_3b.py'
if (-not (Test-Path -LiteralPath $probe34)) { Fail "Probe 34 nao encontrado" }

$planShaFrozen = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
if ($planShaFrozen -ne $planSha) { Fail 'O plano mudou durante a sessao.' }

$mutationDir = Join-Path $artifacts 'mutation'
$mutationCompletion = Join-Path $artifacts 'completion.json'
$obs2 = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe34 `
    -ScriptArgs ("--plan=" + $Plan) -StageDir $mutationDir -Label 'MUTACAO (probe 34)' `
    -CompletionPath $mutationCompletion

$completion = Read-Completion $mutationCompletion
if ($null -eq $completion) {
    Fail 'completion.json ausente. A copia esta em estado DESCONHECIDO: descarte-a.'
}
Write-Host "[INFO] status do probe 34: $($completion.status)"
if ($completion.status -ne 'saved_as') {
    Fail "Mutacao nao terminou em saved_as: $($completion.status). DESCARTE a copia."
}
$inputShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($inputShaAfter -ne $copySha) { Fail 'A copia de ENTRADA foi modificada. Descarte tudo.' }
if (-not (Test-Path -LiteralPath $outputPath)) { Fail 'save_as declarou sucesso sem criar o arquivo.' }
$outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Saida       : $outputPath"
Write-Host "[OK] SHA256 saida: $outputSha"
if ($obs2.orphan_ids.Count -gt 0) { Fail "Orfaos apos mutacao: $($obs2.orphan_ids -join ', ')" }

# =============================================================================
# BLOCO 4 -- POSTSAVE (segunda abertura, somente leitura)
# =============================================================================

$postsaveDir = Join-Path $artifacts 'postsave'
$postsaveCompletion = Join-Path $postsaveDir 'w1-3b-postsave-completion.json'
$baselineTree = Join-Path $preflightDir 'w1-3b-preflight-tree.json'
$obs3 = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe33 `
    -ScriptArgs ("--mode=postsave --plan=" + $Plan + " --output=" + $postsaveDir +
                 " --baseline=" + $baselineTree + " --output-sha256=" + $outputSha) `
    -StageDir $postsaveDir -Label 'postsave (arquivo salvo, somente leitura)' `
    -CompletionPath $postsaveCompletion

$postsave = Read-Completion $postsaveCompletion
if ($null -eq $postsave) { Fail 'w1-3b-postsave-completion.json ausente.' }
Write-Host "[INFO] postsave status: $($postsave.status)"
if ($obs3.orphan_ids.Count -gt 0) { Fail "Orfaos apos postsave: $($obs3.orphan_ids -join ', ')" }

$verdict = 'REPROVADO'
if ($postsave.status -eq 'postsave_verified') { $verdict = 'APROVADO' }
elseif ($postsave.status -eq 'text_read_gap') { $verdict = 'PENDENTE DE REVISAO HUMANA' }

$sessionReport = [ordered]@{
    verdict = $verdict; plan = $Plan; plan_sha256 = $planSha
    base_project = $basePath; base_sha256 = $baseSha
    working_copy = $copyPath; working_copy_sha256_before = $copySha
    working_copy_sha256_after = $inputShaAfter
    output_project = $outputPath; output_sha256 = $outputSha
    preflight_status = $preflight.status
    mutation_status = $completion.status
    postsave_status = $postsave.status
    edited_declaration_sha256 = $completion.edited_declaration_sha256
    edited_implementation_sha256 = $completion.edited_implementation_sha256
    opt_files = @(Get-ChildItem -LiteralPath $sessionDir -File -Filter '*.opt' -ErrorAction SilentlyContinue |
                  ForEach-Object { $_.Name })
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

Write-Section "VEREDITO DA SESSAO W1.3B: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"
if ($verdict -ne 'APROVADO') { exit 3 }
exit 0
