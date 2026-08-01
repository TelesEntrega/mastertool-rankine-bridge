# run_project_factory.ps1 -- a FABRICA: spec -> plano -> projeto.
#
# Contrato: docs/42.
#
# E o unico host que nao carrega o nome de nenhum objeto no proprio codigo. Os
# marcos anteriores tinham `GVL_AI_TESTE` e `PRG_AI_TESTE` escritos no fonte do
# probe; aqui os nomes vem da SPEC, e trocar a spec troca o projeto gerado sem
# tocar em codigo.
#
# CADEIA:
#
#   1. spec.json          escrita por quem projeta a maquina
#   2. planner (host)     valida offline e emite o plano; recusa fail-closed se
#                         alguma operacao nao foi PROVADA em campo
#   3. probe 46           executa o plano dentro do MasterTool
#   4. probe 40           compila, em fase e abertura PROPRIAS
#
# O plano e a spec ficam em artefatos SEPARADOS, amarrados por hash: o plano
# carrega `planned_after_sha256` de cada texto, a spec carrega o texto, e o
# executor so escreve o que o hash autorizar. Um plano que carregasse o texto
# final autorizaria a si mesmo a escrever qualquer coisa.
#
# MODOS, mutuamente exclusivos:
#   -ValidateOnly     roda o planner e mostra o veredito. Nao abre nada.
#   -ExecutePlan      copia o template e executa o plano (probe 46).
#   -ExecuteBuild     etapa PROPRIA sobre a saida: build (probe 40).

param(
    [Parameter(Mandatory = $true)]
    [string]$Spec,

    [switch]$ValidateOnly,
    [switch]$ExecutePlan,
    [switch]$ExecuteBuild,

    [string]$WorkRoot,
    [string]$BuildPlan,
    [string]$TemplateProject,
    [string]$TemplateQualification,

    # EXECUCAO DE PROVA. Aceita um plano bloqueado APENAS por
    # `operation_not_field_proven` -- a situacao em que a operacao tem API
    # catalogada e nunca foi exercida numa cadeia que persistiu e compilou.
    #
    # Este interruptor NAO autoriza nada: quem autoriza e a fase, e o probe 46
    # recusa se o verbo nao estiver na allowlist LITERAL dela. O que ele faz e
    # nao bloquear ANTES de o probe poder decidir -- sem ele o host reprovaria
    # a run de prova pelo exit 3 do planner, e a operacao ficaria impossivel de
    # provar (o planner nao emite plano executavel sem prova, e sem executar nao
    # ha prova).
    #
    # Spec invalida (exit 2 do planner) continua reprovando com ou sem ele.
    [switch]$AllowProvingRun,

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
    [System.IO.File]::WriteAllText(
        $path, ($data | ConvertTo-Json -Depth 10),
        (New-Object System.Text.UTF8Encoding($false)))
}

$selectedModes = @()
if ($ValidateOnly) { $selectedModes += 'ValidateOnly' }
if ($ExecutePlan)  { $selectedModes += 'ExecutePlan' }
if ($ExecuteBuild) { $selectedModes += 'ExecuteBuild' }
if ($selectedModes.Count -gt 1) {
    Fail ("Modos mutuamente exclusivos: " + ($selectedModes -join ', '))
}
if ($selectedModes.Count -eq 0) {
    $Mode = 'ValidateOnly'
    Write-Host '[INFO] Nenhum modo informado: assumindo -ValidateOnly (default).'
}
else { $Mode = $selectedModes[0] }

$ProcessPattern = [IO.Path]::GetFileNameWithoutExtension($Exe) + '*'

Write-Section "FABRICA DE PROJETOS -- modo '$Mode'"

# =============================================================================
# BLOCO 1 -- A SPEC E O PLANO (host, offline)
# =============================================================================

if (-not (Test-Path -LiteralPath $Spec)) { Fail "Spec inexistente: $Spec" }
if (-not [IO.Path]::IsPathRooted($Spec)) { Fail "Spec deve ser absoluta: $Spec" }
if ($Spec -match '\s') { Fail "Spec em caminho com espaco: $Spec" }
$specSha = (Get-FileHash -LiteralPath $Spec -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Spec        : $Spec"
Write-Host "[OK] SHA256 spec : $specSha"

if ([string]::IsNullOrWhiteSpace($WorkRoot)) {
    Fail '-WorkRoot e obrigatorio: e onde a copia de trabalho e a saida vivem.'
}
if (-not [IO.Path]::IsPathRooted($WorkRoot)) { Fail '-WorkRoot deve ser absoluto' }
if ($WorkRoot -match '\s') {
    Fail "-WorkRoot com espaco: $WorkRoot. `--scriptargs` quebra o valor em espaco em branco."
}

$artifacts = Join-Path $WorkRoot 'artefatos'
$planPath = Join-Path $artifacts 'authoring-plan.json'
$workProject = Join-Path $WorkRoot 'projeto\FABRICA-work.project'
$outputProject = Join-Path $WorkRoot 'saida\FABRICA.project'

$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { Fail "Interpretador nao encontrado: $python" }

# O PLANNER RODA AQUI, e o plano e gravado como artefato ANTES de qualquer
# janela abrir. Um plano que so existisse na memoria do host nao poderia ser
# conferido depois nem citado num relatorio.
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
$planScript = Join-Path $RepoRoot 'scripts\mastertool\emit_authoring_plan.py'
if (-not (Test-Path -LiteralPath $planScript)) { Fail "Emissor de plano ausente: $planScript" }
Write-Section 'Planner (host, offline)'
& $python $planScript --spec $Spec --out $planPath
$plannerExit = $LASTEXITCODE
# 2 = spec invalida (nenhum plano gravado). 3 = plano gravado e nao executavel.
# A distincao existe justamente para que a segunda possa ser tratada aqui.
if ($plannerExit -eq 2) {
    Fail "O planner recusou a SPEC (exit 2). Nada foi gravado, nada foi aberto."
}
if ($plannerExit -eq 3 -and -not $AllowProvingRun) {
    Fail ("Plano NAO executavel (exit 3) e -AllowProvingRun ausente. Se a " +
          "unica lacuna for `operation_not_field_proven`, esta e uma execucao " +
          "de PROVA e exige o interruptor explicito -- e a fase precisa " +
          "autorizar o verbo.")
}
if ($plannerExit -ne 0 -and $plannerExit -ne 3) {
    Fail "O planner falhou (exit $plannerExit). Nada foi aberto."
}
if (-not (Test-Path -LiteralPath $planPath)) { Fail 'Plano nao foi gravado.' }
$planData = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
$planSha = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Plano       : $planPath"
Write-Host "[OK] SHA256 plano: $planSha"
Write-Host "[OK] Passos      : $($planData.steps.Count)"
Write-Host "[OK] Allowlist   : $($planData.required_allowlist -join ', ')"
Write-Host "[OK] Executavel  : $($planData.executable)"
if ($planData.executable -ne $true) {
    $motivos = @($planData.measurement_gaps | ForEach-Object { $_.kind } | Sort-Object -Unique)
    if (-not $AllowProvingRun) {
        Fail ("Plano NAO executavel. Lacunas: " + ($motivos -join ', ') +
              ". Provar a operacao em campo vem antes de executar.")
    }
    # SO a lacuna de prova e tolerada, e mesmo assim so ate o probe decidir.
    # Uma lacuna de API nao catalogada ou de GUID nao medido nao vira execucao
    # de prova por um interruptor de linha de comando.
    if (($motivos -join ',') -ne 'operation_not_field_proven') {
        Fail ("-AllowProvingRun cobre EXCLUSIVAMENTE " +
              "`operation_not_field_proven`. Lacunas presentes: " +
              ($motivos -join ', ') + ".")
    }
    Write-Host ''
    Write-Host '  EXECUCAO DE PROVA' -ForegroundColor Yellow
    Write-Host '  Operacoes com API catalogada e SEM prova em cadeia:' -ForegroundColor Yellow
    foreach ($g in $planData.measurement_gaps) {
        Write-Host ("    - " + $g.detail.Split("'")[1]) -ForegroundColor Yellow
    }
    Write-Host '  Quem autoriza e a FASE, e o probe 46 recusa se o verbo nao' -ForegroundColor Yellow
    Write-Host '  estiver na allowlist literal dela. Este interruptor apenas nao' -ForegroundColor Yellow
    Write-Host '  bloqueia antes de o probe poder decidir.' -ForegroundColor Yellow
    Write-Host ''
}

if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel inexistente: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
if ($exeVersion -notlike "$ExpectedExeVersion*") {
    Fail "Versao do executavel divergente: $exeVersion (esperada $ExpectedExeVersion)"
}
Write-Host "[OK] Executavel  : $Exe ($exeVersion)"

$running = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $AllowRunningInstance) {
    Fail ("Ha $($running.Count) instancia(s) do MasterTool aberta(s). Feche-as.")
}
Write-Host '[OK] Nenhuma instancia do MasterTool X aberta.'

$safetyFile = Join-Path $RepoRoot 'scripts\mastertool\common\safety.py'
if (-not (Select-String -LiteralPath $safetyFile -Pattern '^READ_ONLY_PHASE\s*=\s*True' -Quiet)) {
    Fail 'READ_ONLY_PHASE deixou de ser True'
}
Write-Host '[OK] READ_ONLY_PHASE = True'

$probe46 = Join-Path $RepoRoot 'scripts\mastertool\probes\46_execute_authoring_plan.py'
$probe40 = Join-Path $RepoRoot 'scripts\mastertool\probes\40_build_w1_4.py'
$probe47 = Join-Path $RepoRoot 'scripts\mastertool\probes\47_verify_factory_output_readonly.py'
foreach ($p in @($probe46, $probe40, $probe47)) {
    if (-not (Test-Path -LiteralPath $p)) { Fail "Probe nao encontrado: $p" }
}

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
              "elegibilidade e consultada no artefato do probe 35 (docs/36).")
    }
    try { $qualification = Get-Content -LiteralPath $TemplateQualification -Raw | ConvertFrom-Json }
    catch { Fail "Artefato de qualificacao nao e JSON valido." }
    if ($null -eq $qualification.PSObject.Properties['authoring_eligible']) {
        Fail 'Artefato de qualificacao sem authoring_eligible. Campo ausente nao e "elegivel".'
    }
    if ($qualification.authoring_eligible -ne $true) {
        Fail ("Template NAO elegivel para autoria. Bloqueadores: " +
              ($qualification.blocking_issues -join ', '))
    }
    Write-Host "[OK] Template    : elegivel para autoria"
}

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'O plano foi gravado. Nada foi aberto, nenhuma copia criada.'
    Write-Host "Plano: $planPath"
    exit 0
}

# =============================================================================
# BLOCO 2 -- BUILD, ETAPA PROPRIA
# =============================================================================

if ($Mode -eq 'ExecuteBuild') {
    if (-not (Test-Path -LiteralPath $outputProject)) {
        Fail "Saida inexistente: $outputProject. Rode -ExecutePlan antes."
    }
    if ([string]::IsNullOrWhiteSpace($BuildPlan)) {
        Fail '-BuildPlan e obrigatorio em -ExecuteBuild: o build roda sob fase propria.'
    }
    try { $buildPlanData = Get-Content -LiteralPath $BuildPlan -Raw | ConvertFrom-Json }
    catch { Fail 'Plano de build nao e JSON valido.' }
    if ($buildPlanData.output_project.path -ne $outputProject) {
        Fail ("O plano de build aponta para $($buildPlanData.output_project.path), " +
              "e a execucao produziu $outputProject.")
    }
    $outputSha = (Get-FileHash -LiteralPath $outputProject -Algorithm SHA256).Hash.ToLower()

    Write-Section 'ATENCAO -- LEIA ANTES DE A JANELA ABRIR'
    Write-Host '  O BUILD SEMPRE deixa o projeto "alterado" em memoria.'
    Write-Host '  Diante do dialogo "Deseja salvar as alteracoes?": CLIQUE "NAO".'

    $buildDir = Join-Path $artifacts 'build'
    $buildCompletion = Join-Path $buildDir 'build-completion.json'
    $obsBuild = Invoke-MasterTool -ProjectPath $outputProject -ProbePath $probe40 `
        -ScriptArgs ("--plan=" + $BuildPlan + " --output=" + $buildDir +
                     " --output-sha256=" + $outputSha) `
        -StageDir $buildDir -Label 'BUILD (probe 40, abertura separada)' `
        -CompletionPath $buildCompletion

    $build = Read-Completion $buildCompletion
    if ($null -eq $build) { Fail 'build-completion.json ausente.' }
    Write-Host "[INFO] status do build: $($build.status)"
    Write-Host ("[INFO] mensagens do build: $($build.message_count_from_build) " +
                "(total no armazem: $($build.message_count_total); " +
                "pre-existentes: $($build.messages_baseline_count))")

    $outputShaAfterBuild = (Get-FileHash -LiteralPath $outputProject -Algorithm SHA256).Hash.ToLower()
    if ($outputShaAfterBuild -ne $outputSha) {
        Fail 'O arquivo de saida MUDOU durante o build. Nenhum save foi pedido.'
    }
    if ($obsBuild.orphan_ids.Count -gt 0) { Fail "Orfaos apos build: $($obsBuild.orphan_ids -join ', ')" }

    # O aviso de convencao do fabricante e criterio: a fabrica gera pela forma
    # idiomatica, entao ele NAO pode aparecer. So e conclusivo se o build rodou.
    $vendorWarning = $null
    # TODO AVISO CONTA, e nao so o de convencao.
    #
    # A primeira versao procurava UM texto especifico e devolvia veredito verde
    # diante de qualquer outro. A run-032 saiu `factory_output_verified` com
    # "No POU is defined for task 'TaskDiagnostico'" no artefato -- um aviso
    # real do compilador, que ninguem estava olhando. A fabrica existe para
    # gerar projeto limpo, e um aviso que ninguem leu nao e limpo.
    $allWarnings = @()
    $vendorWarningMeasured = ($build.status -eq 'build_verified')
    if ($vendorWarningMeasured) {
        $messagesPath = Join-Path $buildDir 'build-messages.json'
        if (Test-Path -LiteralPath $messagesPath) {
            try {
                $messages = Get-Content -LiteralPath $messagesPath -Raw | ConvertFrom-Json
                foreach ($m in $messages.messages) {
                    if ($m.pre_existing -eq $true) { continue }
                    if ($m.severity -eq 'warning') { $allWarnings += $m.text }
                    if ($m.text -and $m.text -like '*deveria conter apenas a chamada*') {
                        $vendorWarning = $m.text
                    }
                }
            } catch { $vendorWarningMeasured = $false }
        }
        else { $vendorWarningMeasured = $false }
    }
    if ($allWarnings.Count -gt 0) {
        Write-Host "[ACHADO] O build devolveu $($allWarnings.Count) aviso(s):" -ForegroundColor Yellow
        foreach ($w in $allWarnings) { Write-Host "         $w" -ForegroundColor Yellow }
    }
    if (-not $vendorWarningMeasured) {
        Write-Host ("[NAO MEDIDO] O build nao chegou a build_verified " +
                    "(status: $($build.status)). A pergunta sobre o aviso do " +
                    "fabricante NAO foi respondida.") -ForegroundColor Yellow
    }
    elseif ($vendorWarning) {
        Write-Host '[ACHADO] O aviso do fabricante CONTINUA presente:' -ForegroundColor Yellow
        Write-Host "         $vendorWarning" -ForegroundColor Yellow
    }
    else {
        Write-Host '[OK] Nenhum aviso de convencao do fabricante.'
    }

    # --- VERIFICACAO: terceira abertura, somente leitura, DEPOIS do build ---
    #
    # O executor sabe o que ESCREVEU; ele nao sabe o que ficou no arquivo. Esta
    # etapa reabre a saida numa sessao NOVA e le do disco -- e e essa diferenca
    # que separa "existiu na sessao" de "foi persistido" (docs/32 secao 3).
    #
    # Ela tambem produz a evidencia que torna DUAS execucoes comparaveis: o
    # `.project` tem GUID e timestamp, entao "e o mesmo projeto?" so se
    # responde por conteudo.
    $verifyDir = Join-Path $artifacts 'verificacao'
    $verifyCompletion = Join-Path $verifyDir 'factory-verify-completion.json'
    $obsVerify = Invoke-MasterTool -ProjectPath $outputProject -ProbePath $probe47 `
        -ScriptArgs ("--plan=" + $planPath + " --output=" + $verifyDir +
                     " --output-sha256=" + $outputSha) `
        -StageDir $verifyDir -Label 'VERIFICACAO (probe 47, somente leitura)' `
        -CompletionPath $verifyCompletion

    $verify = Read-Completion $verifyCompletion
    if ($null -eq $verify) { Fail 'factory-verify-completion.json ausente.' }
    Write-Host "[INFO] verificacao: $($verify.status)"
    Write-Host ("[INFO] objetos: $($verify.objects_verified) de " +
                "$($verify.objects_total) verificados; nos: $($verify.node_count)")
    if ($obsVerify.orphan_ids.Count -gt 0) {
        Fail "Orfaos apos verificacao: $($obsVerify.orphan_ids -join ', ')"
    }

    if (-not $vendorWarningMeasured) { $verdict = 'NAO MEDIDO' }
    elseif ($build.status -eq 'build_verified' -and $allWarnings.Count -eq 0 -and
            $verify.status -eq 'factory_output_verified') {
        $verdict = 'factory_output_verified'
    }
    elseif ($allWarnings.Count -gt 0) { $verdict = 'AVISOS PRESENTES' }
    else { $verdict = 'REPROVADO' }

    $verdictPath = Join-Path $artifacts 'factory-verdict-build.json'
    Write-JsonNoBom $verdictPath ([ordered]@{
        spec = $Spec; spec_sha256 = $specSha
        plan = $planPath; plan_sha256 = $planSha
        output_project = $outputProject; output_sha256 = $outputSha
        output_sha256_after_build = $outputShaAfterBuild
        build_status = $build.status
        build_message_count_from_build = $build.message_count_from_build
        vendor_warning_measured = $vendorWarningMeasured
        vendor_warning_present = if ($vendorWarningMeasured) { [bool]$vendorWarning } else { $null }
        warning_count = $allWarnings.Count
        warnings = $allWarnings
        verify_status = $verify.status
        objects_verified = $verify.objects_verified
        objects_total = $verify.objects_total
        node_count = $verify.node_count
        verdict = $verdict
    })

    Write-Section "VEREDITO DA FABRICA: $verdict"
    Write-Host "Relatorio: $verdictPath"
    if ($verdict -ne 'factory_output_verified') { exit 3 }
    exit 0
}

# =============================================================================
# BLOCO 3 -- EXECUCAO DO PLANO
# =============================================================================

if ([string]::IsNullOrWhiteSpace($TemplateProject)) {
    Fail '-TemplateProject e obrigatorio em -ExecutePlan.'
}
if (-not (Test-Path -LiteralPath $TemplateProject)) {
    Fail "Template inexistente: $TemplateProject"
}
$templateSha = (Get-FileHash -LiteralPath $TemplateProject -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Template    : $TemplateProject"
Write-Host "[OK] SHA256 tmpl : $templateSha"
if ($planData.template.sha256 -and $planData.template.sha256 -ne $templateSha) {
    Fail ("A spec declara o template $($planData.template.sha256) e o arquivo " +
          "e $templateSha. Executar assim geraria projeto sobre outra base.")
}

if (Test-Path -LiteralPath $outputProject) {
    Fail "A saida ja existe: $outputProject. Este host nunca sobrescreve."
}
if (Test-Path -LiteralPath $workProject) {
    Fail "A copia de trabalho ja existe: $workProject. Descarte-a antes."
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $workProject) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputProject) | Out-Null
Copy-Item -LiteralPath $TemplateProject -Destination $workProject
$workSha = (Get-FileHash -LiteralPath $workProject -Algorithm SHA256).Hash.ToLower()
if ($workSha -ne $templateSha) { Fail 'A copia difere do template. Abortado.' }
Write-Host "[OK] Copia       : $workProject"
Write-Host "[OK] SHA256 copia: $workSha (identico ao template)"

$execDir = Join-Path $artifacts 'execucao'
$execCompletion = Join-Path $execDir 'execution-completion.json'
$obsExec = Invoke-MasterTool -ProjectPath $workProject -ProbePath $probe46 `
    -ScriptArgs ("--plan=" + $planPath + " --spec=" + $Spec +
                 " --output=" + $execDir + " --output-project=" + $outputProject) `
    -StageDir $execDir -Label 'EXECUCAO DO PLANO (probe 46)' `
    -CompletionPath $execCompletion

$exec = Read-Completion $execCompletion
if ($null -eq $exec) { Fail 'execution-completion.json ausente. Sem veredito.' }
Write-Host "[INFO] status da execucao: $($exec.status)"
Write-Host "[INFO] passos: $($exec.steps_executed) executados, $($exec.steps_delegated) delegados, de $($exec.steps_total)"
Write-Host "[INFO] objetos criados: $(@($exec.created_objects | ForEach-Object { $_.name }) -join ', ')"
if ($exec.status -ne 'plan_executed') {
    Fail "Execucao NAO aprovada: $($exec.status). $($exec.errors -join ' | ')"
}
if ($obsExec.orphan_ids.Count -gt 0) { Fail "Orfaos apos execucao: $($obsExec.orphan_ids -join ', ')" }
if (-not (Test-Path -LiteralPath $outputProject)) { Fail "Saida nao foi criada." }

$templateShaAfter = (Get-FileHash -LiteralPath $TemplateProject -Algorithm SHA256).Hash.ToLower()
if ($templateShaAfter -ne $templateSha) {
    Fail "O TEMPLATE MUDOU ($templateSha -> $templateShaAfter). Isto nunca deveria acontecer."
}
Write-Host "[OK] Template intacto: $templateShaAfter"
$outputSha = (Get-FileHash -LiteralPath $outputProject -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Saida       : $outputProject"
Write-Host "[OK] SHA256 saida: $outputSha"

$verdictPath = Join-Path $artifacts 'factory-verdict.json'
Write-JsonNoBom $verdictPath ([ordered]@{
    spec = $Spec; spec_sha256 = $specSha
    plan = $planPath; plan_sha256 = $planSha
    template = $TemplateProject; template_sha256 = $templateSha
    template_sha256_after = $templateShaAfter
    work_copy = $workProject
    output_project = $outputProject; output_sha256 = $outputSha
    steps_total = $exec.steps_total
    steps_executed = $exec.steps_executed
    steps_delegated = $exec.steps_delegated
    created_objects = $exec.created_objects
    execution_status = $exec.status
})

Write-Section 'PLANO EXECUTADO -- BUILD AINDA NAO'
Write-Host "Relatorio: $verdictPath"
Write-Host 'O build e etapa propria: rode novamente com -ExecuteBuild.'
exit 0
