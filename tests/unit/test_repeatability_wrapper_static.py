"""Verificação ESTÁTICA do wrapper de lote da fase R1.

O wrapper abre o MasterTool, então nenhum teste o executa. O que se verifica é
o que dá para verificar lendo o arquivo: que ele é fail-closed, que não fixa
caminho desta máquina e que o veredito do lote não vem da última execução.
"""

import io
import os
import re

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER = os.path.join(_REPO, "scripts", "mastertool",
                       "run_repeatability_batch.ps1")


def _texto():
    return io.open(WRAPPER, encoding="utf-8").read()


def test_o_wrapper_existe_e_e_legivel():
    assert os.path.isfile(WRAPPER)
    assert _texto().strip()


def test_e_fail_closed_sem_execute():
    """Wrapper que executa por omissão transforma engano de digitação em
    sessão de escrita."""
    texto = _texto()
    assert "[switch]$Execute" in texto
    assert "if (-not $Execute)" in texto
    assert "[SECO]" in texto


def test_nao_fixa_caminho_desta_maquina():
    """A catraca de dívida só pode encolher. Um wrapper novo com os mesmos
    literais dos doze antigos faria a dívida crescer -- e este teste é o que
    impede que isso passe por descuido."""
    import sys

    ferramentas = os.path.join(_REPO, "tools")
    if ferramentas not in sys.path:
        sys.path.insert(0, ferramentas)
    import check_repo_hygiene as hygiene  # noqa: E402

    # Usa o PRÓPRIO verificador, e não uma busca paralela: duas
    # implementações da mesma regra divergiriam, e a que envelheceria seria
    # justamente esta.
    achados = hygiene.find_local_path_findings(
        "scripts/mastertool/run_repeatability_batch.ps1", _texto())
    assert achados == [], [a.message for a in achados]

    # E a raiz é derivada, não escrita.
    texto = _texto()
    assert "$PSScriptRoot" in texto
    assert not re.search(r"RepoRoot\s*=\s*'[A-Za-z]:", texto)
    assert not re.search(r"\$Exe\s*=\s*'[A-Za-z]:", texto)


def test_recusa_lote_menor_que_dois():
    assert "$Runs -lt 2" in _texto()


def test_recusa_saida_preexistente_antes_de_executar():
    """Reaproveitar saída transformaria N execuções em uma execução e N-1
    leituras do mesmo resultado."""
    texto = _texto()
    assert "run-*" in texto
    assert "RECUSADO" in texto
    posicao_recusa = texto.index("ja contem diretorio")
    posicao_execucao = texto.index("foreach ($vaga in $plano)")
    assert posicao_recusa < posicao_execucao


def test_continua_depois_de_falha():
    """Parar na primeira falha destruiria a evidência que separa falha
    isolada de falha sistemática."""
    texto = _texto()
    assert "O lote continua" in texto


def test_o_veredito_do_lote_nao_e_o_da_ultima_execucao():
    """Um lote em que todas as runs terminam bem e cujo conjunto diverge
    continua sendo um lote reprovado."""
    texto = _texto()
    assert "exit $vereditoCodigo" in texto
    assert "qualify-repeatability" in texto


def test_a_numeracao_tem_largura_fixa():
    """`run-001`, e não `run-1`: a ordem lexicográfica dos diretórios passa a
    coincidir com a ordem de execução."""
    assert "'run-{0:d3}'" in _texto()


# =============================================================================
# os dois estágios -- a correção que a leitura do wrapper da fábrica exigiu
# =============================================================================

def test_o_wrapper_tem_dois_estagios():
    """`-ExecutePlan` e `-ExecuteBuild` são modos mutuamente exclusivos da
    fábrica, e rodam sob FASES diferentes. Uma passada só não existe."""
    texto = _texto()
    assert "ValidateSet('plan', 'build')" in texto
    assert "$Stage" in texto


def test_o_estagio_plan_nao_emite_veredito():
    """A verificação (probe 47) roda dentro do -ExecuteBuild. Um lote só de
    planos não produz `verificacao/`, e emitir veredito ali diria "árvore
    ausente" sobre um lote perfeitamente bom."""
    texto = _texto()
    assert "NAO ha veredito ainda, e isso nao e omissao" in texto
    posicao_saida = texto.index("Estagio `plan` encerrado")
    posicao_veredito = texto.index("Veredito do LOTE")
    assert posicao_saida < posicao_veredito


def test_o_estagio_build_opera_sobre_a_saida_da_propria_run():
    """`-BuildPlan` é obrigatório em -ExecuteBuild, e cada run compila a saída
    que ela mesma produziu — nunca a de outra."""
    texto = _texto()
    assert "$vaga.WorkDir 'saida\\FABRICA.project'" in texto
    assert "ExecuteBuild" in texto


def test_o_estagio_build_exige_o_que_o_plan_produziu():
    """Exigir ausência de `run-*` no estágio build seria a regra do estágio
    errado."""
    texto = _texto()
    assert "precisa de $Runs diretorio(s)" in texto


def test_o_estagio_build_GERA_o_plano_de_build():
    """ACHADO do piloto: `-BuildPlan` não é o plano de autoria.

    O probe 40 espera outro documento — `operations: [{kind: build}]`, fase
    própria, caminho do projeto de saída — e o wrapper da fábrica compara
    `output_project.path` com o que a execução produziu. Passar o plano de
    autoria reprovou as três runs.

    Historicamente esses arquivos eram escritos à mão, um por run. Num lote de
    N execuções seriam N arquivos manuais, e cada um uma chance de apontar
    para a run errada."""
    texto = _texto()
    assert "build-plan.json" in texto
    assert "kind = 'build'" in texto
    # A identidade da fase é PARÂMETRO: um lote com spec que cria task usa
    # `w9-prove-task-timing`/`W9_VERIFY_BUILD`, e fixá-la aqui obrigaria a
    # editar o wrapper a cada fase nova.
    assert "$OperationId" in texto
    assert "$BuildPhase" in texto
    assert "operation_id   = $OperationId" in texto
    assert "phase          = $BuildPhase" in texto
    assert r"saida\FABRICA.project" in texto


def test_o_plano_de_build_gerado_e_UTF8_sem_BOM():
    """`Out-File -Encoding utf8` grava BOM no PowerShell 5.1, e leitor estrito
    de JSON morre em `Unexpected UTF-8 BOM`."""
    texto = _texto()
    assert "UTF8Encoding($false)" in texto
    assert "WriteAllText" in texto


def test_a_divida_posicional_do_probe_40_esta_declarada():
    """`container.node_path` continua posicional porque o probe 40 não foi
    migrado na R0b. Fica registrado, não silenciado."""
    texto = _texto()
    assert "root/1/0/0" in texto
    assert "POSICIONAL" in texto
    assert "divida" in texto or "dívida" in texto
