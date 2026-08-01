<#
.SYNOPSIS
    Host supervisionado de W1.4 -- autoria INTEGRADA (create_gvl,
    create_program, tres replace, save_as) e, em ETAPA PROPRIA, o build do
    arquivo salvo.

.DESCRIPTION
    FAIL-CLOSED. Quatro modos MUTUAMENTE EXCLUSIVOS; o default nao muta nada:

        -ValidateOnly    (DEFAULT) so valida o plano. Nao abre o MasterTool
        -PreflightOnly   abre o MasterTool e roda o probe 37 em modo
                         preflight, somente leitura, sobre a copia de
                         trabalho. Prova que o container resolve, que os
                         nomes-alvo NAO existem e congela a varredura
                         recursiva como linha de base
        -ExecuteMutation validacao + preflight + probe 38 (as seis mutacoes).
                         TERMINA AQUI: nao compila
        -ExecuteBuild    ETAPA PROPRIA, sobre a saida ja produzida: probe 40
                         (build, abertura separada) e depois probe 37 em modo
                         postsave. Nao cria copia, nao autora nada

    O probe 38 e alcancavel APENAS pelo ramo -ExecuteMutation; o probe 40,
    APENAS pelo ramo -ExecuteBuild. O build ser etapa propria e o que separa
    "o texto persistiu" de "o texto compila": sao provas de naturezas
    diferentes, e uma decisao humana cabe entre elas.

    AVISO NAO E ERRO. O veredito do build e "sem erro"; avisos entram na
    integra no artefato e nao reprovam.

    FECHAMENTO DE JANELA: com -AutoCloseWindow, o host fecha a janela por
    CloseMainWindow() -- o equivalente a clicar no X -- depois que o artefato
    de conclusao aparece. NUNCA Stop-Process: matar processo violaria docs/28
    secao 7 e poderia interromper gravacao de artefato. Se a janela nao
    fechar (tipicamente porque ha um dialogo aberto), o host REPORTA e nao
    insiste.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso: quem conclui e o ARTEFATO.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [switch]$ValidateOnly,
    [switch]$PreflightOnly,
    [switch]$ExecuteMutation,
    [switch]$ExecuteBuild,

    # Artefato de qualificacao read-only do template (probe 35, docs/36).
    # OBRIGATORIO nos modos que abrem o MasterTool sobre o template: a
    # elegibilidade para autoria e CONSULTADA, nunca presumida.
    [string]$TemplateQualification,

    [string]$Exe = 'C:\Program Files\Altus\MT9000 4.1.0\MT9000\Common\MT9000.exe',
    [string]$ExpectedExeVersion = '4.1.0.11',
    [string]$RepoRoot = 'C:\Pasta Com Espacos\mastertool-rankine-bridge',

    [int]$TimeoutSeconds = 900,
    [int]$ArtifactWaitSeconds = 600,
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
function Write-JsonNoBom($path, $data) {
    # `Out-File -Encoding utf8` grava BOM no PowerShell 5.1, e um leitor JSON
    # estrito recusa o proprio relatorio da sessao com "Unexpected UTF-8 BOM".
    # Achado na execucao real de W1.3A (run-008). UTF8Encoding($false) = sem BOM.
    [System.IO.File]::WriteAllText(
        $path, ($data | ConvertTo-Json -Depth 10),
        (New-Object System.Text.UTF8Encoding($false)))
}

$selectedModes = @()
if ($ValidateOnly)    { $selectedModes += 'ValidateOnly' }
if ($PreflightOnly)   { $selectedModes += 'PreflightOnly' }
if ($ExecuteMutation) { $selectedModes += 'ExecuteMutation' }
if ($ExecuteBuild)    { $selectedModes += 'ExecuteBuild' }
if ($selectedModes.Count -gt 1) {
    Fail ("Modos mutuamente exclusivos: " + ($selectedModes -join ', '))
}
if ($selectedModes.Count -eq 0) {
    $Mode = 'ValidateOnly'
    Write-Host '[INFO] Nenhum modo informado: assumindo -ValidateOnly (default).'
}
else { $Mode = $selectedModes[0] }

$ProcessPattern = [IO.Path]::GetFileNameWithoutExtension($Exe) + '*'

Write-Section "W1.4 -- autoria integrada e build -- modo '$Mode'"

# =============================================================================
# BLOCO 1 -- VALIDACAO (todos os modos)
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
if ($planData.phase -ne 'W1_4_INTEGRATED_BUILD') { Fail "phase inesperada: $($planData.phase)" }
if ($planData.operation_id -ne 'w1-4-integrated-build') { Fail "operation_id inesperado" }
if ($planData.gvl_name -ne 'GVL_AI_TESTE') { Fail "gvl_name inesperado" }
if ($planData.program_name -ne 'PRG_AI_TESTE') { Fail "program_name inesperado" }
if ($planData.st_language_guid -ne 'cc393387-a21c-4f68-a3e3-84c36951965d') {
    Fail "st_language_guid inesperado: o GUID de ST e medido, e a string 'ST' nao o substitui"
}

$kinds = @($planData.operations | ForEach-Object { $_.kind })
if ($kinds.Count -ne 7 -or $kinds[0] -ne 'create_gvl' -or $kinds[1] -ne 'create_program' -or
    $kinds[2] -ne 'replace' -or $kinds[3] -ne 'replace' -or $kinds[4] -ne 'replace' -or
    $kinds[5] -ne 'save_as' -or $kinds[6] -ne 'build') {
    Fail ("Plano deve declarar exatamente create_gvl, create_program, replace, " +
          "replace, replace, save_as, build -- recebido: " + ($kinds -join ', '))
}
$targets = @($planData.operations[2..4] | ForEach-Object { $_.target })
if ($targets[0] -ne 'gvl_textual_declaration' -or
    $targets[1] -ne 'program_textual_declaration' -or
    $targets[2] -ne 'program_textual_implementation') {
    Fail ("Os tres replace devem visar, na ordem, gvl_textual_declaration, " +
          "program_textual_declaration e program_textual_implementation -- recebido: " +
          ($targets -join ', '))
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
if (-not (Test-Path -LiteralPath $basePath)) { Fail "Projeto-base inexistente: $basePath" }
$baseSha = (Get-FileHash -LiteralPath $basePath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $basePath"
Write-Host "[OK] SHA256 base : $baseSha"
if ($planData.input_project.sha256 -ne $baseSha) {
    Fail "SHA-256 do projeto-base diverge do plano"
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

$probe37 = Join-Path $RepoRoot 'scripts\mastertool\probes\37_preflight_w1_4_readonly.py'
if (-not (Test-Path -LiteralPath $probe37)) { Fail "Probe 37 nao encontrado" }
$preflightDir = Join-Path $artifacts 'preflight'
$preflightCompletion = Join-Path $preflightDir 'w1-4-preflight-completion.json'
$baselineTree = Join-Path $preflightDir 'w1-4-preflight-flat-nodes.json'

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
    Write-Host '[LEMBRETE] UI VISIVEL. Diante de qualquer dialogo: CANCELE e registre o texto exato.' -ForegroundColor Yellow
    Write-Host '[LEMBRETE] Dialogo de biblioteca ausente ou indicio de download: ABORTE a sessao.' -ForegroundColor Yellow

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
        # CloseMainWindow = o mesmo que clicar no X. NUNCA matar processo:
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

# -----------------------------------------------------------------------------
# ELEGIBILIDADE DO TEMPLATE -- consultada, nunca presumida.
#
# docs/36: o TemplateExemplo v1.project esta MEDIDO e NAO ELEGIVEL para autoria, com dois
# bloqueadores (compiler_version_unresolved e libraries_unresolved). Template
# qualificado ESTRUTURALMENTE nao e template ELEGIVEL PARA AUTORIA, e um host
# que abrisse o MasterTool sem olhar essa distincao estaria presumindo o que
# outra sessao mediu e negou.
#
# Este bloco nao decide elegibilidade: ele LE o artefato de qualificacao e
# recusa quando o artefato nao diz `authoring_eligible: true`. Artefato
# ausente, ilegivel ou sem o campo tambem recusa -- fail-closed.
# -----------------------------------------------------------------------------
if ($Mode -ne 'ValidateOnly') {
    if ([string]::IsNullOrWhiteSpace($TemplateQualification)) {
        Fail ("-TemplateQualification e obrigatorio fora de -ValidateOnly: a " +
              "elegibilidade do template e consultada no artefato do probe 35 " +
              "(docs/36), nunca presumida por este host.")
    }
    if (-not (Test-Path -LiteralPath $TemplateQualification)) {
        Fail "Artefato de qualificacao inexistente: $TemplateQualification"
    }
    try { $qualification = Get-Content -LiteralPath $TemplateQualification -Raw | ConvertFrom-Json }
    catch { Fail "Artefato de qualificacao nao e JSON valido: $($_.Exception.Message)" }
    if ($null -eq $qualification.PSObject.Properties['authoring_eligible']) {
        Fail ("Artefato de qualificacao sem o campo authoring_eligible. " +
              "Campo ausente nao e 'elegivel': e ausencia de resposta.")
    }
    if ($qualification.authoring_eligible -ne $true) {
        Fail ("Template NAO elegivel para autoria. Bloqueadores: " +
              ($qualification.blocking_issues -join ', ') +
              ". Resolver os acessores vem antes de W1.4 (docs/36 secao 6).")
    }
    Write-Host "[OK] Template    : elegivel para autoria (artefato: $TemplateQualification)"
}

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'Nada foi aberto, nenhuma copia criada, nada compilado.'
    Write-Host 'A elegibilidade do template NAO foi consultada neste modo, e este'
    Write-Host 'host nunca a presume: ela e exigida em -TemplateQualification nos'
    Write-Host 'modos que abrem o MasterTool (docs/36).'
    exit 0
}

# =============================================================================
# BLOCO 2 -- BUILD, ETAPA PROPRIA (somente -ExecuteBuild)
#
# Nao cria copia e nao autora nada: opera sobre a saida JA produzida por uma
# sessao de -ExecuteMutation anterior, em abertura separada. Termina com exit,
# e por isso nenhum bloco abaixo e alcancavel neste modo.
# =============================================================================

if ($Mode -eq 'ExecuteBuild') {
    $probe40 = Join-Path $RepoRoot 'scripts\mastertool\probes\40_build_w1_4.py'
    if (-not (Test-Path -LiteralPath $probe40)) { Fail "Probe 40 nao encontrado" }

    # =========================================================================
    # AVISO ANTES DO LANCAMENTO. O BUILD SEMPRE DISPARA O DIALOGO DE SALVAR.
    #
    # Compilar altera o projeto em memoria -- cache de pre-compilacao, estado
    # de mensagens --, entao `CloseMainWindow()` SEMPRE cai no dialogo "O
    # projeto atual foi alterado. Deseja salvar as alteracoes?", e a janela
    # nao fecha sozinha. Isso e certeza, nao possibilidade.
    #
    # A licao veio de W1.5 e eu nao a tinha replicado aqui: aviso que chega
    # junto com o evento nao e aviso. Agora ele para o fluxo e aparece sozinho.
    # =========================================================================
    Write-Section 'ATENCAO -- LEIA ANTES DE A JANELA ABRIR'
    Write-Host ''
    Write-Host '  O BUILD SEMPRE deixa o projeto "alterado" em memoria.' -ForegroundColor Yellow
    Write-Host '  A janela NAO vai fechar sozinha: vai parar no dialogo' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '      "O projeto atual foi alterado. Deseja salvar as alteracoes?"' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  CLIQUE "NAO".' -ForegroundColor Red
    Write-Host ''
    Write-Host '  NAO       descarta o estado de memoria. O .project salvo pela'
    Write-Host '            autoria continua intacto, e o probe confere isso por'
    Write-Host '            hash antes e depois.'
    Write-Host '  SIM       gravaria o resultado do build por cima da saida, e a'
    Write-Host '            sessao seria reprovada por divergencia de hash.'
    Write-Host '  CANCELAR  trava a janela ate o timeout.'
    Write-Host ''
    Write-Host '  Diante de QUALQUER OUTRO dialogo: CANCELE e registre o texto.'
    Write-Host '  Dialogo de biblioteca ausente ou indicio de download: ABORTE.'
    Write-Host ''
    if (-not (Test-Path -LiteralPath $outputPath)) {
        Fail "Saida inexistente: $outputPath. O build e etapa propria sobre a saida de -ExecuteMutation."
    }
    if (-not (Test-Path -LiteralPath $baselineTree)) {
        Fail "Baseline recursiva do preflight ausente: $baselineTree. Sem ela nao existe diff estrutural."
    }

    $mutationVerdictPath = Join-Path $artifacts 'session-verdict.json'
    $mutationVerdict = Read-Completion $mutationVerdictPath
    if ($null -eq $mutationVerdict) {
        Fail 'session-verdict.json da etapa de mutacao ausente ou ilegivel. Sem ele o hash da saida nao esta ancorado.'
    }
    $outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
    if ($mutationVerdict.output_sha256 -ne $outputSha) {
        Fail "A saida MUDOU desde a mutacao ($($mutationVerdict.output_sha256) -> $outputSha). Descarte-a."
    }
    Write-Host "[OK] Saida       : $outputPath"
    Write-Host "[OK] SHA256 saida: $outputSha (identico ao registrado na mutacao)"

    $buildDir = Join-Path $artifacts 'build'
    $buildCompletion = Join-Path $buildDir 'build-completion.json'
    $obsBuild = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe40 `
        -ScriptArgs ("--plan=" + $Plan + " --output=" + $buildDir +
                     " --output-sha256=" + $outputSha) `
        -StageDir $buildDir -Label 'BUILD (probe 40, abertura separada)' `
        -CompletionPath $buildCompletion

    $build = Read-Completion $buildCompletion
    if ($null -eq $build) {
        Fail 'build-completion.json ausente. Sem veredito de compilacao.'
    }
    Write-Host "[INFO] status do build: $($build.status)"
    # DUAS contagens, e nao uma. O probe escreve no MESMO message store que
    # depois le -- o banner dele entra na conta --, entao "8 mensagens" nunca
    # foram 8 mensagens do compilador. Mostrar so o total esconderia o
    # desconto; mostrar so o descontado esconderia que houve desconto.
    Write-Host ("[INFO] mensagens do build: $($build.message_count_from_build) " +
                "(total no armazem: $($build.message_count_total); " +
                "pre-existentes: $($build.messages_baseline_count)). " +
                'Integra em build-messages.json')
    $outputShaAfterBuild = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
    if ($outputShaAfterBuild -ne $outputSha) {
        Fail 'O arquivo de saida MUDOU durante o build. Nenhum save foi pedido.'
    }
    if ($obsBuild.orphan_ids.Count -gt 0) { Fail "Orfaos apos build: $($obsBuild.orphan_ids -join ', ')" }
    if ($build.status -ne 'build_verified') {
        Fail "Build NAO aprovado: $($build.status). $($build.errors -join ' | ')"
    }

    # ---- postsave: terceira abertura, somente leitura, DEPOIS do build -------
    $postsaveDir = Join-Path $artifacts 'postsave'
    $postsaveCompletion = Join-Path $postsaveDir 'w1-4-postsave-completion.json'
    $obsPost = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe37 `
        -ScriptArgs ("--mode=postsave --plan=" + $Plan + " --output=" + $postsaveDir +
                     " --baseline=" + $baselineTree + " --output-sha256=" + $outputSha) `
        -StageDir $postsaveDir -Label 'postsave (somente leitura, apos o build)' `
        -CompletionPath $postsaveCompletion

    $postsave = Read-Completion $postsaveCompletion
    if ($null -eq $postsave) { Fail 'w1-4-postsave-completion.json ausente.' }
    Write-Host "[INFO] postsave status: $($postsave.status)"
    if ($obsPost.orphan_ids.Count -gt 0) { Fail "Orfaos apos postsave: $($obsPost.orphan_ids -join ', ')" }

    $verdict = 'REPROVADO'
    if ($postsave.status -eq 'postsave_verified' -and $build.status -eq 'build_verified') {
        $verdict = 'integration_verified'
    }
    elseif ($postsave.status -eq 'text_read_gap') { $verdict = 'PENDENTE DE REVISAO HUMANA' }

    $buildReport = [ordered]@{
        verdict = $verdict; plan = $Plan; plan_sha256 = $planSha
        output_project = $outputPath; output_sha256 = $outputSha
        output_sha256_after_build = $outputShaAfterBuild
        build_status = $build.status
        build_message_count = $build.message_count
        build_message_summary = $build.message_summary
        build_messages_available = $build.messages_available
        build_gap_notes = $build.gap_notes
        postsave_status = $postsave.status
        structural_diff = $postsave.structural_diff
        executions = @($obsBuild, $obsPost)
    }
    Write-JsonNoBom (Join-Path $artifacts 'session-verdict-build.json') $buildReport

    Write-Section "VEREDITO DA ETAPA DE BUILD W1.4: $verdict"
    Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict-build.json')"
    if ($verdict -ne 'integration_verified') { exit 3 }
    exit 0
}

# =============================================================================
# BLOCO 3 -- PREFLIGHT (somente leitura, sobre a copia de trabalho)
# =============================================================================

if (Test-Path -LiteralPath $outputPath) { Fail "output ja existe: $outputPath" }
if (Test-Path -LiteralPath $sessionDir) {
    $ocupado = @(Get-ChildItem -LiteralPath $sessionDir -File -ErrorAction SilentlyContinue)
    if ($ocupado.Count -gt 0) { Fail "Diretorio da copia nao esta isolado/vazio: $sessionDir" }
}

New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
Copy-Item -LiteralPath $basePath -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

$obs1 = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe37 `
    -ScriptArgs ("--mode=preflight --plan=" + $Plan + " --output=" + $preflightDir) `
    -StageDir $preflightDir -Label 'preflight (somente leitura)' `
    -CompletionPath $preflightCompletion

$preflight = Read-Completion $preflightCompletion
if ($null -eq $preflight) { Fail 'w1-4-preflight-completion.json ausente. Sem veredito.' }
Write-Host "[INFO] preflight status: $($preflight.status)"
if ($preflight.status -ne 'preflight_verified') {
    Fail "Preflight NAO passou: $($preflight.status). $($preflight.errors -join ' | ')"
}
$copyShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfter -ne $copySha) { Fail 'A copia MUDOU durante o preflight read-only.' }
if ($obs1.orphan_ids.Count -gt 0) { Fail "Orfaos apos preflight: $($obs1.orphan_ids -join ', ')" }
if (-not (Test-Path -LiteralPath $baselineTree)) {
    Fail "Preflight nao gravou a varredura recursiva: $baselineTree"
}

Write-Section 'PREFLIGHT APROVADO'
if ($Mode -eq 'PreflightOnly') {
    Write-Host 'Container resolvido, nomes-alvo livres, baseline recursiva congelada.'
    Write-Host 'Nenhuma mutacao ocorreu.'
    exit 0
}

# =============================================================================
# BLOCO 4 -- MUTACAO (somente -ExecuteMutation)
#
# Seis mutacoes, um unico save_as, e NENHUM build: compilar aqui misturaria
# "o texto persistiu" com "o texto compila". O build e etapa propria.
# =============================================================================

$probe38 = Join-Path $RepoRoot 'scripts\mastertool\probes\38_author_w1_4.py'
if (-not (Test-Path -LiteralPath $probe38)) { Fail "Probe 38 nao encontrado" }

$planShaFrozen = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
if ($planShaFrozen -ne $planSha) { Fail 'O plano mudou durante a sessao.' }

$mutationDir = Join-Path $artifacts 'mutation'
$mutationCompletion = Join-Path $artifacts 'completion.json'
$obs2 = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe38 `
    -ScriptArgs ("--plan=" + $Plan) -StageDir $mutationDir -Label 'MUTACAO (probe 38)' `
    -CompletionPath $mutationCompletion

$completion = Read-Completion $mutationCompletion
if ($null -eq $completion) {
    Fail 'completion.json ausente. A copia esta em estado DESCONHECIDO: descarte-a.'
}
Write-Host "[INFO] status do probe 38: $($completion.status)"
if ($completion.status -ne 'saved_as') {
    Fail "Mutacao nao terminou em saved_as: $($completion.status). DESCARTE a copia inteira -- nao existe rollback."
}
$inputShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($inputShaAfter -ne $copySha) { Fail 'A copia de ENTRADA foi modificada. Descarte tudo.' }
if (-not (Test-Path -LiteralPath $outputPath)) { Fail 'save_as declarou sucesso sem criar o arquivo.' }
$outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Saida       : $outputPath"
Write-Host "[OK] SHA256 saida: $outputSha"
if ($obs2.orphan_ids.Count -gt 0) { Fail "Orfaos apos mutacao: $($obs2.orphan_ids -join ', ')" }

$sessionReport = [ordered]@{
    verdict = 'saved_as'; plan = $Plan; plan_sha256 = $planSha
    base_project = $basePath; base_sha256 = $baseSha
    working_copy = $copyPath; working_copy_sha256_before = $copySha
    working_copy_sha256_after = $inputShaAfter
    output_project = $outputPath; output_sha256 = $outputSha
    preflight_status = $preflight.status
    mutation_status = $completion.status
    operations_executed = $completion.operations_executed
    no_other_mutator_requested = $completion.no_other_mutator_requested
    authored_gvl_declaration_sha256 = $completion.authored_gvl_declaration_sha256
    authored_program_declaration_sha256 = $completion.authored_program_declaration_sha256
    authored_program_implementation_sha256 = $completion.authored_program_implementation_sha256
    build_pending = $true
    opt_files = @(Get-ChildItem -LiteralPath $sessionDir -File -Filter '*.opt' -ErrorAction SilentlyContinue |
                  ForEach-Object { $_.Name })
    executions = @($obs1, $obs2)
}
Write-JsonNoBom (Join-Path $artifacts 'session-verdict.json') $sessionReport

Write-Section 'AUTORIA W1.4 CONCLUIDA -- BUILD AINDA NAO EXECUTADO'
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"
Write-Host 'O build e etapa propria: rode novamente com -ExecuteBuild.'
exit 0
