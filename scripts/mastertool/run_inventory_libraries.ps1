<#
.SYNOPSIS
    Host supervisionado do probe 41 -- inventario SOMENTE LEITURA das
    bibliotecas do projeto, pelas duas cadeias literais do stub oficial:
    marcador `is_libman`, rota rica `references`, rota de conferencia
    `get_libraries(recursive=False)`.

.DESCRIPTION
    FAIL-CLOSED. Dois modos MUTUAMENTE EXCLUSIVOS; o default NAO ABRE NADA:

        -ValidateOnly  (DEFAULT) so valida parametros, executavel, hashes e a
                       ausencia de mutador no probe. Nao abre o MasterTool,
                       nao copia nada.
        -Execute       copia o projeto-base para um diretorio SEM ESPACO, abre
                       o MasterTool sobre a COPIA e roda o probe 41 (somente
                       leitura). Nenhuma escrita ocorre: este script nunca
                       pede create_*, replace, save, save_as nem build.

    POR QUE A GUARDA DE FONTE AQUI E MAIS DURA QUE A DO PROBE 36: os tres
    mutadores de biblioteca (add_library, add_placeholder, remove_library)
    moram no MESMO objeto e na MESMA interface que a leitura. Nao ha separacao
    de tipo protegendo ninguem. Alem deles, get_library_manager tambem e
    recusado: o stub oficial diz que ele obtem o gerenciador "implicitly
    creating one if none is existing yet" -- um acessor que CRIA nao entra em
    sessao read-only, por mais comodo que pareca. Se qualquer um desses nomes
    aparecer no fonte do probe, a sessao NAO COMECA.

    A COPIA E FEITA POR ESTE SCRIPT, SEMPRE. O parametro e -BaseProject, nunca
    um caminho de copia ja pronta. Aceitar copia pre-existente transformaria
    "nao tocar o original" num passo manual, e passo manual dentro de um
    procedimento que se define por nao tocar o original e exatamente onde o
    erro entra -- foi o que falhou em W1.5. O sha256 e conferido no original e
    na copia ANTES da execucao e conferido de novo nos DOIS depois.

    O caminho do projeto-base tem ESPACO, e `--scriptargs` quebra o valor em
    espaco em branco (achado do probe 15, reconfirmado no MasterTool X). Por
    isso a copia de trabalho vai SEMPRE para um diretorio proprio sem espaco.

    DIALOGO ESPERADO AO FECHAR -- LEIA ANTES DE LANCAR
    ==================================================
    Ao fechar, o MasterTool pode perguntar:

        "O projeto atual foi alterado. Deseja salvar as alteracoes?"

    O OPERADOR DEVE CLICAR "NAO".

    Isso NAO significa que o probe escreveu. Medido em W1.5: o MasterTool marca
    o projeto como alterado por conta propria, so de abrir -- ele materializa
    estado em memoria (caches, layout, resolucao de dispositivo) que nada tem a
    ver com o script. O probe 41 e read-only e nao tem uma linha de escrita; a
    prova disso nao e o dialogo, e o sha256 da copia conferido depois.

    Clicar "SIM" gravaria essa alteracao de memoria na COPIA, o hash divergiria
    e a sessao seria (corretamente) reprovada por este script -- perdendo a
    medicao inteira por um clique. "CANCELAR" apenas mantem a janela aberta e a
    sessao trava ate o timeout.

    FECHAMENTO DE JANELA: com -AutoCloseWindow o host chama CloseMainWindow()
    -- o equivalente a clicar no X -- depois que o artefato de conclusao
    aparece. E justamente esse X que dispara o dialogo acima, e o host NAO pode
    responde-lo por voce: automatizar o clique num dialogo de salvamento seria
    dar ao host o poder de gravar. Se a janela nao fechar, o host REPORTA e nao
    insiste. NUNCA Stop-Process: matar processo poderia interromper a gravacao
    do artefato e viola docs/28 secao 7.

    Nunca usa --noUI. Nunca aceita fallback de executavel. Nunca trata exit
    code do launcher como sucesso -- a conclusao vem SEMPRE do artefato
    libraries-completion.json gravado pelo probe 41.

    O veredito tem TRES camadas separadas: "a sessao rodou", "o inventario foi
    MEDIDO pela rota rica" e "as duas rotas CONFEREM". Uma sessao que roda
    inteira e nao mede nada nao e sucesso, e nao pode sair com 0; um inventario
    medido e nao conferido tambem nao pode.
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

Write-Section "Inventario read-only de bibliotecas -- modo '$Mode'"

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
# A mensagem tem de dizer o que E, nao o que se esperava. Imprimir "nenhuma
# instancia aberta" logo depois de -AllowRunningInstance ter deixado passar uma
# seria um [OK] mentindo, e um log que mente e pior que um log ausente.
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

$probe41 = Join-Path $RepoRoot 'scripts\mastertool\probes\41_inventory_libraries_readonly.py'
if (-not (Test-Path -LiteralPath $probe41)) { Fail "Probe 41 nao encontrado: $probe41" }

# Os mutadores de biblioteca vivem no MESMO objeto que a leitura. Esta guarda
# le o FONTE antes de abrir o produto: se um desses nomes aparecer -- em
# codigo, em comentario ou em docstring, de onde alguem poderia copiar por
# engano --, a sessao nem comeca.
$probeSource = Get-Content -LiteralPath $probe41 -Raw
foreach ($mutadorDeBiblioteca in @('add_library', 'add_placeholder', 'remove_library',
                                   'get_library_manager', 'install_library',
                                   'uninstall_library', 'set_redirection',
                                   'insert_repository', 'remove_repository',
                                   'update_repository', 'move_repository',
                                   'download_missing_libraries')) {
    if ($probeSource -match $mutadorDeBiblioteca) {
        Fail ("Probe 41 menciona '$mutadorDeBiblioteca', que altera bibliotecas " +
              "ou cria o gerenciador. Sessao recusada.")
    }
}
foreach ($proibido in @('\.save\s*\(', '\.save_as\s*\(', '\.build\s*\(',
                        '\.rebuild\s*\(', '\.import_xml\s*\(', 'create_pou\s*\(',
                        'create_gvl\s*\(', 'set_compilerversion')) {
    if ($probeSource -match $proibido) {
        Fail "Probe 41 contem chamada proibida (padrao '$proibido'). Sessao recusada."
    }
}
Write-Host "[OK] Probe 41    : $probe41 (sem mutador de biblioteca no fonte)"

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
# BLOCO 1.5 -- INSTRUCAO AO OPERADOR, ANTES DE QUALQUER LANCAMENTO
# =============================================================================
#
# Este bloco existe separado de proposito. Aviso que aparece junto com o evento
# nao e aviso: quando o dialogo abrir, o operador ja precisa saber o que fazer,
# e nao estar lendo pela primeira vez enquanto a janela pisca. Por isso ele vem
# ANTES da copia e ANTES do Start-Process, e nao dentro da funcao que lanca.
Write-Section 'LEIA AGORA -- O QUE FAZER QUANDO A JANELA FECHAR'
Write-Host 'Ao fechar, o MasterTool pode perguntar:' -ForegroundColor Yellow
Write-Host ''
Write-Host '    "O projeto atual foi alterado. Deseja salvar as alteracoes?"' -ForegroundColor Yellow
Write-Host ''
Write-Host 'CLIQUE "NAO".' -ForegroundColor Yellow
Write-Host ''
Write-Host 'Isso NAO quer dizer que o probe escreveu. Medido em W1.5: o' -ForegroundColor Yellow
Write-Host 'MasterTool marca o projeto como alterado so de abrir. O probe 41 e' -ForegroundColor Yellow
Write-Host 'read-only; a prova disso e o sha256 da copia conferido no fim, nao' -ForegroundColor Yellow
Write-Host 'a ausencia do dialogo.' -ForegroundColor Yellow
Write-Host ''
Write-Host '  "SIM"     gravaria a alteracao de memoria na COPIA, o hash' -ForegroundColor Yellow
Write-Host '            divergiria e esta sessao seria reprovada -- a medicao' -ForegroundColor Yellow
Write-Host '            inteira se perderia por um clique.' -ForegroundColor Yellow
Write-Host '  "CANCELAR" mantem a janela aberta e a sessao trava ate o timeout.' -ForegroundColor Yellow
Write-Host ''
Write-Host 'Diante de QUALQUER OUTRO dialogo: CANCELE e registre.' -ForegroundColor Yellow

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
        # CloseMainWindow = o mesmo que clicar no X. NUNCA matar o processo.
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
$copyPath = Join-Path $WorkDir 'TemplateExemplo_v1_libraries.project'
$artifacts = Join-Path $WorkDir 'artifacts'
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

# A copia e SEMPRE criada aqui, a partir de -BaseProject. Uma copia que ja
# existisse teria vindo de um passo manual, e um passo manual e o ponto onde
# "nao tocar o original" deixa de ser garantido pelo script -- foi assim que
# W1.5 falhou. Reaproveitar tambem esconderia mutacao de uma sessao anterior.
if (Test-Path -LiteralPath $copyPath) {
    Fail ("Ja existe arquivo em $copyPath. Este host CRIA a copia a partir de " +
          "-BaseProject e nunca reaproveita copia pre-existente. Use um WorkDir " +
          "limpo.")
}
Copy-Item -LiteralPath $BaseProject -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

$completionPath = Join-Path $artifacts 'libraries-completion.json'
$obs = Invoke-MasterTool -ProjectPath $copyPath -ProbePath $probe41 `
    -ScriptArgs ("--output=" + $artifacts) -Label 'inventario de bibliotecas (somente leitura)' `
    -CompletionPath $completionPath

$completion = Read-Completion $completionPath
if ($null -eq $completion) {
    Fail 'libraries-completion.json ausente. Sem veredito -- trate como falha de artefato.'
}
Write-Host "[INFO] status do probe 41: $($completion.status)"

$copyShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfter -ne $copySha) {
    Fail ('A copia MUDOU durante a leitura read-only. A causa mais provavel nao ' +
          'e o probe: e alguem ter respondido "SIM" ao dialogo "O projeto atual ' +
          'foi alterado. Deseja salvar as alteracoes?". A sessao e reprovada de ' +
          'qualquer forma -- uma copia alterada nao prova leitura.')
}
Write-Host '[OK] Copia intacta apos a execucao (somente leitura confirmada por hash).'

$baseShaAfter = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
if ($baseShaAfter -ne $baseSha) { Fail 'O PROJETO-BASE ORIGINAL foi tocado. Investigar imediatamente.' }
Write-Host '[OK] Projeto-base original intacto.'

if ($obs.orphan_ids.Count -gt 0) { Fail "Orfaos apos a execucao: $($obs.orphan_ids -join ', ')" }

# TRES VEREDITOS SEPARADOS.
#   sessionVerdict   -- a sessao rodou e gravou artefato?
#   librariesMeasured-- a rota rica devolveu inventario nao vazio?
#   routesAgree      -- a rota de conferencia concordou com ele?
# Colapsar isso numa palavra so foi o defeito corrigido na run-010 do wrapper
# de qualificacao; aqui ele ja nasce separado, e com uma camada a mais, porque
# aqui ha DUAS leituras independentes e elas podem discordar.
$librariesMeasured = $false
if ($completion.status -eq 'measured' -and $completion.libraries_count -gt 0) {
    $librariesMeasured = $true
}
$routesAgree = ($null -ne $completion.cross_check -and $completion.cross_check.agree -eq $true)

$sessionVerdict = 'SESSAO REPROVADA'
if ($completion.status -eq 'measured' -or $completion.status -eq 'unresolved' -or
    $completion.status -eq 'partial') {
    $sessionVerdict = 'SESSAO CONCLUIDA'
}

$verdict = $sessionVerdict
if ($sessionVerdict -eq 'SESSAO REPROVADA') { }
elseif ($librariesMeasured -and $routesAgree) {
    $verdict = ('BIBLIOTECAS MEDIDAS E CONFERIDAS: ' + $completion.libraries_count)
}
elseif ($librariesMeasured) {
    $verdict = ('BIBLIOTECAS MEDIDAS SEM CONFERENCIA: ' + $completion.libraries_count +
                ' -- as duas rotas nao concordaram ou a rota simples falhou')
}
else {
    $verdict = ('SESSAO CONCLUIDA SEM MEDIDA -- lacuna permanece (' +
                $completion.libraries.reason + ')')
}

Write-Host "[INFO] marcador do no    : $($completion.marker_chain)"
Write-Host "[INFO] rota rica         : $($completion.route_rich_chain)"
Write-Host "[INFO] rota de conferencia: $($completion.route_simple_chain)"
Write-Host "[INFO] bibliotecas        : $($completion.libraries_count)"
Write-Host "[INFO] evidencia          : $($completion.libraries.status)"

$sessionReport = [ordered]@{
    verdict = $verdict
    session_verdict = $sessionVerdict
    libraries_measured = $librariesMeasured
    routes_agree = $routesAgree
    libraries_count = $completion.libraries_count
    libraries_names = $completion.libraries_names
    libraries = $completion.libraries
    cross_check = $completion.cross_check
    libman_nodes = $completion.libman_nodes
    marker_chain = $completion.marker_chain
    marker_chain_source = $completion.marker_chain_source
    route_rich_chain = $completion.route_rich_chain
    route_simple_chain = $completion.route_simple_chain
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
# UTF-8 sem BOM (mesma correcao aplicada aos wrappers de W1, ao wrapper de
# qualificacao e ao wrapper do probe 36).
[System.IO.File]::WriteAllText(
    (Join-Path $artifacts 'session-verdict.json'),
    ($sessionReport | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false)))

Write-Section "VEREDITO: $verdict"
Write-Host "Relatorio: $(Join-Path $artifacts 'session-verdict.json')"

# Codigo de saida por CAMADA:
#   0 = sessao ok, inventario medido E conferido pelas duas rotas
#   4 = sessao ok, inventario medido mas NAO conferido (rotas discordam ou a
#       rota simples falhou) OU sessao ok sem medida (lacuna permanece)
#   3 = sessao reprovada
if ($sessionVerdict -eq 'SESSAO REPROVADA') { exit 3 }
if (-not $librariesMeasured) {
    Write-Host '[BLOQUEIO] A sessao rodou, mas o inventario NAO foi lido.' -ForegroundColor Yellow
    Write-Host '           O bloqueador libraries_unresolved permanece.' -ForegroundColor Yellow
    exit 4
}
if (-not $routesAgree) {
    Write-Host '[BLOQUEIO] Inventario medido pela rota rica e NAO conferido.' -ForegroundColor Yellow
    Write-Host '           Uma leitura unica nao prova nada sobre si mesma.' -ForegroundColor Yellow
    exit 4
}
exit 0
