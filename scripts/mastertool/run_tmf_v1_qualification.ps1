<#
.SYNOPSIS
    Host supervisionado de qualificacao SOMENTE LEITURA do projeto-base
    candidato a template `TemplateExemplo v1.project` (precondicao de W1.4).

.DESCRIPTION
    FAIL-CLOSED. Dois modos MUTUAMENTE EXCLUSIVOS; o default nao abre nada:

        -ValidateOnly  (DEFAULT) so valida os parametros e os hashes. Nao
                       abre o MasterTool, nao copia nada.
        -Execute       copia o projeto-base para um diretorio SEM ESPACO,
                       abre o MasterTool sobre a COPIA e roda o probe 35
                       (somente leitura). Nenhuma escrita ocorre no projeto:
                       este script nunca chama create_*, replace, save,
                       save_as nem build.

    O caminho do projeto-base tem ESPACO ('Pasta Com Espacos'), e
    `--scriptargs` quebra o valor em espaco em branco (achado do probe 15,
    reconfirmado no MasterTool X). Por isso a copia de trabalho vai SEMPRE
    para um diretorio proprio sem espaco, nunca para o mesmo diretorio do
    arquivo de origem.

    FECHAMENTO DE JANELA: com -AutoCloseWindow, o host fecha a janela por
    CloseMainWindow() -- o equivalente a clicar no X -- depois que o
    artefato de conclusao aparece. NUNCA Stop-Process: matar processo
    poderia interromper a gravacao do artefato e viola docs/28 secao 7. Se a
    janela nao fechar, o host REPORTA e nao insiste.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso -- a conclusao vem SEMPRE do artefato
    qualify-completion.json gravado pelo probe 35.
#>
[CmdletBinding()]
param(
    [string]$BaseProject = 'C:\Exemplos\TemplateExemplo v1\TemplateExemplo v1.project',
    [string]$ExpectedBaseSha256 = '596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5',
    [long]$ExpectedBaseSizeBytes = 503040,

    [Parameter(Mandatory = $true)]
    [string]$WorkDir,

    [switch]$ValidateOnly,
    [switch]$Execute,

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
if ($ValidateOnly) { $selectedModes += 'ValidateOnly' }
if ($Execute)      { $selectedModes += 'Execute' }
if ($selectedModes.Count -gt 1) {
    Fail ("Modos mutuamente exclusivos: " + ($selectedModes -join ', '))
}
if ($selectedModes.Count -eq 0) {
    $Mode = 'ValidateOnly'
    Write-Host '[INFO] Nenhum modo informado: assumindo -ValidateOnly (default).'
}
else { $Mode = $selectedModes[0] }

$ProcessPattern = [IO.Path]::GetFileNameWithoutExtension($Exe) + '*'

Write-Section "Qualificacao read-only de TemplateExemplo v1 -- modo '$Mode'"

# =============================================================================
# BLOCO 1 -- VALIDACAO
# =============================================================================

if ([string]::IsNullOrWhiteSpace($BaseProject)) { Fail 'BaseProject vazio' }
if (-not [IO.Path]::IsPathRooted($BaseProject)) { Fail 'BaseProject deve ser absoluto' }
if (-not (Test-Path -LiteralPath $BaseProject)) { Fail "Projeto-base inexistente: $BaseProject" }

if ([string]::IsNullOrWhiteSpace($WorkDir)) { Fail 'WorkDir vazio' }
if (-not [IO.Path]::IsPathRooted($WorkDir)) { Fail 'WorkDir deve ser absoluto' }
if ($WorkDir -match '\s') {
    Fail ("WorkDir contem espaco: $WorkDir. O MasterTool quebra --scriptargs " +
          "em espaco em branco -- use um diretorio sem espaco.")
}
$repoFull = [IO.Path]::GetFullPath($RepoRoot)
if ([IO.Path]::GetFullPath($WorkDir).StartsWith($repoFull, [StringComparison]::OrdinalIgnoreCase)) {
    Fail "WorkDir dentro do repositorio: $WorkDir"
}

$baseInfo = Get-Item -LiteralPath $BaseProject
if ($baseInfo.Length -ne $ExpectedBaseSizeBytes) {
    Fail ("Tamanho do projeto-base diverge: observado $($baseInfo.Length), " +
          "esperado $ExpectedBaseSizeBytes")
}
$baseSha = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $BaseProject"
Write-Host "[OK] Tamanho base: $($baseInfo.Length) bytes"
Write-Host "[OK] SHA256 base : $baseSha"
if ($baseSha -ne $ExpectedBaseSha256.ToLower()) {
    Fail "SHA-256 do projeto-base diverge do valor medido e congelado"
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

$probe35 = Join-Path $RepoRoot 'scripts\mastertool\probes\35_qualify_template_readonly.py'
if (-not (Test-Path -LiteralPath $probe35)) { Fail "Probe 35 nao encontrado: $probe35" }
Write-Host "[OK] Probe 35    : $probe35"

if (Test-Path -LiteralPath $WorkDir) {
    $ocupado = @(Get-ChildItem -LiteralPath $WorkDir -File -ErrorAction SilentlyContinue)
    if ($ocupado.Count -gt 0) { Fail "WorkDir nao esta isolado/vazio: $WorkDir" }
}

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'Nada foi aberto, nenhuma copia criada.'
    exit 0
}

# =============================================================================
# BLOCO 2 -- EXECUCAO (somente -Execute), SOMENTE LEITURA
# =============================================================================

function Invoke-MasterTool {
    param(
        [Parameter(Mandatory=$true)][string]$ProjectPath,
        [Parameter(Mandatory=$true)][string]$ProbePath,
        [Parameter(Mandatory=$true)][string]$ScriptArgs,
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string]$CompletionPath
    )
    Write-Section "Lancando MasterTool -- $Label"
    $argList = @(
        ('--project="' + $ProjectPath + '"'),
        ('--runscript="' + $ProbePath + '"'),
        ('--scriptargs:"' + $ScriptArgs + '"')
    )
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
        # CloseMainWindow = o mesmo que clicar no X. NUNCA Stop-Process.
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

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$copyPath = Join-Path $WorkDir 'TemplateExemplo_v1_qualify.project'
$artifacts = Join-Path $WorkDir 'artifacts'
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

Copy-Item -LiteralPath $BaseProject -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

$completionPath = Join-Path $artifacts 'qualify-completion.json'
$obs = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe35 `
    -ScriptArgs ("--output=" + $artifacts) -Label 'qualificacao (somente leitura)' `
    -CompletionPath $completionPath

$completion = Read-Completion $completionPath
if ($null -eq $completion) {
    Fail 'qualify-completion.json ausente. Sem veredito -- trate como falha de artefato.'
}
Write-Host "[INFO] status do probe 35: $($completion.status)"

$copyShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfter -ne $copySha) { Fail 'A copia MUDOU durante a qualificacao read-only.' }
Write-Host '[OK] Copia intacta apos a execucao (somente leitura confirmada por hash).'

$baseShaAfter = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
if ($baseShaAfter -ne $baseSha) { Fail 'O PROJETO-BASE ORIGINAL foi tocado. Investigar imediatamente.' }
Write-Host '[OK] Projeto-base original intacto.'

if ($obs.orphan_ids.Count -gt 0) { Fail "Orfaos apos a execucao: $($obs.orphan_ids -join ', ')" }

# DOIS VEREDITOS SEPARADOS, e nao um.
#
# Na run-010 este bloco olhava so `status` e imprimiu "APROVADO" para um
# template com `authoring_eligible = false`. `status` responde "a varredura deu
# certo?"; elegibilidade responde "da para escrever neste template?". Colapsar
# as duas numa palavra so foi o que produziu a contradicao.
$scanVerdict = 'REPROVADO'
if ($completion.status -eq 'qualified' -or $completion.status -eq 'qualified_with_node_errors') {
    $scanVerdict = 'VARREDURA APROVADA'
}
elseif ($completion.status -eq 'name_conflict_detected') {
    $scanVerdict = 'VARREDURA APROVADA COM CONFLITO DE NOME'
}

# O campo e DERIVADO pelo probe; aqui ele so e lido. Ausente e tratado como
# NAO elegivel: artefato que nao responde a pergunta nao autoriza nada.
$eligible = $false
if ($null -ne $completion.authoring_eligible) { $eligible = [bool]$completion.authoring_eligible }
$blockers = @()
if ($completion.blocking_issues) { $blockers = @($completion.blocking_issues) }

$verdict = $scanVerdict
if ($scanVerdict -eq 'REPROVADO') { }
elseif ($eligible) { $verdict = 'APROVADO -- TEMPLATE ELEGIVEL PARA AUTORIA' }
else {
    $verdict = ('QUALIFICADO COM BLOQUEIOS -- NAO ELEGIVEL PARA AUTORIA (' +
                ($blockers -join ', ') + ')')
}

Write-Host "[INFO] qualification_status : $($completion.qualification_status)"
Write-Host "[INFO] authoring_eligible   : $eligible"
Write-Host "[INFO] blocking_issues      : $($blockers -join ', ')"

$sessionReport = [ordered]@{
    verdict = $verdict
    scan_verdict = $scanVerdict
    authoring_eligible = $eligible
    qualification_status = $completion.qualification_status
    blocking_issues = $blockers
    base_project = $BaseProject; base_sha256 = $baseSha; base_size_bytes = $baseInfo.Length
    working_copy = $copyPath; working_copy_sha256_before = $copySha
    working_copy_sha256_after = $copyShaAfter
    probe_status = $completion.status
    probe_exit_code = $completion.exit_code
    registry_candidate = $completion.registry_candidate
    name_conflicts = $completion.name_conflicts
    application = $completion.application
    libraries = $completion.libraries
    tasks = $completion.tasks
    compiler_version = $completion.compiler_version
    compiler_version_gap = $completion.compiler_version_gap
    execution = $obs
}
# `Out-File -Encoding utf8` grava BOM no PowerShell 5.1, e um leitor JSON
# estrito recusaria o proprio relatorio da sessao. UTF8Encoding($false) =
# UTF-8 sem BOM (mesma correcao aplicada aos wrappers de W1).
[System.IO.File]::WriteAllText(
    (Join-Path $artifacts 'session-verdict.json'),
    ($sessionReport | ConvertTo-Json -Depth 10),
    (New-Object System.Text.UTF8Encoding($false)))

Write-Section "VEREDITO DA QUALIFICACAO: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"

# Codigo de saida por CAMADA, para que "medi tudo mas nao posso escrever" nao
# se confunda com "a varredura falhou":
#   0 = varredura ok E template elegivel
#   4 = varredura ok, template NAO elegivel (bloqueios pendentes)
#   3 = varredura reprovada
if ($scanVerdict -eq 'REPROVADO') { exit 3 }
if (-not $eligible) {
    Write-Host '[BLOQUEIO] O template foi medido, mas NAO esta elegivel para autoria.' -ForegroundColor Yellow
    Write-Host '           W1.4 nao pode abrir sobre ele enquanto houver bloqueio.' -ForegroundColor Yellow
    exit 4
}
exit 0
