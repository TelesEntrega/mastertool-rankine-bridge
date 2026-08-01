<#
.SYNOPSIS
Etapa A do roadmap de automacao - auxiliar de HOST para os 5 testes de linha
de comando do MT8500 3.63. NAO roda dentro do MasterTool: monta o comando,
checa as pre-condicoes de seguranca e captura o que o probe IronPython NAO
consegue ver de dentro (codigo de saida, duracao, processo orfao, integridade
da copia descartavel).

.DESCRIPTION
FAIL-CLOSED POR PADRAO: sem -Execute este script apenas IMPRIME o comando
exato e roda as verificacoes previas. Nada e lancado. Lancar o MT8500.exe
exige -Execute explicito, porque a UI precisa ficar visivel e sob supervisao
humana nos 4 primeiros testes (dialogos de licenca/conversao/biblioteca
precisam poder ser cancelados por uma pessoa).

Testes (ver docs/15-automation-launcher-roadmap.md):
  t1  --runscript
  t2  --runscript + --scriptargs
  t3  --project                (sem script: nenhum result.json e esperado)
  t4  --project + --runscript + --scriptargs
  t5  --noUI + --project + --runscript + --scriptargs   (SO apos t1..t4)

.EXAMPLE
  # 1) ensaio: imprime o comando e valida pre-condicoes, sem lancar nada
  .\run_cli_probe_test.ps1 -Test t1

.EXAMPLE
  # 2) execucao real, com UI visivel e supervisao humana
  .\run_cli_probe_test.ps1 -Test t1 -Execute
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('t1', 't2', 't3', 't4', 't5')]
    [string]$Test,

    [string]$Exe = 'C:\Program Files (x86)\Altus\MT8500 3.63\MT8500\Common\MT8500.exe',

    # Resolvido abaixo se nao for informado. NAO usar $PSScriptRoot como valor
    # padrao aqui: quando o script e chamado via `powershell -File ...`, o
    # $PSScriptRoot vem VAZIO no momento da ligacao de parametros e o
    # Split-Path falha com "cadeia de caracteres vazia".
    [string]$RepoRoot,

    # Copia DESCARTAVEL do .project. Obrigatoria em t3/t4/t5. Nunca aponte
    # para o projeto original.
    [string]$ProjectCopy,

    # Projeto original, so para a checagem de "voce nao apontou para o original".
    [string]$OriginalProject = 'C:\Pasta Com Espacos\Projeto Teste\ExemploPlanta V1.0.project',

    # Diretorio de saida do probe. Padrao: workspace\logs\cli-probe\<teste>,
    # cujo caminho CONTEM ESPACOS (a raiz do repo e "Pasta Com Espacos") -
    # ou seja, t2 ja e por construcao um teste de preservacao de aspas.
    # Se t2 falhar, repita com um caminho SEM espacos (ex.:
    # -OutputDir 'C:\mastertool-cli-probe\t2') para separar "--scriptargs nao
    # e suportado" de "--scriptargs nao preserva espacos". Uma variavel por vez.
    [string]$OutputDir,

    # Sem esta flag nada e lancado.
    [switch]$Execute,

    # Permite prosseguir com outra instancia do MasterTool aberta (NAO
    # recomendado: uma instancia ja rodando pode capturar o --runscript ou
    # fazer o processo novo encerrar imediatamente, falseando o resultado).
    [switch]$AllowRunningInstance
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

Write-Section "Etapa A - teste $Test"

# --- pre-condicao 0: raiz do repositorio -----------------------------------
# Derivada do caminho do PROPRIO arquivo, com cadeia de fallbacks, porque
# cada forma de invocacao popula uma variavel automatica diferente:
#   powershell -File ...        -> $PSCommandPath
#   & .\script.ps1              -> $PSScriptRoot / $MyInvocation
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $selfPath = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($selfPath)) { $selfPath = $MyInvocation.MyCommand.Path }
    if ([string]::IsNullOrWhiteSpace($selfPath) -and -not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $selfPath = Join-Path $PSScriptRoot 'run_cli_probe_test.ps1'
    }
    if ([string]::IsNullOrWhiteSpace($selfPath)) {
        Fail ("Nao foi possivel descobrir o caminho deste script para derivar a raiz " +
              "do repositorio. Informe explicitamente: -RepoRoot '<...>\mastertool-rankine-bridge'")
    }
    # <repo>\scripts\host\run_cli_probe_test.ps1 -> host -> scripts -> <repo>
    $RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $selfPath))
}
if (-not (Test-Path -LiteralPath $RepoRoot)) { Fail "RepoRoot inexistente: $RepoRoot" }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Write-Host "[OK] RepoRoot   : $RepoRoot"

# --- pre-condicao 1: executavel -------------------------------------------
if (-not (Test-Path -LiteralPath $Exe)) { Fail "MT8500.exe nao encontrado em: $Exe" }
$exeVersion = (Get-Item -LiteralPath $Exe).VersionInfo.FileVersion
Write-Host "[OK] Executavel : $Exe"
Write-Host "[OK] FileVersion: $exeVersion"

# --- pre-condicao 2: probe e diretorio de saida ----------------------------
$probe = Join-Path $RepoRoot 'scripts\mastertool\probes\15_validate_command_line_execution.py'
if (-not (Test-Path -LiteralPath $probe)) { Fail "Probe nao encontrado em: $probe" }
Write-Host "[OK] Probe      : $probe"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $outDir = Join-Path $RepoRoot ("workspace\logs\cli-probe\" + $Test)
}
else {
    $outDir = $OutputDir
}
# ACHADO REAL do t2 (2026-07-24 16:33): o MT8500 3.63 QUEBRA o valor de
# --scriptargs em espacos em branco. O caminho
#   C:\...\Pasta Com Espacos\...\cli-probe\t2
# chegou ao script como TRES elementos de argv ('...\Agente', 'IA',
# 'MasterTool\...'), e o probe gravou em "C:\...\Exemplos\Agente"
# - um diretorio novo, fora do repositorio. O caminho do --runscript, por
# contraste, chegou intacto. Conclusao: qualquer caminho passado por
# --scriptargs NAO pode conter espaco.
$usesScriptArgs = @('t2', 't4', 't5') -contains $Test
$outDirAutoSwitched = $false
$outDirRequested = $outDir
if ($usesScriptArgs -and ($outDir -match '\s')) {
    $outDir = Join-Path 'C:\mastertool-cli-probe' $Test
    $outDirAutoSwitched = $true
    Write-Host '[AVISO] O diretorio de saida padrao contem espaco e este teste usa' -ForegroundColor Yellow
    Write-Host '        --scriptargs, que comprovadamente NAO preserva espacos (achado do t2).' -ForegroundColor Yellow
    Write-Host "        Trocado automaticamente para: $outDir" -ForegroundColor Yellow
    Write-Host '        Use -OutputDir para escolher outro caminho SEM espacos.' -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
$outDir = (Resolve-Path -LiteralPath $outDir).Path
Write-Host "[OK] Saida      : $outDir"

if ($usesScriptArgs -and ($outDir -match '\s')) {
    Fail ("O diretorio de saida contem espaco e o teste $Test usa --scriptargs, " +
          "que nao preserva espacos no MT8500 3.63 (achado do t2). O probe gravaria " +
          "num caminho truncado, fora do lugar. Informe -OutputDir com um caminho " +
          "SEM espacos, por exemplo: -OutputDir 'C:\mastertool-cli-probe\$Test'")
}

# --- pre-condicao 3: nenhuma instancia do MasterTool aberta ----------------
$running = @(Get-Process -Name 'MT8500*' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    $ids = ($running | ForEach-Object { $_.Id }) -join ', '
    if (-not $AllowRunningInstance) {
        Fail ("Ha $($running.Count) instancia(s) do MasterTool aberta(s) (PID: $ids). " +
              "Feche antes de rodar o teste: uma instancia existente pode absorver o " +
              "--runscript ou encerrar o processo novo na hora, falseando o resultado. " +
              "Use -AllowRunningInstance para ignorar por sua conta.")
    }
    Write-Host "[AVISO] Prosseguindo com instancia(s) aberta(s): PID $ids" -ForegroundColor Yellow
}
else {
    Write-Host '[OK] Nenhuma instancia do MasterTool aberta.'
}

# --- pre-condicao 4: copia descartavel (t3/t4/t5) --------------------------
$needsProject = @('t3', 't4', 't5') -contains $Test
$hashBefore = $null
if ($needsProject) {
    if ([string]::IsNullOrWhiteSpace($ProjectCopy)) {
        Fail "O teste $Test exige -ProjectCopy (caminho de uma COPIA descartavel do .project)."
    }
    if (-not (Test-Path -LiteralPath $ProjectCopy)) { Fail "Copia nao encontrada: $ProjectCopy" }

    $copyFull = (Resolve-Path -LiteralPath $ProjectCopy).Path
    if (Test-Path -LiteralPath $OriginalProject) {
        $origFull = (Resolve-Path -LiteralPath $OriginalProject).Path
        if ($copyFull -eq $origFull) {
            Fail "-ProjectCopy aponta para o PROJETO ORIGINAL. Use sempre uma copia descartavel."
        }
    }
    $ProjectCopy = $copyFull
    $hashBefore = (Get-FileHash -LiteralPath $ProjectCopy -Algorithm SHA256).Hash
    Write-Host "[OK] Copia      : $ProjectCopy"
    Write-Host "[OK] SHA256 antes: $hashBefore"
}

# --- montagem dos argumentos ----------------------------------------------
# ACHADO REAL do teste t1 de 2026-07-24 16:15: `Start-Process -ArgumentList`
# no PowerShell 5.1 junta os elementos do array com espaco e NAO acrescenta
# aspas em elementos que contem espaco. Como a raiz do repo e
# "...\Pasta Com Espacos\...", o MT8500 recebeu o valor sem aspas e leu so
# ate o primeiro espaco, falhando com
#   System.IO.FileNotFoundException: ...\Exemplos\Agente
# Isso NAO foi falha do MasterTool: ele reconheceu `--runscript` e tentou
# carregar o arquivo. Por isso as aspas vao EMBUTIDAS no proprio token.
$scriptArgsValue = '--output=' + $outDir

$argList = New-Object System.Collections.Generic.List[string]
switch ($Test) {
    't1' {
        $argList.Add('--runscript="' + $probe + '"')
    }
    't2' {
        $argList.Add('--runscript="' + $probe + '"')
        $argList.Add('--scriptargs:"' + $scriptArgsValue + '"')
    }
    't3' {
        $argList.Add('--project="' + $ProjectCopy + '"')
    }
    't4' {
        $argList.Add('--project="' + $ProjectCopy + '"')
        $argList.Add('--runscript="' + $probe + '"')
        $argList.Add('--scriptargs:"' + $scriptArgsValue + '"')
    }
    't5' {
        $argList.Add('--project="' + $ProjectCopy + '"')
        $argList.Add('--runscript="' + $probe + '"')
        $argList.Add('--scriptargs:"' + $scriptArgsValue + '"')
        $argList.Add('--noUI')
    }
}

Write-Section 'Comando exato'
Write-Host ('& "' + $Exe + '" `')
for ($i = 0; $i -lt $argList.Count; $i++) {
    $suffix = if ($i -lt $argList.Count - 1) { ' `' } else { '' }
    Write-Host ('    ' + $argList[$i] + $suffix)
}

# A linha de comando REAL que o MT8500 vai receber (Start-Process concatena
# com espaco simples). Confira esta linha antes de usar -Execute: e ela, nao
# o array acima, que determina o resultado.
Write-Section 'Linha de comando efetiva (o que o MT8500 realmente recebe)'
Write-Host ($argList -join ' ')

if (-not $Execute) {
    Write-Section 'ENSAIO (nada foi lancado)'
    Write-Host 'Pre-condicoes verificadas. Para executar de verdade, repita o comando com -Execute.'
    if ($Test -eq 't5') {
        Write-Host '[LEMBRETE] t5 usa --noUI: so rode depois de t1..t4 aprovados.' -ForegroundColor Yellow
    }
    else {
        Write-Host '[LEMBRETE] Mantenha a UI VISIVEL e acompanhe: se aparecer dialogo de licenca,' -ForegroundColor Yellow
        Write-Host '           conversao ou biblioteca ausente, CANCELE e registre o que apareceu.' -ForegroundColor Yellow
    }
    exit 0
}

# --- execucao (somente com -Execute) ---------------------------------------
Write-Section 'EXECUTANDO'
$startedAt = Get-Date
$proc = Start-Process -FilePath $Exe -ArgumentList $argList.ToArray() -PassThru -Wait
$finishedAt = Get-Date

$exitCode = $proc.ExitCode
$elapsed = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 1)
Write-Host "[INFO] Codigo de saida: $exitCode"
Write-Host "[INFO] Duracao: $elapsed s"

# --- pos-execucao: orfaos ---------------------------------------------------
Start-Sleep -Seconds 2
$orphans = @(Get-Process -Name 'MT8500*' -ErrorAction SilentlyContinue)
if ($orphans.Count -gt 0) {
    $oids = ($orphans | ForEach-Object { $_.Id }) -join ', '
    Write-Host "[AVISO] Processo(s) MT8500 ainda em execucao apos o encerramento: PID $oids" -ForegroundColor Yellow
    Write-Host '        Este script NAO mata processo nenhum. Encerre manualmente se for orfao.'
}
else {
    Write-Host '[OK] Nenhum processo MT8500 remanescente.'
}

# --- pos-execucao: integridade da copia -------------------------------------
$hashAfter = $null
$projectUnchanged = $null
if ($needsProject) {
    $hashAfter = (Get-FileHash -LiteralPath $ProjectCopy -Algorithm SHA256).Hash
    $projectUnchanged = ($hashAfter -eq $hashBefore)
    Write-Host "[INFO] SHA256 depois: $hashAfter"
    if ($projectUnchanged) {
        Write-Host '[OK] Copia do projeto INALTERADA.'
    }
    else {
        Write-Host '[FALHA] A copia do projeto FOI MODIFICADA. Registre isso no gate.' -ForegroundColor Red
    }
}

# --- pos-execucao: artefato do probe ---------------------------------------
# ACHADO REAL do t1 (2026-07-24 16:21): sem --scriptargs nao ha --output, entao
# a camada 1 falha e o probe grava na camada 2
# (<repo>\workspace\logs\<timestamp>_validate_command_line_execution\), NUNCA
# em <outDir>. Procurar so em <outDir> nao acha nada em t1. Por isso a busca
# cobre as 3 camadas do probe e filtra por data (artefato criado a partir do
# inicio DESTA execucao), e o achado e COPIADO para <outDir>\collected\ - o
# original nunca e movido nem apagado.
$searchRoots = New-Object System.Collections.Generic.List[string]
$searchRoots.Add($outDir)
$searchRoots.Add((Join-Path $RepoRoot 'workspace\logs'))
try { $searchRoots.Add((Get-Location).Path) } catch { }

$cutoff = $startedAt.AddSeconds(-5)
$candidates = @()
foreach ($root in ($searchRoots | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $root) {
        $candidates += @(Get-ChildItem -Path $root -Filter 'result.json' -Recurse -ErrorAction SilentlyContinue |
                         Where-Object { $_.LastWriteTime -ge $cutoff })
    }
}
$resultFiles = @($candidates | Sort-Object LastWriteTime -Descending | Select-Object -Unique)

$collectedPath = $null
if ($resultFiles.Count -gt 0) {
    $src = $resultFiles[0]
    Write-Host "[OK] result.json encontrado: $($src.FullName)"
    if ($resultFiles.Count -gt 1) {
        Write-Host "[INFO] $($resultFiles.Count) artefatos recentes; usando o mais novo."
    }
    # Copia (nunca move) para um lugar CANONICO dentro do repositorio:
    #   <repo>\workspace\logs\cli-probe\<teste>\collected\
    # Nao para <outDir>: desde o achado do t2, os testes com --scriptargs
    # gravam fora do repositorio (C:\mastertool-cli-probe\<teste>, sem
    # espacos), o que espalharia a evidencia por duas raizes diferentes e
    # obrigaria o verificador a receber varios --results-dir. Com o destino
    # canonico, `verify-cli-probe --results-dir workspace\logs\cli-probe`
    # enxerga os 5 testes de uma vez, independentemente de onde o probe
    # conseguiu gravar.
    $collectedDir = Join-Path $RepoRoot ("workspace\logs\cli-probe\" + $Test + "\collected")
    if (-not (Test-Path -LiteralPath $collectedDir)) {
        New-Item -ItemType Directory -Path $collectedDir -Force | Out-Null
    }
    $collectedPath = Join-Path $collectedDir 'result.json'
    if ($src.FullName -ne $collectedPath) {
        Copy-Item -LiteralPath $src.FullName -Destination $collectedPath -Force
        $srcReport = Join-Path $src.DirectoryName 'report.md'
        if (Test-Path -LiteralPath $srcReport) {
            Copy-Item -LiteralPath $srcReport -Destination (Join-Path $collectedDir 'report.md') -Force
        }
        Write-Host "[OK] Copiado para: $collectedPath (original preservado)"
    }
}
elseif ($Test -eq 't3') {
    Write-Host '[OK] Nenhum result.json - esperado em t3 (nenhum script foi passado).'
}
else {
    Write-Host '[AVISO] Nenhum result.json recente nas 3 camadas de gravacao.' -ForegroundColor Yellow
    Write-Host "        Procurado em: $($searchRoots -join ' | ')"
}

# --- observacao de host -----------------------------------------------------
$observation = [ordered]@{
    test                 = $Test
    executed_at          = $startedAt.ToString('o')
    finished_at          = $finishedAt.ToString('o')
    elapsed_seconds      = $elapsed
    exe                  = $Exe
    exe_file_version     = $exeVersion
    arguments            = $argList.ToArray()
    exit_code            = $exitCode
    orphan_process_ids   = @($orphans | ForEach-Object { $_.Id })
    orphan_processes     = $orphans.Count
    project_copy         = $ProjectCopy
    project_hash_before  = $hashBefore
    project_hash_after   = $hashAfter
    project_unchanged    = $projectUnchanged
    result_json_found    = ($resultFiles.Count -gt 0)
    result_json_path     = if ($resultFiles.Count -gt 0) { $resultFiles[0].FullName } else { $null }
    result_json_collected = $collectedPath
    output_dir            = $outDir
    output_dir_requested  = $outDirRequested
    output_dir_auto_switched = $outDirAutoSwitched
}
$obsPath = Join-Path $outDir 'host-observation.json'
$observation | ConvertTo-Json -Depth 5 | Out-File -FilePath $obsPath -Encoding utf8
Write-Host ''
Write-Host "[OK] Observacao de host gravada em: $obsPath"
Write-Host '[LEMBRETE] Anote em observation.md o que voce VIU na tela (dialogos, atrasos,'
Write-Host '           janelas inesperadas). Nenhum script consegue capturar isso por voce.'
