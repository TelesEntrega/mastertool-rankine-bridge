# run_w3_idiomatic_call.ps1 -- W3: a chamada IDIOMATICA.
#
# Contrato: docs/41. Motivo: docs/39 secao 1 -- o build de W2 devolveu um aviso
# do FABRICANTE dizendo que o padrao correto e outro:
#
#   "A tarefa MainTask deveria conter apenas a chamada do programa MainPrg.
#    Chamadas adicionais de outros programas devem ser realizadas a partir das
#    POUs correspondentes do Perfil de Projeto (StartPrg, UserPrg, ActivePrg e
#    NonSkippedPrg)"
#
# W2 provou a CAPACIDADE de vincular. Este marco prova o PADRAO: a chamada vai
# para dentro de `UserPrg`, e nao para a lista da task.
#
# MODOS, mutuamente exclusivos:
#   -ValidateOnly     so valida o plano. Nao abre nada, nao copia nada.
#   -ExecuteMutation  copia a entrada, roda o preflight (probe 44, leitura) e
#                     a mutacao (probe 45, replace + save_as).
#   -ExecuteBuild     etapa PROPRIA sobre a saida ja produzida: build (probe 40)
#                     e postsave (probe 44 em modo postsave). Nao autora nada.
#
# O build ser etapa propria e o que separa "escreveu" de "compila", e o
# postsave rodar DEPOIS do build e o que separa "compila em memoria" de
# "compila o texto persistido".
#
# ENTRADA: a saida aprovada de W1.4 -- um projeto que JA tem o PRG_AI_TESTE
# criado e NAO vinculado a task. A entrada nunca e tocada: e copiada, e o hash
# e conferido antes e depois.

param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [switch]$ValidateOnly,
    [switch]$ExecuteMutation,
    [switch]$ExecuteBuild,

    # Plano da etapa de BUILD, obrigatorio em -ExecuteBuild.
    #
    # SAO DOIS PLANOS, e nao um, porque sao duas FASES: a mutacao roda sob
    # `W3_IDIOMATIC_CALL` e o build sob `W3_VERIFY_BUILD`. Um plano so teria de
    # declarar uma das duas, e a outra etapa passaria a rodar sob uma fase que
    # o plano nao declara -- que e exatamente o que a separacao existe para
    # impedir. O postsave continua consumindo o plano da MUTACAO: ele confere o
    # texto da POU, e nao a compilacao.
    [string]$BuildPlan,

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
    # estrito recusa o proprio relatorio da sessao. UTF8Encoding($false) = sem BOM.
    [System.IO.File]::WriteAllText(
        $path, ($data | ConvertTo-Json -Depth 10),
        (New-Object System.Text.UTF8Encoding($false)))
}
function Write-TextNoBom($path, $text) {
    [System.IO.File]::WriteAllText(
        $path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

$selectedModes = @()
if ($ValidateOnly)    { $selectedModes += 'ValidateOnly' }
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

Write-Section "W3 -- chamada idiomatica -- modo '$Mode'"

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

if ($planData.schema_version -ne '1.0') { Fail 'schema_version inesperado' }
if ($planData.operation_id -ne 'w3-idiomatic-call') {
    Fail "operation_id inesperado: $($planData.operation_id)"
}
if ($planData.phase -ne 'W3_IDIOMATIC_CALL') {
    Fail "phase inesperada: $($planData.phase)"
}

# A POU hospedeira e conferida contra a lista do AVISO DO FABRICANTE, e nao
# contra qualquer nome: pendurar a chamada numa POU fora do perfil derrotaria o
# proposito do marco.
$profilePous = @('StartPrg', 'UserPrg', 'ActivePrg', 'NonSkippedPrg')
if ($profilePous -notcontains $planData.call_host) {
    Fail ("call_host deve ser uma POU do Perfil de Projeto (" +
          ($profilePous -join ', ') + ") -- recebido: $($planData.call_host)")
}
if ([string]::IsNullOrWhiteSpace($planData.program_name)) {
    Fail 'program_name ausente no plano'
}

$kinds = @($planData.operations | ForEach-Object { $_.kind })
if ($kinds.Count -ne 2 -or $kinds[0] -ne 'replace' -or $kinds[1] -ne 'save_as') {
    Fail ("Plano deve declarar exatamente replace, save_as -- recebido: " +
          ($kinds -join ', '))
}


$inputPath = $planData.input_project.path
$outputPath = $planData.output_project.path
$sourcePath = $planData.source_project.path
foreach ($p in @($inputPath, $outputPath, $sourcePath)) {
    if ([string]::IsNullOrWhiteSpace($p)) { Fail 'caminho de projeto ausente no plano' }
    if (-not [IO.Path]::IsPathRooted($p)) { Fail "caminho deve ser absoluto: $p" }
}
if (-not (Test-Path -LiteralPath $sourcePath)) {
    Fail "Projeto de origem inexistente: $sourcePath"
}
$sourceSha = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Origem      : $sourcePath"
Write-Host "[OK] SHA256 orig : $sourceSha"
if ($planData.source_project.sha256 -and
    $planData.source_project.sha256 -ne $sourceSha) {
    Fail ("A origem MUDOU desde o plano ($($planData.source_project.sha256) -> " +
          "$sourceSha). Descarte o plano.")
}

$artifacts = $planData.artifacts_dir
if ([string]::IsNullOrWhiteSpace($artifacts)) { Fail 'artifacts_dir ausente no plano' }

# O plano do BUILD e validado com o mesmo rigor, e nunca herdado do outro.
$buildPlanSha = $null
if ($Mode -eq 'ExecuteBuild') {
    if ([string]::IsNullOrWhiteSpace($BuildPlan)) {
        Fail ("-BuildPlan e obrigatorio em -ExecuteBuild: o build roda sob " +
              "W3_VERIFY_BUILD, e o plano da mutacao declara W3_IDIOMATIC_CALL.")
    }
    if (-not (Test-Path -LiteralPath $BuildPlan)) { Fail "Plano de build inexistente: $BuildPlan" }
    if (-not [IO.Path]::IsPathRooted($BuildPlan)) { Fail 'Plano de build deve ser absoluto' }
    try { $buildPlanData = Get-Content -LiteralPath $BuildPlan -Raw | ConvertFrom-Json }
    catch { Fail "Plano de build nao e JSON valido: $($_.Exception.Message)" }
    $buildPlanSha = (Get-FileHash -LiteralPath $BuildPlan -Algorithm SHA256).Hash.ToLower()
    if ($buildPlanData.phase -ne 'W3_VERIFY_BUILD') {
        Fail "phase do plano de build inesperada: $($buildPlanData.phase)"
    }
    $buildKinds = @($buildPlanData.operations | ForEach-Object { $_.kind })
    if ($buildKinds.Count -ne 3 -or $buildKinds[0] -ne 'replace' -or
        $buildKinds[1] -ne 'save_as' -or $buildKinds[2] -ne 'build') {
        Fail ("Plano de build deve declarar replace, save_as, build -- " +
              "recebido: " + ($buildKinds -join ', '))
    }
    # AS DUAS ETAPAS TEM DE FALAR DO MESMO PROJETO. Sem esta conferencia, um
    # plano de build apontado para outra saida compilaria outra coisa, e o
    # veredito seria sobre um artefato que esta sessao nunca produziu.
    if ($buildPlanData.output_project.path -ne $outputPath) {
        Fail ("O plano de build aponta para " +
              "$($buildPlanData.output_project.path), e a mutacao produziu " +
              "$outputPath.")
    }
    Write-Host "[OK] Plano build : $BuildPlan"
    Write-Host "[OK] SHA256 build: $buildPlanSha"
}

if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel inexistente: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
if ($exeVersion -notlike "$ExpectedExeVersion*") {
    Fail "Versao do executavel divergente: $exeVersion (esperada $ExpectedExeVersion)"
}
Write-Host "[OK] Executavel  : $Exe ($exeVersion)"

$running = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $AllowRunningInstance) {
    Fail ("Ha $($running.Count) instancia(s) do MasterTool aberta(s). " +
          "Feche-as: uma sessao com projeto aberto por outra via nao e reprodutivel.")
}
Write-Host '[OK] Nenhuma instancia do MasterTool X aberta.'

$safetyFile = Join-Path $RepoRoot 'scripts\mastertool\common\safety.py'
if (-not (Test-Path -LiteralPath $safetyFile)) { Fail 'safety.py nao encontrado' }
if (-not (Select-String -LiteralPath $safetyFile -Pattern '^READ_ONLY_PHASE\s*=\s*True' -Quiet)) {
    Fail 'READ_ONLY_PHASE deixou de ser True'
}
Write-Host '[OK] READ_ONLY_PHASE = True'

$probe44 = Join-Path $RepoRoot 'scripts\mastertool\probes\44_preflight_w3_readonly.py'
$probe45 = Join-Path $RepoRoot 'scripts\mastertool\probes\45_author_w3_idiomatic_call.py'
$probe40 = Join-Path $RepoRoot 'scripts\mastertool\probes\40_build_w1_4.py'
foreach ($p in @($probe44, $probe45, $probe40)) {
    if (-not (Test-Path -LiteralPath $p)) { Fail "Probe nao encontrado: $p" }
}

$preflightDir = Join-Path $artifacts 'preflight'
$preflightCompletion = Join-Path $preflightDir 'w3-preflight-completion.json'
$originalTextPath = Join-Path $preflightDir 'userprg-original.st'

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

    $limite = (Get-Date).AddSeconds($ArtifactWaitSeconds)
    while (-not (Test-Path -LiteralPath $CompletionPath) -and (Get-Date) -lt $limite) {
        Start-Sleep -Seconds 3
        if ($proc.HasExited) { break }
    }
    $artefatoPresente = Test-Path -LiteralPath $CompletionPath
    Write-Host "[INFO] artefato de conclusao presente: $artefatoPresente"

    $fechadoPeloHost = $false
    if ($AutoCloseWindow -and -not $proc.HasExited) {
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

if ($Mode -ne 'ValidateOnly') {
    if ([string]::IsNullOrWhiteSpace($TemplateQualification)) {
        Fail ("-TemplateQualification e obrigatorio fora de -ValidateOnly: a " +
              "elegibilidade e consultada no artefato do probe 35 (docs/36), " +
              "nunca presumida por este host.")
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
              ($qualification.blocking_issues -join ', '))
    }
    Write-Host "[OK] Template    : elegivel para autoria (artefato: $TemplateQualification)"
}

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'Nada foi aberto, nenhuma copia criada, nada compilado.'
    exit 0
}

# =============================================================================
# BLOCO 2 -- BUILD E POSTSAVE, ETAPA PROPRIA
# =============================================================================

if ($Mode -eq 'ExecuteBuild') {
    if (-not (Test-Path -LiteralPath $outputPath)) {
        Fail "Saida inexistente: $outputPath. Rode -ExecuteMutation antes."
    }
    if (-not (Test-Path -LiteralPath $originalTextPath)) {
        Fail ("Texto original do preflight ausente: $originalTextPath. Sem ele " +
              "o postsave nao consegue provar que o codigo do fabricante " +
              "sobreviveu.")
    }
    $outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()

    Write-Section 'ATENCAO -- LEIA ANTES DE A JANELA ABRIR'
    Write-Host ''
    Write-Host '  O BUILD SEMPRE deixa o projeto "alterado" em memoria.'
    Write-Host '  Diante do dialogo "Deseja salvar as alteracoes?": CLIQUE "NAO".'
    Write-Host '  SIM gravaria o resultado do build por cima da saida, e a sessao'
    Write-Host '  seria reprovada por divergencia de hash.'
    Write-Host ''

    $buildDir = Join-Path $artifacts 'build'
    $buildCompletion = Join-Path $buildDir 'build-completion.json'
    # O probe 40 recebe o plano do BUILD; o postsave, mais abaixo, recebe o da
    # MUTACAO. Cada probe le o plano da fase sob a qual ele roda.
    $obsBuild = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe40 `
        -ScriptArgs ("--plan=" + $BuildPlan + " --output=" + $buildDir +
                     " --output-sha256=" + $outputSha) `
        -StageDir $buildDir -Label 'BUILD (probe 40, abertura separada)' `
        -CompletionPath $buildCompletion

    $build = Read-Completion $buildCompletion
    if ($null -eq $build) { Fail 'build-completion.json ausente. Sem veredito de compilacao.' }
    Write-Host "[INFO] status do build: $($build.status)"
    Write-Host ("[INFO] mensagens do build: $($build.message_count_from_build) " +
                "(total no armazem: $($build.message_count_total); " +
                "pre-existentes: $($build.messages_baseline_count))")

    $outputShaAfterBuild = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
    if ($outputShaAfterBuild -ne $outputSha) {
        Fail 'O arquivo de saida MUDOU durante o build. Nenhum save foi pedido.'
    }
    if ($obsBuild.orphan_ids.Count -gt 0) { Fail "Orfaos apos build: $($obsBuild.orphan_ids -join ', ')" }

    # O AVISO DO FABRICANTE E O CRITERIO DESTE MARCO, e por isso ele e lido
    # aqui em vez de ficar so no artefato: W3 existe para faze-lo desaparecer.
    #
    # AUSENCIA DE AVISO SO SIGNIFICA ALGUMA COISA SE O BUILD RODOU. A primeira
    # versao deste bloco imprimiu "o aviso NAO aparece" sobre um build que
    # tinha reprovado em `precondition_failed` -- ou seja, anunciou o resultado
    # que o marco procura a partir de uma compilacao que nunca aconteceu. E o
    # mesmo modo de falha que o probe 40 combate com `no_build_messages`, e ele
    # reapareceu aqui, no host.
    #
    # Tres estados, e nao dois: presente, ausente, NAO MEDIDO.
    $vendorWarning = $null
    $vendorWarningMeasured = ($build.status -eq 'build_verified')
    if ($vendorWarningMeasured) {
        $messagesPath = Join-Path $buildDir 'build-messages.json'
        if (Test-Path -LiteralPath $messagesPath) {
            try {
                $messages = Get-Content -LiteralPath $messagesPath -Raw | ConvertFrom-Json
                foreach ($m in $messages.messages) {
                    if ($m.pre_existing -eq $true) { continue }
                    if ($m.text -and $m.text -like '*deveria conter apenas a chamada*') {
                        $vendorWarning = $m.text
                    }
                }
            } catch { $vendorWarningMeasured = $false }
        }
        else { $vendorWarningMeasured = $false }
    }
    if (-not $vendorWarningMeasured) {
        Write-Host ("[NAO MEDIDO] O build nao chegou a `build_verified` " +
                    "(status: $($build.status)). A pergunta do marco -- o aviso " +
                    "do fabricante desaparece? -- NAO foi respondida.") -ForegroundColor Yellow
    }
    elseif ($vendorWarning) {
        Write-Host '[ACHADO] O aviso do fabricante CONTINUA presente:' -ForegroundColor Yellow
        Write-Host "         $vendorWarning" -ForegroundColor Yellow
    }
    else {
        Write-Host '[OK] O aviso do fabricante sobre chamadas na task NAO aparece.'
    }

    $postsaveDir = Join-Path $artifacts 'postsave'
    $postsaveCompletion = Join-Path $postsaveDir 'w3-preflight-completion.json'
    $originalSha = (Get-FileHash -LiteralPath $originalTextPath -Algorithm SHA256).Hash.ToLower()
    $obsPost = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe44 `
        -ScriptArgs ("--mode=postsave --plan=" + $Plan + " --output=" + $postsaveDir +
                     " --original-implementation=" + $originalTextPath) `
        -StageDir $postsaveDir -Label 'postsave (somente leitura, apos o build)' `
        -CompletionPath $postsaveCompletion

    $postsave = Read-Completion $postsaveCompletion
    if ($null -eq $postsave) { Fail 'w3-preflight-completion.json (postsave) ausente.' }
    Write-Host "[INFO] postsave status: $($postsave.status)"
    if ($obsPost.orphan_ids.Count -gt 0) { Fail "Orfaos apos postsave: $($obsPost.orphan_ids -join ', ')" }

    if (-not $vendorWarningMeasured) { $verdict = 'NAO MEDIDO' }
    elseif ($postsave.status -eq 'postsave_verified' -and
            $build.status -eq 'build_verified') {
        $verdict = if ($vendorWarning) { 'IDIOMATICO NAO CONFIRMADO' } else { 'idiomatic_call_verified' }
    }
    else { $verdict = 'REPROVADO' }

    $verdictPath = Join-Path $artifacts 'session-verdict-build.json'
    Write-JsonNoBom $verdictPath ([ordered]@{
        plan = $Plan; plan_sha256 = $planSha
        output_project = $outputPath; output_sha256 = $outputSha
        output_sha256_after_build = $outputShaAfterBuild
        build_status = $build.status
        build_message_count_from_build = $build.message_count_from_build
        build_message_count_total = $build.message_count_total
        # `$null` quando NAO MEDIDO. `false` diria "o aviso nao aparece", que e
        # uma afirmacao sobre uma compilacao que talvez nao tenha acontecido.
        vendor_warning_measured = $vendorWarningMeasured
        vendor_warning_present = if ($vendorWarningMeasured) { [bool]$vendorWarning } else { $null }
        vendor_warning_text = $vendorWarning
        postsave_status = $postsave.status
        call_host = $planData.call_host
        verdict = $verdict
    })

    Write-Section "VEREDITO DA ETAPA DE BUILD W3: $verdict"
    Write-Host "Relatorio: $verdictPath"
    if ($verdict -ne 'idiomatic_call_verified') { exit 3 }
    exit 0
}

# =============================================================================
# BLOCO 3 -- PREFLIGHT E MUTACAO
# =============================================================================

if (Test-Path -LiteralPath $outputPath) {
    Fail "A saida ja existe: $outputPath. Este host nunca sobrescreve."
}

# A COPIA E CRIADA AQUI, e nao pelo probe. Um probe que criasse a propria copia
# poderia, num caminho de erro, abrir o original -- e o original e a testemunha.
$inputDir = Split-Path -Parent $inputPath
New-Item -ItemType Directory -Force -Path $inputDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null
if (Test-Path -LiteralPath $inputPath) {
    Fail "A copia de trabalho ja existe: $inputPath. Descarte-a antes."
}
Copy-Item -LiteralPath $sourcePath -Destination $inputPath
$inputSha = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToLower()
if ($inputSha -ne $sourceSha) { Fail 'A copia difere da origem. Abortado.' }
Write-Host "[OK] Copia       : $inputPath"
Write-Host "[OK] SHA256 copia: $inputSha (identico a origem)"

$obsPre = Invoke-MasterTool -ProjectPath $inputPath -ProbePath $probe44 `
    -ScriptArgs ("--mode=preflight --plan=" + $Plan + " --output=" + $preflightDir) `
    -StageDir $preflightDir -Label 'preflight (somente leitura)' `
    -CompletionPath $preflightCompletion

$preflight = Read-Completion $preflightCompletion
if ($null -eq $preflight) { Fail 'w3-preflight-completion.json ausente.' }
Write-Host "[INFO] preflight status: $($preflight.status)"
Write-Host "[INFO] POUs de perfil presentes: $($preflight.profile_pous_present -join ', ')"
Write-Host "[INFO] POUs de perfil ausentes : $($preflight.profile_pous_absent -join ', ')"
if ($preflight.status -ne 'preflight_verified') {
    Fail "Preflight NAO aprovado: $($preflight.status). $($preflight.errors -join ' | ')"
}
if ($obsPre.orphan_ids.Count -gt 0) { Fail "Orfaos apos preflight: $($obsPre.orphan_ids -join ', ')" }

# O TEXTO LIDO PELO PREFLIGHT VIRA ARQUIVO, e e ele que a mutacao consome.
# Sem isto a mutacao escreveria a partir de uma leitura que ninguem registrou,
# e "preservou o codigo do fabricante" viraria afirmacao sem testemunha.
$pousPath = Join-Path $preflightDir 'w3-profile-pous.json'
if (-not (Test-Path -LiteralPath $pousPath)) { Fail 'w3-profile-pous.json ausente.' }
$pous = Get-Content -LiteralPath $pousPath -Raw | ConvertFrom-Json
$host_entry = $null
foreach ($e in $pous.profile_pous) {
    if ($e.name -eq $planData.call_host) { $host_entry = $e }
}
if ($null -eq $host_entry) { Fail "POU $($planData.call_host) ausente no artefato do preflight." }
if ($host_entry.implementation.state -ne 'read') {
    Fail ("Implementacao de $($planData.call_host) nao foi lida " +
          "(state=$($host_entry.implementation.state)). Escrever sem ter lido " +
          "apagaria o codigo do fabricante.")
}
Write-TextNoBom $originalTextPath $host_entry.implementation.text
$writtenSha = (Get-FileHash -LiteralPath $originalTextPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Texto original de $($planData.call_host): $($host_entry.implementation.text.Length) caracteres"
Write-Host "[OK] SHA256 do texto (probe): $($host_entry.implementation.sha256)"

# O SHA que a mutacao recebe e o do PROBE, calculado sobre o texto em memoria do
# produto -- e nao o do arquivo que este host acabou de gravar. Os dois tem de
# bater; se nao baterem, a gravacao alterou o texto e a mutacao seria feita
# sobre outra coisa.
$probeSha = $host_entry.implementation.sha256
$fileText = [System.IO.File]::ReadAllText($originalTextPath, (New-Object System.Text.UTF8Encoding($false)))
$fileSha = [System.BitConverter]::ToString(
    (New-Object System.Security.Cryptography.SHA256Managed).ComputeHash(
        [System.Text.Encoding]::UTF8.GetBytes($fileText))).Replace('-', '').ToLower()
if ($fileSha -ne $probeSha) {
    Fail ("O texto gravado por este host ($fileSha) difere do que o probe leu " +
          "($probeSha). A mutacao seria feita sobre outro texto.")
}
Write-Host '[OK] O texto gravado confere com o que o probe leu.'

$mutationDir = $artifacts
$mutationCompletion = Join-Path $mutationDir 'w3-completion.json'
$obsMut = Invoke-MasterTool -ProjectPath $inputPath -ProbePath $probe45 `
    -ScriptArgs ("--plan=" + $Plan + " --output=" + $mutationDir +
                 " --original-implementation=" + $originalTextPath +
                 " --original-implementation-sha256=" + $probeSha) `
    -StageDir $mutationDir -Label 'MUTACAO (probe 45: replace + save_as)' `
    -CompletionPath $mutationCompletion

$mutation = Read-Completion $mutationCompletion
if ($null -eq $mutation) { Fail 'w3-completion.json ausente. Sem veredito da mutacao.' }
Write-Host "[INFO] status do probe 45: $($mutation.status)"
if ($mutation.status -ne 'saved_as') {
    Fail "Mutacao NAO aprovada: $($mutation.status). $($mutation.errors -join ' | ')"
}
if ($obsMut.orphan_ids.Count -gt 0) { Fail "Orfaos apos mutacao: $($obsMut.orphan_ids -join ', ')" }
if (-not (Test-Path -LiteralPath $outputPath)) { Fail "Saida nao foi criada: $outputPath" }

$outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
$inputShaAfter = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToLower()
if ($inputShaAfter -ne $inputSha) {
    Write-Host '[INFO] a copia de trabalho mudou durante a sessao (esperado: o' -ForegroundColor Yellow
    Write-Host '       replace acontece nela antes do save_as).' -ForegroundColor Yellow
}
$sourceShaAfter = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLower()
if ($sourceShaAfter -ne $sourceSha) {
    Fail "A ORIGEM MUDOU ($sourceSha -> $sourceShaAfter). Isto nunca deveria acontecer."
}
Write-Host "[OK] Origem intacta: $sourceShaAfter"
Write-Host "[OK] Saida       : $outputPath"
Write-Host "[OK] SHA256 saida: $outputSha"

$verdictPath = Join-Path $artifacts 'session-verdict.json'
Write-JsonNoBom $verdictPath ([ordered]@{
    plan = $Plan; plan_sha256 = $planSha
    source_project = $sourcePath; source_sha256 = $sourceSha
    source_sha256_after = $sourceShaAfter
    work_copy = $inputPath
    output_project = $outputPath; output_sha256 = $outputSha
    call_host = $planData.call_host
    program_name = $planData.program_name
    original_sha256 = $mutation.original_sha256
    final_sha256 = $mutation.final_sha256
    preflight_status = $preflight.status
    mutation_status = $mutation.status
    profile_pous_present = $preflight.profile_pous_present
    profile_pous_absent = $preflight.profile_pous_absent
})

Write-Section 'AUTORIA W3 CONCLUIDA -- BUILD AINDA NAO EXECUTADO'
Write-Host "Relatorio: $verdictPath"
Write-Host 'O build e etapa propria: rode novamente com -ExecuteBuild.'
exit 0
