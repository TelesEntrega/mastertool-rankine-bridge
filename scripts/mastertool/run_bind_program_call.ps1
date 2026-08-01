<#
.SYNOPSIS
    Host supervisionado do marco W2 -- Task Configuration e Program Call:
    reconhecimento read-only das tasks (probe 42) e, em modo proprio, o vinculo
    do PROGRAM a uma task JA EXISTENTE (probe 43: add + save_as).

.DESCRIPTION
    FAIL-CLOSED. Tres modos MUTUAMENTE EXCLUSIVOS; o default NAO ABRE NADA:

        -ValidateOnly    (DEFAULT) valida plano, executavel, hashes, fonte dos
                         probes e a fase de escrita. Nao abre o MasterTool,
                         nao copia nada.
        -ReconOnly       cria a copia descartavel e roda o probe 42 sobre ela,
                         SOMENTE LEITURA. Mede quantas tasks existem, como cada
                         uma esta configurada e o que cada uma ja executa.
                         Nenhuma escrita: este ramo nunca alcanca o probe 43.
        -ExecuteMutation recon + probe 43 (as DUAS mutacoes: add e save_as) +
                         reabertura da SAIDA com o probe 42 em --mode=postsave
                         para provar que o vinculo PERSISTIU.

    POR QUE VINCULAR A UMA TASK EXISTENTE. O projeto-base ja tem task (medida
    nas runs 011 e 018). Reutiliza-la deixa a superficie mutavel em UMA
    operacao -- so `add`. `create_task` nao entra neste marco e nao aparece em
    probe nenhum dele.

    A GUARDA DE FONTE E POR NOME AQUI, E POR RECEPTOR NOS TESTES. Este host le
    o FONTE dos probes antes de abrir o produto e recusa a sessao se o probe 42
    (read-only) mencionar um mutador, ou se o probe 43 tiver mais de uma
    chamada de `add` sobre a colecao de POUs. A distincao fina -- `pous.add`
    contra `.add` de colecao Python -- e feita por RECEPTOR na analise de AST
    dos testes, porque `ScriptPouObjectCollection` HERDA de `list` e proibir o
    NOME `add` nao separaria as duas coisas.

    O BUILD NAO ESTA AQUI, E ISSO E DE PROPOSITO. Vincular nao basta: o
    criterio do marco e reabrir, o vinculo persistir e o build continuar verde.
    A persistencia este host prova (postsave). O BUILD e ETAPA PROPRIA, com
    instrumento proprio ja existente -- `probes/40_build_w1_4.py`, alcancado
    por `run_w1_4_integrated.ps1 -ExecuteBuild`. Compilar aqui misturaria "o
    vinculo persistiu" com "o projeto compila", que sao provas de naturezas
    diferentes e admitem decisao humana entre elas.

    A COPIA E FEITA POR ESTE SCRIPT, SEMPRE. O parametro e -BaseProject (ou o
    base_path do plano), nunca um caminho de copia ja pronta, e uma copia
    pre-existente e RECUSADA. Aceitar copia pronta transformaria "nao tocar o
    original" num passo manual, e passo manual dentro de um procedimento que se
    define por nao tocar o original e exatamente onde o erro entra -- foi o que
    falhou em W1.5. O sha256 e conferido no original e na copia ANTES e nos
    DOIS depois.

    O caminho do projeto-base do cliente tem ESPACO, e `--scriptargs` quebra o
    valor em espaco em branco (achado do probe 15). Por isso a COPIA e a saida
    vao sempre para caminhos sem espaco -- so o base_path pode te-lo.

    FECHAMENTO DE JANELA: os dois probes chamam `system.exit(0)` DEPOIS de
    gravar os artefatos. `CloseMainWindow()` nao basta nesta familia de sessao:
    o MasterTool marca o projeto como alterado so de abrir, e o pedido de
    fechar cai num dialogo modal de salvar (medido em W1.5 e na run-019). Com
    -AutoCloseWindow o host ainda tenta CloseMainWindow() como ultimo recurso,
    e NUNCA Stop-Process: matar processo poderia interromper a gravacao do
    artefato e viola docs/28 secao 7.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso -- a conclusao vem SEMPRE do artefato.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [string]$BaseProject = '',

    [switch]$ValidateOnly,
    [switch]$ReconOnly,
    [switch]$ExecuteMutation,

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
        $path, ($data | ConvertTo-Json -Depth 12),
        (New-Object System.Text.UTF8Encoding($false)))
}

$selectedModes = @()
if ($ValidateOnly)    { $selectedModes += 'ValidateOnly' }
if ($ReconOnly)       { $selectedModes += 'ReconOnly' }
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
$ExpectedPhase = 'W2_BIND_PROGRAM_CALL'

Write-Section "W2 -- Task Configuration e Program Call -- modo '$Mode'"

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

if ($planData.schema_version -ne '1.0') { Fail 'schema_version inesperado' }
if ($planData.phase -ne $ExpectedPhase) { Fail "phase inesperada: $($planData.phase)" }
if ($planData.operation_id -ne 'w2-bind-program-call') { Fail 'operation_id inesperado' }
if ([string]::IsNullOrWhiteSpace($planData.task_name)) { Fail 'task_name vazio no plano' }
if ([string]::IsNullOrWhiteSpace($planData.program_name)) { Fail 'program_name vazio no plano' }

$kinds = @($planData.operations | ForEach-Object { $_.kind })
if ($kinds.Count -ne 2 -or $kinds[0] -ne 'add' -or $kinds[1] -ne 'save_as') {
    Fail ("Plano deve declarar exatamente add, save_as -- recebido: " +
          ($kinds -join ', '))
}
if ($planData.operations[0].target -ne 'task_pou_collection') {
    Fail ("A operacao 'add' deve visar task_pou_collection -- recebido: " +
          "$($planData.operations[0].target). O nome 'add' colide com o metodo " +
          "homonimo de list, e o alvo declarado e o que impede que um plano " +
          "autorize 'um add qualquer'.")
}
Write-Host "[OK] Operacoes   : $($kinds -join ', ')"
Write-Host "[OK] Vinculo     : PROGRAM '$($planData.program_name)' -> task '$($planData.task_name)'"

$planBase  = $planData.input_project.base_path
$copyPath  = $planData.input_project.path
$outputPath = $planData.output_project.path
$artifacts = $planData.artifacts_dir
$sessionDir = Split-Path -Parent $copyPath

if ([string]::IsNullOrWhiteSpace($BaseProject)) { $BaseProject = $planBase }
elseif ([IO.Path]::GetFullPath($BaseProject) -ne [IO.Path]::GetFullPath($planBase)) {
    Fail ("-BaseProject ($BaseProject) diverge do input_project.base_path do " +
          "plano ($planBase). Duas fontes para a mesma entrada seriam duas " +
          "verdades.")
}

foreach ($par in @(@{n='base_path';v=$BaseProject}, @{n='input path';v=$copyPath},
                   @{n='output path';v=$outputPath}, @{n='artifacts_dir';v=$artifacts})) {
    if ([string]::IsNullOrWhiteSpace($par.v)) { Fail "$($par.n) vazio" }
    if (-not [IO.Path]::IsPathRooted($par.v)) { Fail "$($par.n) deve ser absoluto" }
}
# So a COPIA, a saida e os artefatos entram em --scriptargs; o projeto do
# cliente mora num caminho com espaco e nao herda a proibicao.
foreach ($par in @(@{n='input path';v=$copyPath}, @{n='output path';v=$outputPath},
                   @{n='artifacts_dir';v=$artifacts})) {
    if ($par.v -match '\s') { Fail "$($par.n) contem espaco: $($par.v)" }
}
if ([IO.Path]::GetFullPath($copyPath) -eq [IO.Path]::GetFullPath($outputPath)) {
    Fail 'entrada e saida sao o mesmo arquivo'
}
$repoFull = [IO.Path]::GetFullPath($RepoRoot)
foreach ($p in @($outputPath, $artifacts, $sessionDir)) {
    if ([IO.Path]::GetFullPath($p).StartsWith($repoFull, [StringComparison]::OrdinalIgnoreCase)) {
        Fail "caminho dentro do repositorio: $p"
    }
}

if (-not (Test-Path -LiteralPath $BaseProject)) { Fail "Projeto-base inexistente: $BaseProject" }
$baseSha = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $BaseProject"
Write-Host "[OK] SHA256 base : $baseSha"
if ($planData.input_project.sha256 -ne $baseSha) {
    Fail 'SHA-256 do projeto-base diverge do plano'
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
# A mensagem tem de dizer o que E, nao o que se esperava: imprimir "nenhuma
# instancia" logo depois de -AllowRunningInstance ter deixado passar uma seria
# um [OK] mentindo, e um log que mente e pior que um log ausente.
if ($running.Count -gt 0) {
    Write-Host ("[AVISO] $($running.Count) instancia(s) aberta(s) e " +
                "-AllowRunningInstance foi informado: " +
                (($running | ForEach-Object { $_.Id }) -join ', ')) -ForegroundColor Yellow
}
else {
    Write-Host '[OK] Nenhuma instancia do MasterTool X aberta.'
}

$safetyFile = Join-Path $RepoRoot 'scripts\mastertool\common\safety.py'
if (-not (Select-String -LiteralPath $safetyFile -Pattern '^READ_ONLY_PHASE\s*=\s*True' -Quiet)) {
    Fail 'READ_ONLY_PHASE deixou de ser True'
}
Write-Host '[OK] READ_ONLY_PHASE = True'

$probe42 = Join-Path $RepoRoot 'scripts\mastertool\probes\42_recon_tasks_readonly.py'
$probe43 = Join-Path $RepoRoot 'scripts\mastertool\probes\43_bind_program_to_task.py'
if (-not (Test-Path -LiteralPath $probe42)) { Fail "Probe 42 nao encontrado: $probe42" }
if (-not (Test-Path -LiteralPath $probe43)) { Fail "Probe 43 nao encontrado: $probe43" }

# --- guarda de fonte do probe 42 (read-only) ---------------------------------
#
# Os mutadores da colecao de POUs moram no MESMO objeto que a leitura e a
# colecao HERDA de list. Esta guarda le o FONTE antes de abrir o produto: se um
# desses nomes aparecer no probe read-only, a sessao nem comeca.
#
# `sys.path.insert(0, ...)` existe em TODO probe deste repositorio e nao tem
# nada a ver com a colecao de POUs: o RECEPTOR e que decide. Por isso o padrao
# de `insert` traz um lookbehind que dispensa exatamente esse receptor -- a
# separacao fina por receptor e feita na analise de AST dos testes.
$probe42Source = Get-Content -LiteralPath $probe42 -Raw
foreach ($mutadorDeTask in @('create_task', 'create_boot_application',
                             '\.add\s*\(', '(?<!sys\.path)\.insert\s*\(',
                             '\.remove\s*\(', '\.replace\s*\(', '\.save\s*\(',
                             '\.save_as\s*\(', '\.build\s*\(', '\.rebuild\s*\(',
                             'import_xml')) {
    if ($probe42Source -match $mutadorDeTask) {
        Fail ("Probe 42 e SOMENTE LEITURA e casa com '$mutadorDeTask'. " +
              "Sessao recusada.")
    }
}
Write-Host "[OK] Probe 42    : $probe42 (sem mutador no fonte)"

# --- guarda de fonte do probe 43 (as DUAS mutacoes, e so elas) ---------------
$probe43Source = Get-Content -LiteralPath $probe43 -Raw
$addCalls = ([regex]::Matches($probe43Source, '\.add\s*\(')).Count
if ($addCalls -ne 1) {
    Fail ("Probe 43 tem $addCalls chamada(s) de .add( no fonte; o marco " +
          "autoriza EXATAMENTE UMA. Sessao recusada.")
}
$saveAsCalls = ([regex]::Matches($probe43Source, '\.save_as\s*\(')).Count
if ($saveAsCalls -ne 1) {
    Fail ("Probe 43 tem $saveAsCalls chamada(s) de .save_as( no fonte; o marco " +
          "autoriza EXATAMENTE UMA. Sessao recusada.")
}
foreach ($proibido in @('create_task\s*\(', '(?<!sys\.path)\.insert\s*\(',
                        '\.remove\s*\(', '\.replace\s*\(', '\.build\s*\(',
                        '\.rebuild\s*\(', '\.clean\s*\(', 'import_xml\s*\(',
                        '\.rename\s*\(', '\.save\s*\(')) {
    if ($probe43Source -match $proibido) {
        Fail "Probe 43 contem chamada proibida (padrao '$proibido'). Sessao recusada."
    }
}
Write-Host "[OK] Probe 43    : $probe43 (uma chamada de add, uma de save_as)"

# --- a fase de escrita controlada --------------------------------------------
#
# FAIL-CLOSED, e com a razao dita por extenso: abrir a fase e commit ISOLADO e
# humano (docs/28 secao 14). Enquanto ela nao estiver autorizada, o modo de
# mutacao nem lanca o produto -- e mesmo que lancasse, a porta unica de
# safety.py recusaria as duas operacoes.
$phaseAutorizada = (Select-String -LiteralPath $safetyFile `
    -Pattern ('^CONTROLLED_WRITE_PHASE\s*=\s*.' + $ExpectedPhase + '.') -Quiet)
$allowlistPresente = (Select-String -LiteralPath $safetyFile `
    -Pattern ($ExpectedPhase + '.\s*:\s*frozenset') -Quiet)
if ($Mode -eq 'ExecuteMutation') {
    if (-not $phaseAutorizada -or -not $allowlistPresente) {
        Fail ("Fase $ExpectedPhase NAO autorizada em safety.py " +
              "(CONTROLLED_WRITE_PHASE e/ou allowlist ausentes). Nenhuma " +
              "mutacao e tentada: abrir a fase e decisao humana em commit " +
              "isolado (docs/28 secao 14). Ate la, use -ReconOnly.")
    }
}
Write-Host "[INFO] fase $ExpectedPhase autorizada em safety.py: $phaseAutorizada"

Write-Section 'VALIDACAO APROVADA'
if ($Mode -eq 'ValidateOnly') {
    Write-Host 'Nada foi aberto, nenhuma copia criada, nada compilado.'
    Write-Host 'O build NAO pertence a este host: e etapa propria, pelo probe 40.'
    exit 0
}

# =============================================================================
# BLOCO 1.5 -- INSTRUCAO AO OPERADOR, ANTES DE QUALQUER LANCAMENTO
# =============================================================================
#
# Este bloco existe separado de proposito. Aviso que aparece junto com o evento
# nao e aviso: quando o dialogo abrir, o operador ja precisa saber o que fazer,
# e nao estar lendo pela primeira vez enquanto a janela pisca. Por isso ele vem
# ANTES da copia e ANTES do Start-Process, e nao dentro da funcao que lanca.
Write-Section 'LEIA AGORA -- O QUE FAZER SE APARECER O DIALOGO DE SALVAR'
Write-Host 'Os probes encerram o MasterTool por system.exit(0) depois de' -ForegroundColor Yellow
Write-Host 'gravar os artefatos, e nesse caminho o dialogo nao aparece. Se' -ForegroundColor Yellow
Write-Host 'ainda assim ele aparecer:' -ForegroundColor Yellow
Write-Host ''
Write-Host '    "O projeto atual foi alterado. Deseja salvar as alteracoes?"' -ForegroundColor Yellow
Write-Host ''
Write-Host 'CLIQUE "NAO".' -ForegroundColor Yellow
Write-Host ''
Write-Host 'Isso NAO quer dizer que o probe escreveu onde nao devia. Medido em' -ForegroundColor Yellow
Write-Host 'W1.5: o MasterTool marca o projeto como alterado so de abrir.' -ForegroundColor Yellow
Write-Host ''
Write-Host '  "SIM"      gravaria por cima da COPIA DE ENTRADA, destruindo a' -ForegroundColor Yellow
Write-Host '             testemunha do estado inicial. A sessao seria' -ForegroundColor Yellow
Write-Host '             reprovada por divergencia de hash.' -ForegroundColor Yellow
Write-Host '  "CANCELAR" mantem a janela aberta e a sessao trava ate o timeout.' -ForegroundColor Yellow
Write-Host ''
Write-Host 'Diante de QUALQUER OUTRO dialogo: CANCELE e registre o texto exato.' -ForegroundColor Yellow

# =============================================================================
# BLOCO 2 -- EXECUCAO
# =============================================================================

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
    Write-Host '[LEMBRETE] UI VISIVEL. Vale a instrucao impressa antes do lancamento:' -ForegroundColor Yellow
    Write-Host '           dialogo de salvar alteracoes -> "NAO"; qualquer outro -> CANCELE.' -ForegroundColor Yellow

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
        # Ultimo recurso: o probe ja pediu system.exit(0). CloseMainWindow = o
        # mesmo que clicar no X. NUNCA matar o processo.
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

# --- a copia descartavel, criada AQUI e nunca reaproveitada ------------------
if (Test-Path -LiteralPath $outputPath) { Fail "output ja existe: $outputPath" }
if (Test-Path -LiteralPath $sessionDir) {
    $ocupado = @(Get-ChildItem -LiteralPath $sessionDir -File -ErrorAction SilentlyContinue)
    if ($ocupado.Count -gt 0) { Fail "Diretorio da copia nao esta isolado/vazio: $sessionDir" }
}
New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
if (Test-Path -LiteralPath $copyPath) {
    Fail ("Ja existe arquivo em $copyPath. Este host CRIA a copia a partir de " +
          "-BaseProject e nunca reaproveita copia pre-existente. Use um " +
          "diretorio de sessao limpo.")
}
Copy-Item -LiteralPath $BaseProject -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

# --- recon: probe 42, somente leitura, sobre a copia -------------------------
$reconDir = Join-Path $artifacts 'recon'
$reconCompletion = Join-Path $reconDir 'tasks-completion.json'
$obsRecon = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe42 `
    -ScriptArgs ("--mode=recon --output=" + $reconDir) -StageDir $reconDir `
    -Label 'RECON de tasks (probe 42, somente leitura)' `
    -CompletionPath $reconCompletion

$recon = Read-Completion $reconCompletion
if ($null -eq $recon) {
    Fail 'tasks-completion.json ausente. Sem veredito -- trate como falha de artefato.'
}
Write-Host "[INFO] status do recon: $($recon.status)"
Write-Host "[INFO] tasks medidas  : $($recon.tasks_count)"

$copyShaAfterRecon = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfterRecon -ne $copySha) {
    Fail ('A copia MUDOU durante o recon read-only. A causa mais provavel nao ' +
          'e o probe: e alguem ter respondido "SIM" ao dialogo de salvar. A ' +
          'sessao e reprovada de qualquer forma -- uma copia alterada nao ' +
          'prova leitura.')
}
$baseShaAfterRecon = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
if ($baseShaAfterRecon -ne $baseSha) { Fail 'O PROJETO-BASE ORIGINAL foi tocado. Investigar imediatamente.' }
if ($obsRecon.orphan_ids.Count -gt 0) { Fail "Orfaos apos o recon: $($obsRecon.orphan_ids -join ', ')" }
Write-Host '[OK] Copia intacta apos o recon (somente leitura confirmada por hash).'

$reconMedido = ($recon.status -eq 'measured' -and $recon.tasks_count -gt 0)

if ($Mode -eq 'ReconOnly') {
    $reconReport = [ordered]@{
        verdict = $(if ($reconMedido) { 'TASKS MEDIDAS: ' + $recon.tasks_count }
                    else { 'SESSAO CONCLUIDA SEM MEDIDA -- lacuna permanece' })
        mode = $Mode
        recon_status = $recon.status
        tasks_count = $recon.tasks_count
        task_summaries = $recon.task_summaries
        task_configuration_nodes = $recon.task_configuration_nodes
        marker_chain_task = $recon.marker_chain_task
        marker_chain_task_configuration = $recon.marker_chain_task_configuration
        pous_chain = $recon.pous_chain
        chain_steps = $recon.chain_steps
        plan = $Plan; plan_sha256 = $planSha
        base_project = $BaseProject; base_sha256 = $baseSha
        working_copy = $copyPath; working_copy_sha256_before = $copySha
        working_copy_sha256_after = $copyShaAfterRecon
        mutation_pending = $true
        executions = @($obsRecon)
    }
    Write-JsonNoBom (Join-Path $artifacts 'session-verdict-recon.json') $reconReport
    Write-Section "RECON CONCLUIDO -- NENHUMA MUTACAO OCORREU"
    Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict-recon.json')"
    if (-not $reconMedido) {
        Write-Host '[BLOQUEIO] A sessao rodou e as tasks NAO foram medidas.' -ForegroundColor Yellow
        exit 4
    }
    exit 0
}

# =============================================================================
# BLOCO 3 -- MUTACAO (somente -ExecuteMutation)
#
# Duas mutacoes, e so duas: add e save_as. NENHUM build aqui -- o build e etapa
# propria, pelo probe 40 (run_w1_4_integrated.ps1 -ExecuteBuild).
# =============================================================================

if (-not $reconMedido) {
    Fail ("O recon nao mediu as tasks ($($recon.status)). Vincular sem saber o " +
          "estado inicial nao e mutacao controlada.")
}

$planShaFrozen = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
if ($planShaFrozen -ne $planSha) { Fail 'O plano mudou durante a sessao.' }

$bindDir = Join-Path $artifacts 'bind'
$bindCompletion = Join-Path $bindDir 'bind-completion.json'
$obsBind = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe43 `
    -ScriptArgs ("--plan=" + $Plan) -StageDir $bindDir `
    -Label 'MUTACAO -- Program Call (probe 43: add + save_as)' `
    -CompletionPath $bindCompletion

$bind = Read-Completion $bindCompletion
if ($null -eq $bind) {
    Fail 'bind-completion.json ausente. A copia esta em estado DESCONHECIDO: descarte-a.'
}
Write-Host "[INFO] status do probe 43: $($bind.status)"
if ($bind.status -ne 'saved_as') {
    Fail ("Mutacao nao terminou em saved_as: $($bind.status). $($bind.errors -join ' | ') " +
          "DESCARTE a copia inteira -- nao existe rollback.")
}
$copyShaAfterBind = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfterBind -ne $copySha) { Fail 'A copia de ENTRADA foi modificada. Descarte tudo.' }
if (-not (Test-Path -LiteralPath $outputPath)) { Fail 'save_as declarou sucesso sem criar o arquivo.' }
$outputSha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
if ($obsBind.orphan_ids.Count -gt 0) { Fail "Orfaos apos a mutacao: $($obsBind.orphan_ids -join ', ')" }
Write-Host "[OK] Saida       : $outputPath"
Write-Host "[OK] SHA256 saida: $outputSha"

# --- postsave: abertura SEPARADA sobre a SAIDA -------------------------------
#
# Vincular em memoria nao prova nada. O criterio do marco e que o vinculo
# PERSISTA: por isso o probe 42 volta a rodar, agora sobre o arquivo salvo, em
# processo novo, e conferindo o par (task, PROGRAM) declarado no plano.
$postsaveDir = Join-Path $artifacts 'postsave'
$postsaveCompletion = Join-Path $postsaveDir 'tasks-completion.json'
$obsPost = Invoke-MasterTool -ProjectPath $outputPath -ProbePath $probe42 `
    -ScriptArgs ("--mode=postsave --output=" + $postsaveDir +
                 " --expect-task=" + $planData.task_name +
                 " --expect-pou=" + $planData.program_name) `
    -StageDir $postsaveDir -Label 'POSTSAVE (probe 42, abertura separada sobre a saida)' `
    -CompletionPath $postsaveCompletion

$postsave = Read-Completion $postsaveCompletion
if ($null -eq $postsave) { Fail 'tasks-completion.json do postsave ausente. Sem prova de persistencia.' }
Write-Host "[INFO] status do postsave: $($postsave.status)"
$outputShaAfterPostsave = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLower()
if ($outputShaAfterPostsave -ne $outputSha) {
    Fail 'A SAIDA MUDOU durante o postsave read-only. Nenhum save foi pedido.'
}
if ($obsPost.orphan_ids.Count -gt 0) { Fail "Orfaos apos o postsave: $($obsPost.orphan_ids -join ', ')" }

$bindPersisted = ($postsave.status -eq 'binding_verified' -and $postsave.binding_verified -eq $true)
$verdict = 'REPROVADO'
if ($bindPersisted) { $verdict = 'program_call_persisted' }

$sessionReport = [ordered]@{
    verdict = $verdict
    mode = $Mode
    plan = $Plan; plan_sha256 = $planSha
    base_project = $BaseProject; base_sha256 = $baseSha
    working_copy = $copyPath; working_copy_sha256_before = $copySha
    working_copy_sha256_after = $copyShaAfterBind
    output_project = $outputPath; output_sha256 = $outputSha
    output_sha256_after_postsave = $outputShaAfterPostsave
    recon_status = $recon.status
    recon_task_summaries = $recon.task_summaries
    bind_status = $bind.status
    task_name = $bind.task_name; program_name = $bind.program_name
    pous_before = $bind.pous_before; pous_after = $bind.pous_after
    operations_executed = $bind.operations_executed
    no_other_mutator_requested = $bind.no_other_mutator_requested
    postsave_status = $postsave.status
    binding = $postsave.binding
    binding_persisted = $bindPersisted
    build_pending = $true
    executions = @($obsRecon, $obsBind, $obsPost)
}
Write-JsonNoBom (Join-Path $artifacts 'session-verdict.json') $sessionReport

Write-Section "VEREDITO W2 -- PROGRAM CALL: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"
Write-Host ''
Write-Host 'O BUILD AINDA NAO FOI EXECUTADO, e nao pertence a este host.'
Write-Host 'Vincular nao basta: o criterio do marco exige que o projeto ainda'
Write-Host 'compile. Isso e ETAPA PROPRIA, com instrumento proprio ja existente'
Write-Host '-- probes/40_build_w1_4.py, alcancado por'
Write-Host '   run_w1_4_integrated.ps1 -ExecuteBuild'
Write-Host 'sobre a saida acima. Ate que ele rode e saia build_verified, o'
Write-Host 'vinculo esta PERSISTIDO e NAO VALIDADO por compilacao.'
if (-not $bindPersisted) {
    Write-Host '[BLOQUEIO] O vinculo NAO foi confirmado apos a reabertura.' -ForegroundColor Yellow
    exit 3
}
exit 0
