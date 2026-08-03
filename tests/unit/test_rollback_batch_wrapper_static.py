"""Verificação ESTÁTICA de `scripts/mastertool/run_rollback_batch.ps1`.

Não executa PowerShell, não abre o MasterTool.

POR QUE EXISTE UM LOTE SEPARADO
===============================
`run_repeatability_batch.ps1` manda **uma** spec para as N execuções, porque
numa qualificação de repetibilidade a entrada tem de ser idêntica — é o ponto
dela. Reversão não aceita isso: o `expected_before_sha256` de cada reversão é o
hash do texto que **uma saída específica** contém, e dez alterações produzem
dez saídas distintas. Dez reversões exigem dez specs inversas, dez alvos e dez
qualificações.

Rodar as dez contra uma spec única não seria um lote de reversões — seria a
mesma reversão reprovando nove vezes por `before_hash_mismatch`.
"""

import io
import os

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER = os.path.join(_REPO, "scripts", "mastertool", "run_rollback_batch.ps1")


@pytest.fixture(scope="module")
def texto():
    return io.open(WRAPPER, encoding="utf-8").read()


def test_o_wrapper_existe_e_e_legivel(texto):
    assert texto.strip()


def test_e_fail_closed_sem_execute(texto):
    """Wrapper que executa por omissão transforma engano de digitação em
    sessão de escrita."""
    assert "[switch]$Execute" in texto
    assert "if (-not $Execute)" in texto


def test_a_spec_inversa_e_EMITIDA_e_nao_escrita_aqui(texto):
    """O wrapper não sabe qual era o texto anterior, e não deve saber. Se ele
    montasse a spec, o `expected_before` deixaria de vir do plano."""
    assert "emit-rollback-spec" in texto
    assert "expected_before_sha256" not in texto.split("#>")[1]


def test_cada_run_tem_a_PROPRIA_spec_inversa(texto):
    """O invariante que separa este lote do de repetibilidade."""
    assert "SpecInversa  = Join-Path $origem 'rollback-spec.json'" in texto


def test_cada_alvo_tem_a_PROPRIA_qualificacao(texto):
    """Desde a amarração de 2026-08-02, reusar uma qualificação para dez alvos
    não é atalho — é recusa da fábrica."""
    assert "QualifDir    = Join-Path $origem 'qualif-alvo'" in texto
    assert "run_tmf_v1_qualification.ps1" in texto


def test_o_estagio_confere_a_FASE_antes_de_abrir_o_produto(texto):
    """O probe também recusa fase errada, e recusa depois de a janela abrir.
    Dez janelas para dez recusas idênticas é ruído; e no `prepare` uma fase de
    escrita aberta tornaria o "antes" medido inútil como antes."""
    assert "$mapaDeFases = @{" in texto
    assert texto.count("'prepare' = 'None'") == 2
    assert "'plan'    = '\"W10_REVERT\"'" in texto
    assert "'build'   = '\"W10_REVERT_VERIFY_BUILD\"'" in texto


def test_o_redo_roda_sob_a_fase_da_ALTERACAO_e_nao_numa_fase_nova(texto):
    """Desfazer a reversão NÃO é operação nova: a spec inversa da reversão tem
    `expected_before` = texto vazio e `text` = o texto da alteração — ou seja,
    é a alteração original sobre outra base.

    Dar-lhe fase própria (`W10_REVERT2`) faria a volta seguinte pedir
    `W10_REVERT3`, e assim por diante. O ciclo é fechado por DUAS operações,
    não por uma cadeia infinita delas."""
    assert "'plan'    = '\"W10_EDIT_EXISTING\"'" in texto
    assert "'build'   = '\"W10_VERIFY_BUILD\"'" in texto
    # `W10_REVERT2` pode ser MENCIONADO — o comentário existe para explicar por
    # que ele não existe. O que não pode é ser usado como fase.
    for linha in texto.splitlines():
        if "W10_REVERT2" in linha:
            assert linha.lstrip().startswith("#"), linha


def test_a_direcao_e_conjunto_FECHADO(texto):
    assert "[ValidateSet('undo', 'redo')]" in texto
    assert "[string]$Direction = 'undo'," in texto


def test_o_operation_id_acompanha_a_direcao(texto):
    """`w10-revert` e `w10-edit-existing` são listas fechadas no `probes/40`.
    Mandar o da direção errada reprova lá, e é onde tem de reprovar."""
    assert "$operationId = if ($Direction -eq 'undo')" in texto
    assert "'w10-revert' } else { 'w10-edit-existing' }" in texto
    assert "operation_id   = $operationId" in texto


def test_o_wrapper_LE_o_gate_e_nunca_o_escreve(texto):
    """Trocar de fase é decisão humana em commit isolado (`docs/28` §14). Um
    wrapper que abrisse a fase sozinho tornaria o commit isolado ficção.

    O teste é sobre o VERBO aplicado a `$safetyFile`: ele aparece só com
    `Select-String`, e nenhum cmdlet de escrita o toca."""
    assert "$safetyFile" in texto
    linhas = texto.splitlines()
    usos = [linha for linha in linhas if "$safetyFile" in linha]
    assert usos, "o wrapper deixou de conferir a fase"
    for linha in usos:
        assert ("Join-Path" in linha or "Select-String" in linha
                or "-LiteralPath $safetyFile" in linha), linha
    for escrita in ("Set-Content", "Add-Content", "Out-File", "WriteAllText"):
        for linha in linhas:
            if escrita in linha:
                assert "safety" not in linha, linha


def test_run_sem_before_texts_e_RECUSA_com_o_motivo(texto):
    """Uma run executada antes de o executor gravar o texto anterior não é
    reversível, e o diagnóstico tem de dizer isso — não "artefato ausente"."""
    assert "before-texts.json" in texto
    assert "reverter a partir do hash e impossivel" in texto


def test_nao_fixa_caminho_desta_maquina(texto):
    assert "C:\\\\Users\\\\Rankine" not in texto
    assert "C:\\Program Files\\Altus" not in texto
    assert "[Parameter(Mandatory = $true)]\n    [string]$Exe," in texto


def test_o_veredito_do_lote_nao_sai_do_host(texto):
    """Exit code do wrapper diz se o host falhou, nunca se a reversão deu
    certo. Quem decide é o artefato."""
    assert texto.count(
        "O veredito do lote NAO sai daqui: ele sai dos artefatos.") == 2


def test_nao_mata_processo_nem_usa_noUI(texto):
    assert "Stop-Process" not in texto
    assert "--noUI" not in texto
