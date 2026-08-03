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
                                              # application/9/4 BLINK_QUE_FUNCIONA
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,

    [string]$ProjectCopy = 'C:\Pasta Com Espacos\Projeto Teste\_descartavel\ExemploPlanta V1.0 COPIA.project',
    [string]$OriginalProject = 'C:\Pasta Com Espacos\Projeto Teste\ExemploPlanta V1.0.project',

    # Sem espacos de proposito: nao e exigencia aqui (o orquestrador nao usa
    # --scriptargs), mas mantem o layout de execucao previsivel.
    [string]$RunsRoot = 'C:\mastertool-rankine-bridge-runs',

    # Identidade da Application do ExemploPlanta V1.0. Trocar ao rodar contra
    # outro projeto - NUNCA hardcoded do lado Python, por isso vem por
    # argumento.
    [string]$ApplicationName = 'Application',
    [string]$ApplicationGuid = '00000000-0000-0000-0000-000000000001',
    [string]$ApplicationTypeGuid = '639b491f-5557-464c-af91-1471bac9f549',

    [int]$TimeoutSeconds = 900,
    [switch]$NoIndex,

    # Fase L1 (Ladder) - sondagem de superfície sobre UM objeto POU. Os 4
    # valores abaixo sao a identidade de application/9/4 BLINK_QUE_FUNCIONA
    # no ExemploPlanta V1.0 (menor candidato partially_supported de L0, achado
    # em docs/14-ladder-roadmap.md). Trocar ao sondar outro objeto/projeto -
    # NUNCA hardcoded do lado Python, por isso vem por argumento aqui tambem.
    [switch]$ProbeLadderSurface,
    [string]$LadderTargetNodeId = 'application/9/4',
    [string]$LadderExpectedName = 'BLINK_QUE_FUNCIONA',
    [string]$LadderExpectedGuid = 'beca53e2-8466-404a-baf5-9fba1adc0fac',
    [string]$LadderExpectedTypeGuid = '6f9dac99-8de1-4efc-8465-68ac443b7d08',

    # Fase L1, probe 17 - sondagem da superficie DINAMICA. Defaults VAZIOS de
    # proposito, diferente dos -Ladder* do probe 16: o contrato exige
    # identidade explicita no modo supervisionado. Um default preenchido
    # transformaria "esqueci de informar o alvo" numa execucao silenciosa
    # contra o alvo de outra pessoa.
    [switch]$ProbeLadderDynamicSurface,
    [string]$LadderDynamicTargetNodeId = '',
    [string]$LadderDynamicExpectedName = '',
    [string]$LadderDynamicExpectedGuid = '',
    [string]$LadderDynamicExpectedTypeGuid = '',

    # Fase L1, probe 18 - canal Extender. Defaults VAZIOS pelo mesmo motivo
    # dos -LadderDynamic*: identidade explicita e exigida no modo
    # supervisionado.
    [switch]$ProbeLadderExtenderSurface,
    [string]$LadderExtenderTargetNodeId = '',
    [string]$LadderExtenderExpectedName = '',
    [string]$LadderExtenderExpectedGuid = '',
    [string]$LadderExtenderExpectedTypeGuid = '',

    # Fase L1, probe 19 - assinatura de export_xml (SEM invocar). Defaults
    # vazios pelo mesmo motivo dos anteriores.
    [switch]$ProbePLCopenExportSignature,
    [string]$PLCopenTargetNodeId = '',
    [string]$PLCopenExpectedName = '',
    [string]$PLCopenExpectedGuid = '',
    [string]$PLCopenExpectedTypeGuid = '',
    [switch]$NoInspectActiveApplication,

    # Fase L1 - EXPORTACAO CONTROLADA. Primeira operacao que ESCREVE em
    # disco (dentro do diretorio descartavel da run, nunca no projeto).
    [switch]$ExportPLCopenXml,
    [string]$ExportTargetNodeId = '',
    [string]$ExportExpectedName = '',
    [string]$ExportExpectedGuid = '',
    [string]$ExportExpectedTypeGuid = '',
    [string]$ExportTargetLeafName = 'pou-export',

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

# Deteccao de processo aberto. Em execucao real (-Execute) SEMPRE consulta o
# processo de verdade via Get-Process -- esse ramo do `if` e estruturalmente
# inalcancavel com -Execute, entao nao ha combinacao possivel que deixe
# -Execute + lista simulada colarem juntos. A variavel de ambiente
# MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST so e considerada em ENSAIO, para tornar
# os testes deste wrapper deterministicos (independentes de haver ou nao
# MasterTool aberto na maquina que roda a suite). Formato: lista separada por
# ';', cada item '<nome-da-imagem>:<pid>'. String vazia = nenhum processo.
$running = @(if (-not $Execute -and $null -ne $env:MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST) {
    $raw = $env:MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST
    if ($raw -eq '') {
        @()
    } else {
        $parsed = @()
        foreach ($item in ($raw -split ';')) {
            if ($item -notmatch '^[^:]+:\d+$') {
                Fail "MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST malformada: '$item' (esperado '<nome>:<pid>')."
            }
            $parts = $item -split ':'
            $parsed += [pscustomobject]@{ Id = [int]$parts[1] }
        }
        $parsed
    }
} else {
    Get-Process -Name 'MT8500*' -ErrorAction SilentlyContinue
})
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

if ($ProbeLadderDynamicSurface) {
    $faltandoDin = @()
    if ([string]::IsNullOrWhiteSpace($LadderDynamicTargetNodeId)) { $faltandoDin += '-LadderDynamicTargetNodeId' }
    if ([string]::IsNullOrWhiteSpace($LadderDynamicExpectedName)) { $faltandoDin += '-LadderDynamicExpectedName' }
    if ([string]::IsNullOrWhiteSpace($LadderDynamicExpectedGuid)) { $faltandoDin += '-LadderDynamicExpectedGuid' }
    if ([string]::IsNullOrWhiteSpace($LadderDynamicExpectedTypeGuid)) { $faltandoDin += '-LadderDynamicExpectedTypeGuid' }
    if ($faltandoDin.Count -gt 0) {
        Fail ("-ProbeLadderDynamicSurface exige a identificacao completa do alvo. Faltando: " +
              ($faltandoDin -join ', ') +
              "`n            Sem default de identidade no modo supervisionado: os candidatos da Fase L0 compartilham o mesmo type_guid.")
    }
    Write-Host "[OK] Alvo Dinamico  : $LadderDynamicTargetNodeId ($LadderDynamicExpectedName)"
}

if ($ProbeLadderExtenderSurface) {
    $faltandoExt = @()
    if ([string]::IsNullOrWhiteSpace($LadderExtenderTargetNodeId)) { $faltandoExt += '-LadderExtenderTargetNodeId' }
    if ([string]::IsNullOrWhiteSpace($LadderExtenderExpectedName)) { $faltandoExt += '-LadderExtenderExpectedName' }
    if ([string]::IsNullOrWhiteSpace($LadderExtenderExpectedGuid)) { $faltandoExt += '-LadderExtenderExpectedGuid' }
    if ([string]::IsNullOrWhiteSpace($LadderExtenderExpectedTypeGuid)) { $faltandoExt += '-LadderExtenderExpectedTypeGuid' }
    if ($faltandoExt.Count -gt 0) {
        Fail ("-ProbeLadderExtenderSurface exige a identificacao completa do alvo. Faltando: " +
              ($faltandoExt -join ', ') +
              "`n            Sem default de identidade no modo supervisionado.")
    }
    Write-Host "[OK] Alvo Extender  : $LadderExtenderTargetNodeId ($LadderExtenderExpectedName)"
}

if ($ProbePLCopenExportSignature) {
    $faltandoPlc = @()
    if ([string]::IsNullOrWhiteSpace($PLCopenTargetNodeId)) { $faltandoPlc += '-PLCopenTargetNodeId' }
    if ([string]::IsNullOrWhiteSpace($PLCopenExpectedName)) { $faltandoPlc += '-PLCopenExpectedName' }
    if ([string]::IsNullOrWhiteSpace($PLCopenExpectedGuid)) { $faltandoPlc += '-PLCopenExpectedGuid' }
    if ([string]::IsNullOrWhiteSpace($PLCopenExpectedTypeGuid)) { $faltandoPlc += '-PLCopenExpectedTypeGuid' }
    if ($faltandoPlc.Count -gt 0) {
        Fail ("-ProbePLCopenExportSignature exige a identificacao completa do alvo. Faltando: " +
              ($faltandoPlc -join ', ') +
              "`n            Sem default de identidade no modo supervisionado.")
    }
    Write-Host "[OK] Alvo PLCopen   : $PLCopenTargetNodeId ($PLCopenExpectedName)"
    Write-Host "[OK] Escopo App     : $(if ($NoInspectActiveApplication) { 'NAO inspecionado' } else { 'inspecionado' })"
}

if ($ExportPLCopenXml) {
    $faltandoExp = @()
    if ([string]::IsNullOrWhiteSpace($ExportTargetNodeId)) { $faltandoExp += '-ExportTargetNodeId' }
    if ([string]::IsNullOrWhiteSpace($ExportExpectedName)) { $faltandoExp += '-ExportExpectedName' }
    if ([string]::IsNullOrWhiteSpace($ExportExpectedGuid)) { $faltandoExp += '-ExportExpectedGuid' }
    if ([string]::IsNullOrWhiteSpace($ExportExpectedTypeGuid)) { $faltandoExp += '-ExportExpectedTypeGuid' }
    if ($faltandoExp.Count -gt 0) {
        Fail ("-ExportPLCopenXml exige a identificacao completa do alvo. Faltando: " +
              ($faltandoExp -join ', ') +
              "`n            Esta operacao ESCREVE em disco; nenhum default de identidade e aceito.")
    }
    if ($ExportTargetLeafName -match '[\/:]' -or $ExportTargetLeafName -eq '..' -or $ExportTargetLeafName -eq '.') {
        Fail "-ExportTargetLeafName deve ser um nome SIMPLES (sem separador, drive ou '..'): '$ExportTargetLeafName'"
    }
    Write-Host "[OK] Exportacao     : $ExportTargetNodeId ($ExportExpectedName) -> leaf '$ExportTargetLeafName'"
    Write-Host "[AVISO] Esta operacao ESCREVE em disco, dentro do diretorio da run." -ForegroundColor Yellow
}

# Exclusao mutua: canais distintos, gates proprios, vereditos que nao podem
# competir sob um unico status. Bloqueado aqui alem de na CLI e no runner.
$probesLigados = @()
if ($ProbeLadderSurface) { $probesLigados += '-ProbeLadderSurface' }
if ($ProbeLadderDynamicSurface) { $probesLigados += '-ProbeLadderDynamicSurface' }
if ($ProbeLadderExtenderSurface) { $probesLigados += '-ProbeLadderExtenderSurface' }
if ($ProbePLCopenExportSignature) { $probesLigados += '-ProbePLCopenExportSignature' }
if ($ExportPLCopenXml) { $probesLigados += '-ExportPLCopenXml' }
if ($probesLigados.Count -gt 1) {
    Fail ("Mais de um probe Ladder na mesma run: " + ($probesLigados -join ', ') +
          "`n            Cada probe investiga um canal distinto; rode um por vez.")
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
if ($ProbeLadderDynamicSurface) {
    $cliArgs += @(
        '--probe-ladder-dynamic-surface',
        '--ladder-dynamic-target-node-id', $LadderDynamicTargetNodeId,
        '--ladder-dynamic-expected-name', $LadderDynamicExpectedName,
        '--ladder-dynamic-expected-guid', $LadderDynamicExpectedGuid,
        '--ladder-dynamic-expected-type-guid', $LadderDynamicExpectedTypeGuid
    )
}
if ($ProbeLadderExtenderSurface) {
    $cliArgs += @(
        '--probe-ladder-extender-surface',
        '--ladder-extender-target-node-id', $LadderExtenderTargetNodeId,
        '--ladder-extender-expected-name', $LadderExtenderExpectedName,
        '--ladder-extender-expected-guid', $LadderExtenderExpectedGuid,
        '--ladder-extender-expected-type-guid', $LadderExtenderExpectedTypeGuid
    )
}
if ($ProbePLCopenExportSignature) {
    $cliArgs += @(
        '--probe-plcopen-export-signature',
        '--plcopen-target-node-id', $PLCopenTargetNodeId,
        '--plcopen-expected-name', $PLCopenExpectedName,
        '--plcopen-expected-guid', $PLCopenExpectedGuid,
        '--plcopen-expected-type-guid', $PLCopenExpectedTypeGuid
    )
    if ($NoInspectActiveApplication) { $cliArgs += '--no-inspect-active-application' }
}
if ($ExportPLCopenXml) {
    $cliArgs += @(
        '--export-plcopen-xml',
        '--export-target-node-id', $ExportTargetNodeId,
        '--export-expected-name', $ExportExpectedName,
        '--export-expected-guid', $ExportExpectedGuid,
        '--export-expected-type-guid', $ExportExpectedTypeGuid,
        '--export-target-leaf-name', $ExportTargetLeafName
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
