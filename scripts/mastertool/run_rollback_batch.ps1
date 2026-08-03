<#
  run_rollback_batch.ps1 -- lote de REVERSOES independentes.

  POR QUE ESTE ARQUIVO EXISTE, E POR QUE NAO E O LOTE DE REPETIBILIDADE
  ====================================================================
  `run_repeatability_batch.ps1` manda UMA spec para as N execucoes, porque numa
  qualificacao de repetibilidade a entrada tem de ser identica -- e isso e o
  ponto dela.

  Reversao nao aceita isso. O `expected_before_sha256` de cada reversao e o
  hash do texto que UMA saida especifica contem, e dez alteracoes produzem dez
  saidas distintas (o `.project` carrega GUID e timestamp). Logo: dez specs
  inversas, dez alvos, dez qualificacoes. Rodar as dez contra uma unica spec
  nao seria um lote de reversoes -- seria a mesma reversao reprovando nove
  vezes por `before_hash_mismatch`, que e exatamente o que a conferencia serve
  para dizer.

  A spec inversa NAO e escrita aqui. Ela e EMITIDA por
  `mastertool-bridge emit-rollback-spec` a partir do plano da ida e do
  `before-texts.json` que o executor gravou. Este wrapper nao sabe qual era o
  texto anterior, e nao deve saber.

  TRES ESTAGIOS, e o gate muda entre eles
  =======================================
    prepare  emite a spec inversa e QUALIFICA o alvo. Somente leitura, e
             RECUSA rodar com fase de escrita aberta.
    plan     aplica a spec inversa.
    build    compila e verifica.

  As fases de `plan` e `build` dependem de `-Direction` -- ver o comentario
  do parametro.

  Trocar de fase e decisao humana em commit isolado (`docs/28` secao 14), entao
  o wrapper faz um estagio por vez e nunca mexe no gate.

  USO:
    .\run_rollback_batch.ps1 -SourceRoot <lote-de-alteracoes> -Stage prepare -Execute -Exe <mt.exe>
    .\run_rollback_batch.ps1 -SourceRoot <...> -OutputRoot <...> -Stage plan  -Execute -Exe <mt.exe>
    .\run_rollback_batch.ps1 -SourceRoot <...> -OutputRoot <...> -Stage build -Execute -Exe <mt.exe>
#>

param(
    # Raiz do lote de ALTERACOES ja executado: espera-se `run-001`, `run-002`,
    # ... cada uma com `artefatos/` e `saida/FABRICA.project`.
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,

    # Onde as runs de REVERSAO vivem. Em `prepare` e opcional: nada e criado la.
    [string]$OutputRoot,

    [Parameter(Mandatory = $true)]
    [ValidateSet('prepare', 'plan', 'build')]
    [string]$Stage,

    # DIRECAO DA APLICACAO. As duas usam a MESMA maquinaria -- uma spec inversa
    # emitida de um plano e do texto anterior -- e diferem no que significam:
    #
    #   undo  desfaz uma alteracao aceita. Fase propria (`W10_REVERT`), porque
    #         desfazer nao e um detalhe da sessao que fez.
    #
    #   redo  desfaz a reversao. E aqui esta o achado: isso NAO e uma operacao
    #         nova. A spec inversa da reversao tem `expected_before` = texto
    #         vazio e `text` = o texto da alteracao -- exatamente a alteracao
    #         original, sobre outra base. Roda sob `W10_EDIT_EXISTING`, a fase
    #         que ja significa "aplicar este texto a um objeto preexistente".
    #
    # Dar a `redo` uma fase propria (`W10_REVERT2`) tornaria a proxima volta
    # `W10_REVERT3`, e assim por diante. O ciclo e fechado por DUAS operacoes,
    # nao por uma cadeia infinita delas, e a nomenclatura tem de dizer isso.
    # O que distingue as runs no registro nao e o nome da fase: sao o hash da
    # spec, o do plano e o do alvo, todos gravados.
    [ValidateSet('undo', 'redo')]
    [string]$Direction = 'undo',

    [int]$Runs = 10,

    # Sem isto, o script so lista o que faria.
    [switch]$Execute,

    # SEM DEFAULT: ver o mesmo comentario em `run_repeatability_batch.ps1`.
    # Fixar o caminho de instalacao aqui faria a divida da catraca CRESCER.
    [Parameter(Mandatory = $true)]
    [string]$Exe,

    [string]$RepoRoot,
    [int]$TimeoutSeconds = 900,
    [switch]$AutoCloseWindow
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

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

Write-Section "Lote de REVERSOES -- estagio '$Stage', N = $Runs"

if (-not [IO.Path]::IsPathRooted($SourceRoot)) { Fail '-SourceRoot deve ser absoluto' }
if (-not (Test-Path -LiteralPath $SourceRoot)) { Fail "SourceRoot inexistente: $SourceRoot" }
if ($Runs -lt 2) { Fail '-Runs < 2 nao e lote' }

if ($Stage -ne 'prepare') {
    if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
        Fail '-OutputRoot e obrigatorio fora de -Stage prepare'
    }
    if ($OutputRoot -match '\s') {
        Fail "-OutputRoot com espaco: $OutputRoot. --scriptargs quebra em espaco."
    }
}

$safetyFile = Join-Path $RepoRoot 'scripts\mastertool\common\safety.py'
$faseLinha = Select-String -LiteralPath $safetyFile `
    -Pattern '^CONTROLLED_WRITE_PHASE\s*=\s*(.+)$'
$faseAtual = if ($faseLinha) { $faseLinha.Matches[0].Groups[1].Value.Trim() } else { 'None' }

# ESTAGIO x FASE, conferido AQUI e nao so no probe.
#
# O probe recusa fase errada, e recusa DEPOIS de o produto abrir. Conferir
# antes evita dez janelas abrindo para dez recusas identicas -- e, no
# `prepare`, evita medir um "antes" com janela de escrita aberta, que nao serve
# de antes.
$mapaDeFases = @{
    'undo' = @{
        'prepare' = 'None'
        'plan'    = '"W10_REVERT"'
        'build'   = '"W10_REVERT_VERIFY_BUILD"'
    }
    'redo' = @{
        'prepare' = 'None'
        'plan'    = '"W10_EDIT_EXISTING"'
        'build'   = '"W10_VERIFY_BUILD"'
    }
}
$faseEsperada = $mapaDeFases[$Direction][$Stage]
$operationId = if ($Direction -eq 'undo') { 'w10-revert' } else { 'w10-edit-existing' }
$faseDeBuild = if ($Direction -eq 'undo') { 'W10_REVERT_VERIFY_BUILD' } else { 'W10_VERIFY_BUILD' }
Write-Host "[OK] Direcao     : $Direction (operation_id '$operationId')"
if ($faseAtual -ne $faseEsperada) {
    Fail ("Estagio '$Stage' exige CONTROLLED_WRITE_PHASE = $faseEsperada, e o " +
          "codigo tem $faseAtual. Trocar de fase e commit isolado.")
}
Write-Host "[OK] CONTROLLED_WRITE_PHASE = $faseAtual (esperado para '$Stage')"

if (-not (Test-Path -LiteralPath $Exe)) { Fail "Executavel nao encontrado: $Exe" }
Write-Host "[OK] Executavel  : $Exe"

$fabrica = Join-Path $RepoRoot 'scripts\mastertool\run_project_factory.ps1'
$qualificador = Join-Path $RepoRoot 'scripts\mastertool\run_tmf_v1_qualification.ps1'
$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
foreach ($caminho in @($fabrica, $qualificador, $python)) {
    if (-not (Test-Path -LiteralPath $caminho)) { Fail "Nao encontrado: $caminho" }
}

# ---------------------------------------------------------------------------
# As vagas: uma por run da ida.
# ---------------------------------------------------------------------------
$vagas = @()
for ($i = 1; $i -le $Runs; $i++) {
    $id = 'run-{0:D3}' -f $i
    $origem = Join-Path $SourceRoot $id
    $vaga = [pscustomobject]@{
        RunId        = $id
        Origem       = $origem
        Plano        = Join-Path $origem 'artefatos\authoring-plan.json'
        BeforeTexts  = Join-Path $origem 'artefatos\execucao\before-texts.json'
        Saida        = Join-Path $origem 'saida\FABRICA.project'
        SpecInversa  = Join-Path $origem 'rollback-spec.json'
        QualifDir    = Join-Path $origem 'qualif-alvo'
        QualifJson   = Join-Path $origem 'qualif-alvo\artifacts\qualify-analysis.json'
        Destino      = if ($OutputRoot) { Join-Path $OutputRoot $id } else { $null }
    }
    $vagas += $vaga
    Write-Host ("  {0} <- {1}" -f $id, $origem)
}

foreach ($vaga in $vagas) {
    if (-not (Test-Path -LiteralPath $vaga.Saida)) {
        Fail ("$($vaga.RunId): saida da ida inexistente: $($vaga.Saida). O lote " +
              "de alteracoes precisa ter rodado antes.")
    }
    if ($Stage -eq 'prepare') {
        if (-not (Test-Path -LiteralPath $vaga.BeforeTexts)) {
            Fail ("$($vaga.RunId): sem `before-texts.json`. Esta run foi " +
                  "executada por um executor que ainda nao gravava o texto " +
                  "anterior, e reverter a partir do hash e impossivel.")
        }
    }
}

Write-Section 'VALIDACAO APROVADA'
if (-not $Execute) {
    Write-Host 'Ensaio: nada foi aberto e nada foi gravado. Use -Execute.'
    exit 0
}

# ---------------------------------------------------------------------------
# EXECUCAO
# ---------------------------------------------------------------------------
$falhas = @()

foreach ($vaga in $vagas) {
    Write-Section "Executando $($vaga.RunId)"

    if ($Stage -eq 'prepare') {
        $saidaSha = (Get-FileHash -LiteralPath $vaga.Saida -Algorithm SHA256).Hash.ToLower()
        Write-Host "[INFO] alvo da reversao: $saidaSha"

        & $python -m mastertool_bridge.cli emit-rollback-spec `
            --plan $vaga.Plano `
            --before-texts $vaga.BeforeTexts `
            --target-project-sha256 $saidaSha `
            --output $vaga.SpecInversa
        if ($LASTEXITCODE -ne 0) {
            $falhas += "$($vaga.RunId): emit-rollback-spec saiu $LASTEXITCODE"
            continue
        }

        # QUALIFICACAO POR ALVO, e nao uma para todas. Desde 2026-08-02 a
        # fabrica confere que a qualificacao e DESTE arquivo, entao reusar uma
        # so nao seria atalho: seria recusa.
        $tamanho = (Get-Item -LiteralPath $vaga.Saida).Length
        $argumentos = @{
            BaseProject          = $vaga.Saida
            ExpectedBaseSha256   = $saidaSha
            ExpectedBaseSizeBytes = $tamanho
            WorkDir              = $vaga.QualifDir
            Execute              = $true
            Exe                  = $Exe
            RepoRoot             = $RepoRoot
            TimeoutSeconds       = $TimeoutSeconds
        }
        if ($AutoCloseWindow) { $argumentos['AutoCloseWindow'] = $true }
        & $qualificador @argumentos
        if ($LASTEXITCODE -ne 0) {
            $falhas += "$($vaga.RunId): qualificacao do alvo saiu $LASTEXITCODE"
        }
        continue
    }

    $argumentos = @{
        Spec                  = $vaga.SpecInversa
        WorkRoot              = $vaga.Destino
        TemplateQualification = $vaga.QualifJson
        Exe                   = $Exe
        RepoRoot              = $RepoRoot
        TimeoutSeconds        = $TimeoutSeconds
    }
    if ($AutoCloseWindow) { $argumentos['AutoCloseWindow'] = $true }

    if ($Stage -eq 'plan') {
        $argumentos['ExecutePlan'] = $true
        $argumentos['TemplateProject'] = $vaga.Saida
    }
    else {
        $planoBuild = Join-Path $vaga.Destino 'build-plan.json'
        $conteudo = [ordered]@{
            schema_version = '1.0'
            operation_id   = $operationId
            phase          = $faseDeBuild
            run_id         = ($vaga.RunId + '-' + $Direction + '-build')
            output_project = [ordered]@{
                path = (Join-Path $vaga.Destino 'saida\FABRICA.project') }
            artifacts_dir  = (Join-Path $vaga.Destino 'artefatos')
            container      = [ordered]@{
                node_path          = 'root/1/0/0'
                expected_name      = 'Application'
                expected_type_guid = '639b491f-5557-464c-af91-1471bac9f549'
            }
            mastertool     = [ordered]@{ version = '4.1.0.11'; script_engine = '4.2.0.0' }
            operations     = @([ordered]@{ kind = 'build' })
            notes          = 'Gerado por run_rollback_batch.ps1. NAO versionar.'
        }
        [System.IO.File]::WriteAllText(
            $planoBuild, ($conteudo | ConvertTo-Json -Depth 6),
            (New-Object System.Text.UTF8Encoding($false)))
        $argumentos['ExecuteBuild'] = $true
        $argumentos['BuildPlan'] = $planoBuild
    }

    & $fabrica @argumentos
    if ($LASTEXITCODE -ne 0) {
        $falhas += "$($vaga.RunId): fabrica saiu $LASTEXITCODE"
    }
}

Write-Section "VEREDITO DO ESTAGIO '$Stage'"
if ($falhas.Count -gt 0) {
    Write-Host "[FALHAS] $($falhas.Count) de $($vagas.Count):" -ForegroundColor Yellow
    foreach ($f in $falhas) { Write-Host "  - $f" }
    Write-Host '[INFO] O veredito do lote NAO sai daqui: ele sai dos artefatos.'
    exit 3
}
Write-Host "[OK] $($vagas.Count) run(s) sem falha de host."
Write-Host '[INFO] O veredito do lote NAO sai daqui: ele sai dos artefatos.'
exit 0
