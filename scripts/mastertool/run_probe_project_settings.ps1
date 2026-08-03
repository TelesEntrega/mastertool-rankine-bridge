<#
.SYNOPSIS
    Host supervisionado do probe 36 -- leitura SOMENTE LEITURA da compiler
    version do projeto, pela cadeia literal
    `projects.primary.project_settings.get_compilerversion()`.

.DESCRIPTION
    FAIL-CLOSED. Dois modos MUTUAMENTE EXCLUSIVOS; o default NAO ABRE NADA:

        -ValidateOnly  (DEFAULT) so valida parametros, executavel, hashes e a
                       ausencia de mutador no probe. Nao abre o MasterTool,
                       nao copia nada.
        -Execute       copia o projeto-base para um diretorio SEM ESPACO, abre
                       o MasterTool sobre a COPIA e roda o probe 36 (somente
                       leitura). Nenhuma escrita ocorre: este script nunca
                       pede create_*, replace, save, save_as nem build.

    O caminho do projeto-base tem ESPACO, e `--scriptargs` quebra o valor em
    espaco em branco (achado do probe 15, reconfirmado no MasterTool X). Por
    isso a copia de trabalho vai SEMPRE para um diretorio proprio sem espaco.

    FECHAMENTO DE JANELA: com -AutoCloseWindow o host chama CloseMainWindow()
    -- o equivalente a clicar no X -- depois que o artefato de conclusao
    aparece. NUNCA Stop-Process: matar processo poderia interromper a gravacao
    do artefato e viola docs/28 secao 7. Se a janela nao fechar, o host
    REPORTA e nao insiste.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso -- a conclusao vem SEMPRE do artefato
    project-settings-completion.json gravado pelo probe 36.

    O veredito tem DUAS camadas separadas: "a sessao rodou" e "a compiler
    version foi MEDIDA". Uma sessao que roda inteira e nao mede nada nao e
    sucesso, e nao pode sair com 0.
#>
[CmdletBinding()]
param(
    [string]$BaseProject = 'C:\Pasta Com Espacos\TemplateExemplo v1\TemplateExemplo v1.project',
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

Write-Section "Leitura read-only da compiler version -- modo '$Mode'"

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
    Fail 'SHA-256 do projeto-base diverge do valor medido e congelado'
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

$probe36 = Join-Path $RepoRoot 'scripts\mastertool\probes\36_probe_project_settings_readonly.py'
if (-not (Test-Path -LiteralPath $probe36)) { Fail "Probe 36 nao encontrado: $probe36" }

# O probe le a compiler version. O mutador irmao vive no MESMO tipo do
# ScriptEngine e tem nome quase igual. Esta guarda le o FONTE antes de abrir o
# produto: se o nome do mutador aparecer, a sessao nem comeca.
$probeSource = Get-Content -LiteralPath $probe36 -Raw
if ($probeSource -match 'set_compilerversion') {
    Fail 'Probe 36 menciona o mutador de compiler version. Sessao recusada.'
}
foreach ($proibido in @('\.save\s*\(', '\.save_as\s*\(', '\.build\s*\(',
                        '\.rebuild\s*\(', '\.import_xml\s*\(', 'create_pou\s*\(',
                        'create_gvl\s*\(')) {
    if ($probeSource -match $proibido) {
        Fail "Probe 36 contem chamada proibida (padrao '$proibido'). Sessao recusada."
    }
}
Write-Host "[OK] Probe 36    : $probe36 (sem mutador no fonte)"

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
$copyPath = Join-Path $WorkDir 'TemplateExemplo_v1_settings.project'
$artifacts = Join-Path $WorkDir 'artifacts'
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

Copy-Item -LiteralPath $BaseProject -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

$completionPath = Join-Path $artifacts 'project-settings-completion.json'
$obs = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe36 `
    -ScriptArgs ("--output=" + $artifacts) -Label 'compiler version (somente leitura)' `
    -CompletionPath $completionPath

$completion = Read-Completion $completionPath
if ($null -eq $completion) {
    Fail 'project-settings-completion.json ausente. Sem veredito -- trate como falha de artefato.'
}
Write-Host "[INFO] status do probe 36: $($completion.status)"

$copyShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfter -ne $copySha) { Fail 'A copia MUDOU durante a leitura read-only.' }
Write-Host '[OK] Copia intacta apos a execucao (somente leitura confirmada por hash).'

$baseShaAfter = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
if ($baseShaAfter -ne $baseSha) { Fail 'O PROJETO-BASE ORIGINAL foi tocado. Investigar imediatamente.' }
Write-Host '[OK] Projeto-base original intacto.'

if ($obs.orphan_ids.Count -gt 0) { Fail "Orfaos apos a execucao: $($obs.orphan_ids -join ', ')" }

# DOIS VEREDITOS SEPARADOS.
#   sessionVerdict  -- a sessao rodou e gravou artefato?
#   measured        -- a compiler version foi de fato LIDA?
# Colapsar os dois numa palavra so foi o defeito corrigido na run-010 do
# wrapper de qualificacao; aqui ele ja nasce separado.
$measured = $false
if ($completion.status -eq 'measured' -and $completion.compiler_version_value) {
    $measured = $true
}
$sessionVerdict = 'SESSAO REPROVADA'
if ($completion.status -eq 'measured' -or $completion.status -eq 'unresolved') {
    $sessionVerdict = 'SESSAO CONCLUIDA'
}

$verdict = $sessionVerdict
if ($sessionVerdict -eq 'SESSAO REPROVADA') { }
elseif ($measured) {
    $verdict = ('COMPILER VERSION MEDIDA: ' + $completion.compiler_version_value)
}
else {
    $verdict = ('SESSAO CONCLUIDA SEM MEDIDA -- lacuna permanece (' +
                $completion.compiler_version.reason + ')')
}

Write-Host "[INFO] cadeia usada        : $($completion.accessor_chain)"
Write-Host "[INFO] compiler_version    : $($completion.compiler_version_value)"
Write-Host "[INFO] evidencia           : $($completion.compiler_version.status)"

$sessionReport = [ordered]@{
    verdict = $verdict
    session_verdict = $sessionVerdict
    compiler_version_measured = $measured
    compiler_version_value = $completion.compiler_version_value
    compiler_version = $completion.compiler_version
    accessor_chain = $completion.accessor_chain
    accessor_chain_source = $completion.accessor_chain_source
    chain_steps = $completion.chain_steps
    base_project = $BaseProject; base_sha256 = $baseSha; base_size_bytes = $baseInfo.Length
    working_copy = $copyPath; working_copy_sha256_before = $copySha
    working_copy_sha256_after = $copyShaAfter
    probe_status = $completion.status
    probe_exit_code = $completion.exit_code
    execution = $obs
}
# `Out-File -Encoding utf8` grava BOM no PowerShell 5.1, e um leitor JSON
# estrito recusaria o proprio relatorio da sessao. UTF8Encoding($false) =
# UTF-8 sem BOM (mesma correcao aplicada aos wrappers de W1 e ao wrapper de
# qualificacao).
[System.IO.File]::WriteAllText(
    (Join-Path $artifacts 'session-verdict.json'),
    ($sessionReport | ConvertTo-Json -Depth 10),
    (New-Object System.Text.UTF8Encoding($false)))

Write-Section "VEREDITO: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"

# Codigo de saida por CAMADA:
#   0 = sessao ok E compiler version medida
#   4 = sessao ok, compiler version NAO medida (lacuna permanece)
#   3 = sessao reprovada
if ($sessionVerdict -eq 'SESSAO REPROVADA') { exit 3 }
if (-not $measured) {
    Write-Host '[BLOQUEIO] A sessao rodou, mas a compiler version NAO foi lida.' -ForegroundColor Yellow
    Write-Host '           O bloqueador compiler_version_unresolved permanece.' -ForegroundColor Yellow
    exit 4
}
exit 0
