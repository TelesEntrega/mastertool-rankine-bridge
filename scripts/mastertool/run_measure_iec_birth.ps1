<#
.SYNOPSIS
    Host supervisionado de W1.5 -- MEDIR o texto de nascimento de
    FUNCTION_BLOCK e FUNCTION numa copia descartavel. Nunca persiste.

.DESCRIPTION
    FAIL-CLOSED. Dois modos MUTUAMENTE EXCLUSIVOS; o default nao abre nada:

        (default)   so valida o plano. Nao abre o MasterTool.
        -Execute    abre o MasterTool e roda o probe 39 (create_function_block +
                    create_function, cada um com guarda propria). NUNCA chama
                    save/save_as/build -- a copia inteira fica em memoria e e
                    descartada fechando a janela SEM SALVAR.

    O probe 39 e alcancavel APENAS pelo ramo -Execute.

    HOJE (2026-07-31) a fase W1_5_MEASURE_IEC_BIRTH NAO ESTA ABERTA em
    safety.py -- abrir a fase e decisao humana, em commit isolado, fora deste
    slice. Rodar -Execute agora e ESPERADO terminar em status "gate_closed":
    o probe tenta as duas chamadas, a guarda as recusa, e nada e criado. Isso
    e o comportamento CORRETO, nao uma falha do host.

    FECHAMENTO DE JANELA: com -AutoCloseWindow, o host fecha a janela por
    CloseMainWindow() -- o equivalente a clicar no X -- depois que o artefato
    de conclusao aparece. NUNCA Stop-Process: matar processo violaria
    docs/28 secao 7 e poderia interromper gravacao de artefato. Se a janela
    nao fechar (tipicamente porque ha um dialogo aberto), o host REPORTA e
    nao insiste.

    ======================================================================
    O DIALOGO DE SALVAR VAI APARECER. A RESPOSTA E "NAO".
    ======================================================================
    Esta fase CRIA objetos e NUNCA salva. Logo, ao fechar, o MasterTool
    pergunta "O projeto atual foi alterado. Deseja salvar as alteracoes?".
    Isso NAO e um dialogo inesperado -- e a consequencia projetada da fase, e
    a unica resposta correta e NAO:

        NAO       descarta as alteracoes. E o que o desenho exige.
        Cancelar  mantem a janela aberta e nao resolve nada.
        SIM       persiste uma criacao que ninguem autorizou a existir --
                  `save_as` esta FORA da allowlist da fase por esse motivo.

    Aprendido na run-013, em que o SIM foi clicado: a copia descartavel foi
    persistida. O dano ficou contido nela -- base sintetica e projeto do
    cliente intactos --, mas a run foi invalidada como registro, porque
    congelar constante canonica a partir de execucao que desviou do desenho
    e o mesmo atalho que este repositorio recusa em todo lugar.

    A licao de host, e nao de operador: o aviso ANTIGO era impresso junto com
    o lancamento, no meio de vinte linhas, quando a janela ja abria. Aviso que
    chega junto com o evento nao e aviso. Agora ele aparece ANTES, sozinho, e
    exige confirmacao explicita por `-ConfirmoQueVouFecharSemSalvar`.

    A COPIA DESCARTAVEL E CRIADA POR ESTE HOST, a partir de `-BaseProject`.
    Antes ela vinha pronta no plano, e criar copia a mao dentro de um
    procedimento que se define por "nunca persistir" e exatamente onde o erro
    entra -- foi o que aconteceu na run-013. Os outros quatro wrappers de W1
    ja criavam a propria copia; este era o unico que nao criava.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso. Conclusao SEMPRE pelo artefato
    (completion.json), nunca pelo exit code do processo do MasterTool.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [switch]$Execute,

    # Obrigatorio junto com -Execute. Existe para que a instrucao "feche sem
    # salvar" seja LIDA antes do lancamento, e nao descoberta no meio dele.
    [switch]$ConfirmoQueVouFecharSemSalvar,

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

$Mode = 'ValidateOnly'
if ($Execute) { $Mode = 'Execute' }

$ProcessPattern = [IO.Path]::GetFileNameWithoutExtension($Exe) + '*'

Write-Section "W1.5 -- medir nascimento de FUNCTION_BLOCK/FUNCTION -- modo '$Mode'"

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
if ($planData.phase -ne 'W1_5_MEASURE_IEC_BIRTH') { Fail "phase inesperada: $($planData.phase)" }
if ($planData.function_block_name -ne 'FB_AI_MEASURE_W1_5') { Fail "function_block_name inesperado" }
if ($planData.function_name -ne 'F_AI_MEASURE_W1_5') { Fail "function_name inesperado" }

$kinds = @($planData.operations | ForEach-Object { $_.kind })
if ($kinds.Count -ne 2 -or $kinds[0] -ne 'create_function_block' -or $kinds[1] -ne 'create_function') {
    Fail ("Plano deve declarar exatamente create_function_block, create_function -- recebido: " +
          ($kinds -join ', '))
}
Write-Host "[OK] Operacoes   : $($kinds -join ', ')"

$languageGuid = $planData.language_guid
if ([string]::IsNullOrWhiteSpace($languageGuid) -or $languageGuid.Length -ne 36) {
    Fail "language_guid ausente ou sem forma de GUID: '$languageGuid'"
}
Write-Host "[OK] GUID linguagem: $languageGuid"

$returnType = $planData.function_return_type
if ([string]::IsNullOrWhiteSpace($returnType)) {
    Fail "function_return_type ausente"
}
Write-Host "[OK] return_type : $returnType"

$copyPath   = $planData.input_project.path
$artifacts  = $planData.artifacts_dir
$basePath   = $planData.input_project.base_path
if ([string]::IsNullOrWhiteSpace($basePath)) { $basePath = $copyPath }
$sessionDir = Split-Path -Parent $copyPath

foreach ($par in @(@{n='input path';v=$copyPath}, @{n='artifacts_dir';v=$artifacts})) {
    if ([string]::IsNullOrWhiteSpace($par.v)) { Fail "$($par.n) vazio" }
    if (-not [IO.Path]::IsPathRooted($par.v)) { Fail "$($par.n) deve ser absoluto" }
    if ($par.v -match '\s') { Fail "$($par.n) contem espaco: $($par.v)" }
}
$repoFull = [IO.Path]::GetFullPath($RepoRoot)
if ([IO.Path]::GetFullPath($artifacts).StartsWith($repoFull, [StringComparison]::OrdinalIgnoreCase)) {
    Fail "artifacts_dir dentro do repositorio: $artifacts"
}
if ([string]::IsNullOrWhiteSpace($basePath)) { Fail 'input_project.base_path obrigatorio: o host cria a copia, e precisa saber de onde' }
if (-not (Test-Path -LiteralPath $basePath)) { Fail "Projeto-base inexistente: $basePath" }
if ([IO.Path]::GetFullPath($basePath) -eq [IO.Path]::GetFullPath($copyPath)) {
    Fail 'base e copia sao o mesmo arquivo: a copia descartavel deixaria de ser descartavel'
}

# VALIDACAO SO OLHA. A copia e criada no BLOCO 2, depois da saida do modo
# ValidateOnly -- se ela fosse criada aqui, o modo que promete "nada foi
# tocado" estaria criando arquivo, e a promessa seria falsa. Defeito que eu
# mesmo introduzi ao corrigir a run-013, e que o proprio ValidateOnly pegou.
$sessionDirCopia = Split-Path -Parent $copyPath
if (Test-Path -LiteralPath $copyPath) {
    Fail ("A copia ja existe: $copyPath. Este host cria a copia; arquivo " +
          "pre-existente pode ser sobra de run anterior -- inclusive de uma " +
          "que salvou, como a run-013. Use diretorio novo.")
}
$baseSha = (Get-FileHash -LiteralPath $basePath -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $basePath"
Write-Host "[OK] SHA256 base : $baseSha"
if ($planData.input_project.sha256 -ne $baseSha) {
    Fail 'SHA-256 do projeto-base diverge do plano'
}
Write-Host "[OK] Copia a criar: $copyPath (ainda nao existe -- correto)"

if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel nao encontrado: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
if ($exeVersion -ne $ExpectedExeVersion) {
    Fail ("FileVersion inesperada: '$exeVersion'. Sem fallback para outra versao " +
          "do MasterTool.")
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
    Write-Host 'Nada foi aberto, nenhuma copia tocada.'
    Write-Host 'Lembrete: a fase W1_5_MEASURE_IEC_BIRTH ainda nao esta aberta em safety.py.'
    exit 0
}

# =============================================================================
# BLOCO 2 -- EXECUCAO (somente -Execute)
# =============================================================================

$probe39 = Join-Path $RepoRoot 'scripts\mastertool\probes\39_measure_iec_birth.py'
if (-not (Test-Path -LiteralPath $probe39)) { Fail "Probe 39 nao encontrado" }

# A COPIA E CRIADA AQUI, no ramo -Execute, e nao na validacao: o modo que
# promete "nada foi tocado" nao pode criar arquivo.
New-Item -ItemType Directory -Force -Path $sessionDirCopia | Out-Null
Copy-Item -LiteralPath $basePath -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base' }
Write-Host "[OK] Copia criada: $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

# =============================================================================
# AVISO ANTES DO LANCAMENTO, e nao junto com ele.
#
# Na run-013 o lembrete saia no meio do bloco de lancamento, quando a janela ja
# estava abrindo -- e o operador clicou SIM no dialogo de salvar. Aviso que
# chega junto com o evento nao e aviso. Agora ele para o fluxo, aparece
# sozinho, e exige uma confirmacao explicita que so pode ser dada por quem
# leu.
# =============================================================================
Write-Section 'ATENCAO -- LEIA ANTES DE A JANELA ABRIR'
Write-Host ''
Write-Host '  Esta fase CRIA objetos e NUNCA salva.' -ForegroundColor Yellow
Write-Host '  Ao fechar, o MasterTool vai perguntar:' -ForegroundColor Yellow
Write-Host ''
Write-Host '      "O projeto atual foi alterado. Deseja salvar as alteracoes?"' -ForegroundColor Yellow
Write-Host ''
Write-Host '  A RESPOSTA E:  NAO' -ForegroundColor Red
Write-Host ''
Write-Host '  NAO       descarta. E o que o desenho exige.'
Write-Host '  Cancelar  mantem a janela aberta e nao resolve nada.'
Write-Host '  SIM       persiste uma criacao que ninguem autorizou a existir.'
Write-Host ''
Write-Host '  Este dialogo NAO e inesperado: e a consequencia projetada de'
Write-Host '  criar sem persistir. `save_as` esta fora da allowlist da fase.'
Write-Host ''
if (-not $ConfirmoQueVouFecharSemSalvar) {
    Fail ('Faltou -ConfirmoQueVouFecharSemSalvar. Releia o bloco acima e ' +
          'passe o parametro. Ele existe para que a instrucao seja lida ' +
          'ANTES do lancamento, nao descoberta no meio dele.')
}
Write-Host '[OK] Operador confirmou que vai fechar SEM SALVAR.'

$planShaFrozen = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLower()
if ($planShaFrozen -ne $planSha) { Fail 'O plano mudou durante a sessao.' }

New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

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
    Write-Host '[LEMBRETE] Este probe NUNCA salva. Ao final, FECHE A JANELA SEM SALVAR.' -ForegroundColor Yellow

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
        # Fechar SEM salvar e exatamente o que descarta a copia deste probe.
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
        Write-Host '          Este host NAO mata processo. Verifique a tela e feche SEM SALVAR.' -ForegroundColor Yellow
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

$measureCompletion = Join-Path $artifacts 'completion.json'
$obs = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe39 `
    -ScriptArgs ("--plan=" + $Plan) -StageDir $artifacts -Label 'MEDICAO (probe 39)' `
    -CompletionPath $measureCompletion

$completion = Read-Completion $measureCompletion
if ($null -eq $completion) {
    Fail 'completion.json ausente. Estado DESCONHECIDO: feche a janela SEM SALVAR e investigue.'
}
Write-Host "[INFO] status do probe 39: $($completion.status)"

$inputShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($inputShaAfter -ne $copySha) {
    # DISTINGUIR AS DUAS CAUSAS, porque exigem acoes opostas: o probe escreveu
    # (defeito grave, o probe nao tem `save`/`save_as`), ou o operador clicou
    # SIM no dialogo (procedimento, nao codigo). O que decide e o journal: se
    # nao ha mutacao alem dos dois `create_*` guardados, o probe nao escreveu.
    Write-Host ''
    Write-Host '[BLOQUEADO] A COPIA MUDOU NO DISCO.' -ForegroundColor Red
    Write-Host '  Duas causas possiveis, e elas pedem acoes opostas:'
    Write-Host '   (a) o operador clicou SIM no dialogo de salvar  -> a MEDICAO'
    Write-Host '       vale, mas a run e invalida como registro: descarte a'
    Write-Host '       copia e refaca em diretorio novo.'
    Write-Host '   (b) o probe escreveu sozinho -> DEFEITO GRAVE: ele nao tem'
    Write-Host '       `save` nem `save_as`. Investigue o journal antes de'
    Write-Host '       qualquer outra execucao.'
    Write-Host '  O journal distingue: se ele so tem os dois `create_*`'
    Write-Host '  guardados e nenhuma outra mutacao, foi (a).'
    Fail 'copia alterada -- ver as duas causas acima'
}
Write-Host '[OK] O arquivo de entrada nao mudou no disco (nenhum save_as foi chamado, como esperado).'

if ($obs.orphan_ids.Count -gt 0) { Fail "Orfaos apos a sessao: $($obs.orphan_ids -join ', ')" }

$verdict = 'REPROVADO'
switch ($completion.status) {
    'measured'         { $verdict = 'MEDIDO' }
    'gate_closed'       { $verdict = 'FASE FECHADA (esperado hoje)' }
    'partial_measured'  { $verdict = 'MEDICAO PARCIAL' }
    default             { $verdict = 'REPROVADO' }
}

$sessionReport = [ordered]@{
    verdict = $verdict; plan = $Plan; plan_sha256 = $planSha
    language_guid = $languageGuid; function_return_type = $returnType
    input_project = $copyPath; input_sha256_before = $copySha
    input_sha256_after = $inputShaAfter
    probe_status = $completion.status
    function_block_declaration_sha256 = $completion.function_block_declaration_sha256
    function_block_implementation_sha256 = $completion.function_block_implementation_sha256
    function_declaration_sha256 = $completion.function_declaration_sha256
    function_implementation_sha256 = $completion.function_implementation_sha256
    dut_measured = $completion.dut_measured
    requires_copy_discard = $completion.requires_copy_discard
    lembrete = 'Feche o MasterTool SEM SALVAR. Nenhum arquivo novo foi criado por este probe.'
    executions = @($obs)
}
# `Out-File -Encoding utf8` grava BOM no PowerShell 5.1, e um leitor JSON
# estrito recusaria o proprio relatorio da sessao com "Unexpected UTF-8 BOM"
# (achado ja registrado na execucao real de W1.3A). UTF8Encoding($false) =
# UTF-8 sem BOM.
[System.IO.File]::WriteAllText(
    (Join-Path $artifacts 'session-verdict.json'),
    ($sessionReport | ConvertTo-Json -Depth 8),
    (New-Object System.Text.UTF8Encoding($false)))

Write-Section "VEREDITO DA SESSAO W1.5: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"
Write-Host 'LEMBRETE FINAL: feche o MasterTool SEM SALVAR. Este host nunca chamou save_as.' -ForegroundColor Yellow
if ($verdict -eq 'REPROVADO') { exit 3 }
exit 0
