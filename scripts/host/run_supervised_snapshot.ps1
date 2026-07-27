<#
.SYNOPSIS
Etapa B - dispara o `supervised-snapshot` com os argumentos deste projeto
ja preenchidos. E so um montador de argumentos: quem valida a copia, abre o
MasterTool, espera, confere hash e roda o indexador e o orquestrador Python
(src/mastertool_bridge/automation/supervised_run.py).

.DESCRIPTION
FAIL-CLOSED POR PADRAO: sem -Execute apenas IMPRIME o comando e confere as
pre-condicoes locais. Nada e lancado.

Existe porque a linha de comando tem 7 argumentos obrigatorios com caminhos
que contem espacos - montar isso a mao no PowerShell erra facil (continuacao
com crase, aspas, `$env:` em vez de VAR=valor).

.EXAMPLE
  .\run_supervised_snapshot.ps1              # ensaio
  .\run_supervised_snapshot.ps1 -Execute     # execucao real, UI visivel
  .\run_supervised_snapshot.ps1 -ProbeLadderSurface -Execute
                                              # idem, + sonda Fase L1 sobre
                                              # application/9/4 FB_PISCA_EXEMPLO
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,

    [string]$ProjectCopy = 'C:\caminho\para\Projeto Teste\_descartavel\ExemploPlanta V1.0 COPIA.project',
    [string]$OriginalProject = 'C:\caminho\para\Projeto Teste\ExemploPlanta V1.0.project',

    # Sem espacos de proposito: nao e exigencia aqui (o orquestrador nao usa
    # --scriptargs), mas mantem o layout de execucao previsivel.
    [string]$RunsRoot = 'C:\mastertool-ai-bridge-runs',

    # Identidade da Application do ExemploPlanta V1.0. Trocar ao rodar contra
    # outro projeto - NUNCA hardcoded do lado Python, por isso vem por
    # argumento.
    [string]$ApplicationName = 'Application',
    [string]$ApplicationGuid = '00000000-0000-0000-0000-000000000001',
    [string]$ApplicationTypeGuid = '639b491f-5557-464c-af91-1471bac9f549',

    [int]$TimeoutSeconds = 900,
    [switch]$NoIndex,

    # Fase L1 (Ladder) - sondagem de superfície sobre UM objeto POU. Os 4
    # valores abaixo sao a identidade de application/9/4 FB_PISCA_EXEMPLO
    # no ExemploPlanta V1.0 (menor candidato partially_supported de L0, achado
    # em docs/14-ladder-roadmap.md). Trocar ao sondar outro objeto/projeto -
    # NUNCA hardcoded do lado Python, por isso vem por argumento aqui tambem.
    [switch]$ProbeLadderSurface,
    [string]$LadderTargetNodeId = 'application/9/4',
    [string]$LadderExpectedName = 'FB_PISCA_EXEMPLO',
    [string]$LadderExpectedGuid = '00000000-0000-0000-0000-000000000002',
    [string]$LadderExpectedTypeGuid = '6f9dac99-8de1-4efc-8465-68ac443b7d08',

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'

function Write-Section($text) {
    Write-Host ''
    Write-Host ('=' * 70)
    Write-Host $text
    Write-Host ('=' * 70)
}

function Fail($message) {
    Write-Host "[BLOQUEADO] $message" -ForegroundColor Red
    exit 2
}

Write-Section 'Etapa B - supervised snapshot'

# Raiz do repo derivada do proprio arquivo (mesma cadeia de fallbacks do
# runner da Etapa A: `powershell -File` deixa $PSScriptRoot vazio na ligacao
# de parametros).
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $selfPath = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($selfPath)) { $selfPath = $MyInvocation.MyCommand.Path }
    if ([string]::IsNullOrWhiteSpace($selfPath)) { Fail 'Informe -RepoRoot explicitamente.' }
    $RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $selfPath))
}
if (-not (Test-Path -LiteralPath $RepoRoot)) { Fail "RepoRoot inexistente: $RepoRoot" }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Write-Host "[OK] RepoRoot       : $RepoRoot"

if (-not (Test-Path -LiteralPath $ProjectCopy)) {
    Fail ("Copia descartavel nao encontrada: $ProjectCopy`n" +
          "            Crie com: Copy-Item -LiteralPath '$OriginalProject' -Destination '$ProjectCopy'")
}
if (-not (Test-Path -LiteralPath $OriginalProject)) { Fail "Projeto original nao encontrado: $OriginalProject" }

$copyFull = (Resolve-Path -LiteralPath $ProjectCopy).Path
$origFull = (Resolve-Path -LiteralPath $OriginalProject).Path
if ($copyFull -eq $origFull) { Fail '-ProjectCopy aponta para o PROJETO ORIGINAL.' }
Write-Host "[OK] Copia          : $copyFull"
Write-Host "[OK] SHA256 antes   : $((Get-FileHash -LiteralPath $copyFull -Algorithm SHA256).Hash)"

$running = @(Get-Process -Name 'MT8500*' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    $ids = ($running | ForEach-Object { $_.Id }) -join ', '
    Fail "Ha instancia(s) do MasterTool aberta(s) (PID: $ids). Feche antes de rodar."
}
Write-Host '[OK] Nenhuma instancia do MasterTool aberta.'

if ($ProbeLadderSurface) {
    $faltando = @()
    if ([string]::IsNullOrWhiteSpace($LadderTargetNodeId)) { $faltando += '-LadderTargetNodeId' }
    if ([string]::IsNullOrWhiteSpace($LadderExpectedName)) { $faltando += '-LadderExpectedName' }
    if ([string]::IsNullOrWhiteSpace($LadderExpectedGuid)) { $faltando += '-LadderExpectedGuid' }
    if ([string]::IsNullOrWhiteSpace($LadderExpectedTypeGuid)) { $faltando += '-LadderExpectedTypeGuid' }
    if ($faltando.Count -gt 0) {
        Fail ("-ProbeLadderSurface exige a identificacao completa do alvo. Faltando: " +
              ($faltando -join ', ') +
              "`n            Os 25 candidatos da Fase L0 compartilham o mesmo type_guid, entao os quatro campos sao necessarios juntos.")
    }
    Write-Host "[OK] Alvo Ladder    : $LadderTargetNodeId ($LadderExpectedName)"
}

$cliArgs = @(
    '-m', 'mastertool_bridge', 'supervised-snapshot',
    '--project-copy', $copyFull,
    '--original-project', $origFull,
    '--runs-root', $RunsRoot,
    '--expected-application-name', $ApplicationName,
    '--expected-application-guid', $ApplicationGuid,
    '--expected-application-type-guid', $ApplicationTypeGuid,
    '--timeout', $TimeoutSeconds.ToString()
)
if ($NoIndex) { $cliArgs += '--no-index' }
if ($ProbeLadderSurface) {
    $cliArgs += @(
        '--probe-ladder-surface',
        '--ladder-target-node-id', $LadderTargetNodeId,
        '--ladder-expected-name', $LadderExpectedName,
        '--ladder-expected-guid', $LadderExpectedGuid,
        '--ladder-expected-type-guid', $LadderExpectedTypeGuid
    )
}

Write-Section 'Comando'
Write-Host ('$env:PYTHONPATH = "' + (Join-Path $RepoRoot 'src') + '"')
Write-Host ('python ' + (($cliArgs | ForEach-Object {
    if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
}) -join ' '))

if (-not $Execute) {
    Write-Section 'ENSAIO (nada foi lancado)'
    Write-Host 'Pre-condicoes verificadas. Repita com -Execute para rodar de verdade.'
    exit 0
}

Write-Section 'EXECUTANDO (a UI do MasterTool vai abrir - acompanhe a tela)'
Write-Host 'Se aparecer dialogo inesperado, CANCELE e registre. O orquestrador'
Write-Host 'NUNCA mata o MasterTool: no timeout ele marca needs_interaction.'
Write-Host ''

$env:PYTHONPATH = Join-Path $RepoRoot 'src'
Push-Location $RepoRoot
try {
    & python @cliArgs
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

Write-Section "Codigo de saida do orquestrador: $code"
if ($code -eq 0) {
    Write-Host '[OK] Estado final: completed.' -ForegroundColor Green
}
else {
    Write-Host '[ATENCAO] Estado final NAO foi completed. Leia o relatorio do run e' -ForegroundColor Yellow
    Write-Host "          o status-history.jsonl em $RunsRoot\<run-id>\." -ForegroundColor Yellow
}
exit $code
