<#
  run_readonly_tree_scan.ps1 -- varredura SOMENTE LEITURA da arvore de um
  projeto, para servir de ANTES numa comparacao.

  POR QUE ESTE ARQUIVO EXISTE
  ===========================
  A fase R2 pergunta "mudou alguma coisa alem do que foi autorizado?", e essa
  pergunta so tem resposta com duas medicoes: a arvore ANTES e a arvore
  DEPOIS. O DEPOIS ja tinha instrumento -- o probe 47 mede a saida no estagio
  de verificacao. O ANTES nao tinha: o probe 21 varre a arvore inteira desde
  a fase L0, mas nenhum lancador o chamava, e sem lancador ele so rodava a
  mao. Comparar contra medicao feita a mao e comparar contra memoria.

  O probe 21 e o MESMO instrumento nos dois lados? Nao, e isso esta declarado
  no artefato: ele varre com o scanner generico, o probe 47 varre o que o
  plano autorizou. A camada de ARVORE (nome + type_guid) e comparavel entre
  os dois; a camada de TEXTO nao vem daqui.

  SOMENTE LEITURA, E PROVADO POR HASH
  ===================================
  Copia o projeto, mede o hash da copia antes e depois, e recusa se a copia
  mudou. O projeto-base tambem e conferido: se ele foi tocado, isso e um
  achado, nao um detalhe.

  USO:
    .\run_readonly_tree_scan.ps1 -BaseProject <p> -WorkDir <sem-espaco> -Exe <mt.exe>
    ...  -Execute     # abre o produto; sem isto so valida e nao copia nada.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$BaseProject,

    [Parameter(Mandatory = $true)]
    [string]$WorkDir,

    # Congela o que se espera do arquivo de entrada. Opcional: nem todo ANTES
    # e um template com hash publicado. Informado, e conferido.
    [string]$ExpectedBaseSha256,

    [switch]$ValidateOnly,
    [switch]$Execute,

    # SEM DEFAULT, de proposito. Os wrappers antigos fixam a instalacao desta
    # maquina de desenvolvimento, e o gate de higiene os carrega como divida
    # NOMEADA. Arquivo novo nao nasce devendo: quem chama informa o executavel.
    # `mastertool-bridge detect-mastertool` o descobre quando ha uma unica
    # instalacao plausivel -- nesta maquina ha onze, e ele RECUSA, que e o
    # comportamento certo e a razao de o parametro nao ter default.
    [Parameter(Mandatory = $true)]
    [string]$Exe,

    [string]$ExpectedExeVersion = '4.1.0.11',

    # Derivado do proprio arquivo: este script mora em
    # <repo>/scripts/mastertool/, entao dois niveis acima e a raiz.
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),

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

Write-Section "Varredura read-only de arvore -- modo '$Mode'"

# =============================================================================
# BLOCO 1 -- VALIDACAO
# =============================================================================

if (-not [IO.Path]::IsPathRooted($BaseProject)) { Fail 'BaseProject deve ser absoluto' }
if (-not (Test-Path -LiteralPath $BaseProject)) { Fail "Projeto inexistente: $BaseProject" }

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
$baseSha = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
Write-Host "[OK] Base        : $BaseProject"
Write-Host "[OK] Tamanho base: $($baseInfo.Length) bytes"
Write-Host "[OK] SHA256 base : $baseSha"
if ($ExpectedBaseSha256) {
    if ($baseSha -ne $ExpectedBaseSha256.ToLower()) {
        Fail "SHA-256 do projeto diverge do valor declarado em -ExpectedBaseSha256"
    }
    Write-Host '[OK] SHA256      : confere com o valor declarado'
}
else {
    Write-Host '[INFO] -ExpectedBaseSha256 nao informado: o hash acima e o MEDIDO,'
    Write-Host '       e nao foi conferido contra nada.'
}

if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel nao encontrado: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
if ($exeVersion -ne $ExpectedExeVersion) {
    Fail "FileVersion inesperada: '$exeVersion'. Sem fallback."
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

# Varredura de ANTES nao roda com fase de escrita aberta. Nao e o probe 21 que
# escreveria -- e que uma janela de escrita aberta durante a medicao do ANTES
# torna o ANTES suspeito: nada garante que a fase nao foi usada no intervalo.
$fase = Select-String -LiteralPath $safetyFile -Pattern '^CONTROLLED_WRITE_PHASE\s*=\s*(.+)$'
if ($fase -and $fase.Matches[0].Groups[1].Value.Trim() -ne 'None') {
    Fail ("Ha fase de escrita ABERTA (" + $fase.Matches[0].Groups[1].Value.Trim() +
          "). Um ANTES medido com janela de escrita aberta nao serve de ANTES.")
}
Write-Host '[OK] CONTROLLED_WRITE_PHASE = None'

$probe21 = Join-Path $RepoRoot 'scripts\mastertool\probes\21_scan_project_tree_full.py'
if (-not (Test-Path -LiteralPath $probe21)) { Fail "Probe 21 nao encontrado: $probe21" }
Write-Host "[OK] Probe 21    : $probe21"

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
# BLOCO 2 -- EXECUCAO, SOMENTE LEITURA
# =============================================================================

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$copyPath = Join-Path $WorkDir 'SCAN-work.project'
$artifacts = Join-Path $WorkDir 'artifacts'
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

Copy-Item -LiteralPath $BaseProject -Destination $copyPath
Set-ItemProperty -LiteralPath $copyPath -Name IsReadOnly -Value $false
$copySha = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copySha -ne $baseSha) { Fail 'A copia difere do projeto-base.' }
Write-Host "[OK] Copia       : $copyPath"
Write-Host "[OK] SHA256 copia: $copySha (identico a base)"

Write-Section 'Lancando MasterTool -- varredura (somente leitura)'
$argList = @(
    ('--project="' + $copyPath + '"'),
    ('--runscript="' + $probe21 + '"'),
    ('--scriptargs:"--output=' + $artifacts + '"')
)
Write-Host ($argList -join ' ')
Write-Host '[LEMBRETE] UI VISIVEL. Diante de qualquer dialogo: CANCELE e registre.' -ForegroundColor Yellow

$startedAt = Get-Date
$proc = Start-Process -FilePath $Exe -ArgumentList $argList -PassThru
Write-Host "[INFO] PID: $($proc.Id)"

# O probe 21 grava num subdiretorio com nome gerado por `new_export_dir`, entao
# o caminho de conclusao NAO e previsivel. Espera-se pelo `manifest.json`
# ONDE QUER QUE ELE APARECA sob o diretorio de artefatos.
function Find-Manifest {
    $achados = @(Get-ChildItem -LiteralPath $artifacts -Recurse -Filter 'manifest.json' `
                 -ErrorAction SilentlyContinue)
    if ($achados.Count -eq 0) { return $null }
    return ($achados | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}

$limite = (Get-Date).AddSeconds($ArtifactWaitSeconds)
$manifestPath = $null
while ($null -eq $manifestPath -and (Get-Date) -lt $limite) {
    Start-Sleep -Seconds 3
    $manifestPath = Find-Manifest
    if ($proc.HasExited -and $null -eq $manifestPath) { break }
}
Write-Host "[INFO] artefato de conclusao presente: $($null -ne $manifestPath)"

$fechadoPeloHost = $false
if ($AutoCloseWindow -and -not $proc.HasExited) {
    Write-Host '[INFO] Fechando a janela (CloseMainWindow, equivalente ao X)...'
    try { $null = $proc.CloseMainWindow(); $fechadoPeloHost = $true } catch { }
}
try { Wait-Process -Id $proc.Id -Timeout $TimeoutSeconds -ErrorAction Stop } catch { }
try { $proc.Refresh() } catch { }
$timedOut = -not $proc.HasExited
$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
Write-Host "[INFO] duracao: $elapsed s; fechado pelo host: $fechadoPeloHost"
Write-Host '[INFO] O exit code do launcher NAO decide nada.'
if ($timedOut) {
    Write-Host '[TIMEOUT] A janela nao fechou. Provavelmente ha um dialogo aberto.' -ForegroundColor Yellow
    Write-Host '          Este host NAO mata processo. Verifique a tela.' -ForegroundColor Yellow
}

if ($null -eq $manifestPath) {
    Fail 'manifest.json ausente. Sem veredito -- trate como falha de artefato.'
}

$copyShaAfter = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash.ToLower()
if ($copyShaAfter -ne $copySha) { Fail 'A copia MUDOU durante a varredura read-only.' }
Write-Host '[OK] Copia intacta apos a execucao (somente leitura confirmada por hash).'

$baseShaAfter = (Get-FileHash -LiteralPath $BaseProject -Algorithm SHA256).Hash.ToLower()
if ($baseShaAfter -ne $baseSha) { Fail 'O PROJETO-BASE ORIGINAL foi tocado. Investigar imediatamente.' }
Write-Host '[OK] Projeto-base original intacto.'

Start-Sleep -Seconds 2
$orphans = @(Get-Process -Name $ProcessPattern -ErrorAction SilentlyContinue)
if ($orphans.Count -gt 0) {
    Fail ("Orfaos apos a execucao: " + (($orphans | ForEach-Object { $_.Id }) -join ', '))
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$runDir = Split-Path -Parent $manifestPath
$flatNodes = Join-Path $runDir 'flat-nodes.json'

Write-Host "[INFO] status da varredura: $($manifest.status)"
Write-Host "[INFO] nos: $($manifest.observed.total_nodes); profundidade: $($manifest.observed.max_depth)"

Write-Section 'VEREDITO'
# `complete` e o unico status que autoriza usar isto como ANTES. Varredura
# truncada descreve parte da arvore, e comparar contra parte da arvore faria
# todo o resto parecer removido.
if ($manifest.status -ne 'complete') {
    Write-Host "[NAO USAVEL COMO ANTES] status: $($manifest.status)" -ForegroundColor Yellow
    Write-Host '  Varredura incompleta descreve parte da arvore. Comparar contra'
    Write-Host '  parte da arvore faria o resto parecer removido.'
    Write-Host "flat-nodes: $flatNodes"
    exit 3
}
Write-Host '[OK] VARREDURA COMPLETA -- utilizavel como ANTES' -ForegroundColor Green
Write-Host "flat-nodes: $flatNodes"
Write-Host "manifest  : $manifestPath"
exit 0
