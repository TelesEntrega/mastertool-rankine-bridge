"""Verificacao ESTATICA do wrapper `scripts/mastertool/run_w1_2_create_program.ps1`.

Nao executa PowerShell, nao abre o MasterTool. O teste central e o de ALCANCE:
`ValidateOnly` e `PreflightOnly` terminam com `exit 0` ANTES da primeira mencao
ao probe 30, e isso se verifica por ordem de linhas.
"""

import io
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER_PATH = os.path.join(_REPO_ROOT, "scripts", "mastertool",
                            "run_w1_2_create_program.ps1")


@pytest.fixture(scope="module")
def linhas():
    return io.open(WRAPPER_PATH, encoding="utf-8-sig").read().split("\n")


@pytest.fixture(scope="module")
def codigo():
    """Somente codigo: sem o bloco `<# ... #>` e sem linha de comentario. A
    prosa do cabecalho promete coisas ("Nunca usa --noUI") e uma busca literal
    no arquivo inteiro acusaria a propria promessa."""
    bruto = io.open(WRAPPER_PATH, encoding="utf-8-sig").read()
    sem_ajuda = re.sub(r"<#.*?#>", "", bruto, flags=re.S)
    return "\n".join([re.sub(r"(?<!`)#.*$", "", l) for l in sem_ajuda.split("\n")])


def _primeira_linha_com(linhas, padrao):
    expressao = re.compile(padrao)
    for indice, linha in enumerate(linhas):
        if expressao.search(linha):
            return indice
    return None


def _corpo_do_bloco(codigo, indice_da_chave):
    profundidade = 0
    posicao = indice_da_chave
    while posicao < len(codigo):
        if codigo[posicao] == "{":
            profundidade = profundidade + 1
        elif codigo[posicao] == "}":
            profundidade = profundidade - 1
            if profundidade == 0:
                return codigo[indice_da_chave:posicao + 1]
        posicao = posicao + 1
    return codigo[indice_da_chave:]


def test_wrapper_existe():
    assert os.path.isfile(WRAPPER_PATH)


def test_tres_modos_e_default(codigo):
    for parametro in ("[switch]$ValidateOnly", "[switch]$PreflightOnly",
                      "[switch]$ExecuteMutation"):
        assert parametro in codigo
    assert "$Mode = 'ValidateOnly'" in codigo
    assert "$selectedModes.Count -gt 1" in codigo


def test_probe_30_mencionado_uma_vez(linhas):
    ocorrencias = [i for i, l in enumerate(linhas) if "30_create_program_w1_2.py" in l]
    assert len(ocorrencias) == 1, ocorrencias


@pytest.mark.parametrize("modo", ["ValidateOnly", "PreflightOnly"])
def test_modo_sai_antes_do_probe_30(linhas, modo):
    saida = _primeira_linha_com(linhas, r"\$Mode -eq '" + modo + r"'")
    probe30 = _primeira_linha_com(linhas, r"30_create_program_w1_2\.py")
    assert saida is not None and probe30 is not None
    assert saida < probe30
    trecho = "\n".join(linhas[saida:saida + 8])
    assert "exit 0" in trecho


def test_preflight_verde_e_condicao(codigo):
    assert "$preflight.status -ne 'preflight_passed'" in codigo


def test_guid_medido_confere_com_o_plano(codigo):
    """Se a medicao contradiz o plano, a sessao para -- o plano nao antecipa o
    que o runtime desmente."""
    assert "$preflight.st_language_guid -ne $stGuid" in codigo


def test_sem_noui(codigo):
    assert "noUI" not in codigo


def test_nunca_mata_processo(codigo):
    """CloseMainWindow e o equivalente a clicar no X. Stop-Process e matar, e
    docs/28 secao 7 proibe."""
    for suspeito in ("Stop-Process", "Kill()", "taskkill"):
        assert suspeito not in codigo
    assert "CloseMainWindow" in codigo


def test_sem_retry_nem_fallback_de_lancamento(codigo):
    lancamentos = [m.start() for m in re.finditer(r"Invoke-MasterTool", codigo)]
    assert lancamentos
    for construcao in (r"while\s*\([^)]*\)\s*\{", r"for\s*\([^)]*\)\s*\{",
                       r"foreach\s*\([^)]*\)\s*\{", r"catch\s*\{"):
        for encontrado in re.finditer(construcao, codigo):
            trecho = _corpo_do_bloco(codigo, encontrado.end() - 1)
            assert "Invoke-MasterTool" not in trecho, construcao
    assert re.search(r"function Fail\([^)]*\)\s*\{[^}]*exit 2", codigo, re.S)


def test_sem_fallback_de_executavel(codigo):
    assert "$exeVersion -ne $ExpectedExeVersion" in codigo
    assert "MT8500.exe" not in codigo


def test_exit_code_do_launcher_nao_decide(codigo):
    assert "$completion.status -ne 'saved_as'" in codigo
    assert "$postsave.status -eq 'postsave_verified'" in codigo
    assert "if ($launcherExit" not in codigo
    assert "$launcherExit -eq 0" not in codigo


def test_conclusao_detectada_por_artefato(codigo):
    assert "CompletionPath" in codigo
    assert "artefato de conclusao presente" in codigo


def test_ausencia_de_completion_aborta(codigo):
    assert "completion.json ausente" in codigo


def test_confere_hashes(codigo):
    assert "A copia difere do projeto-base" in codigo
    assert "A copia MUDOU durante o preflight" in codigo
    assert "A copia de ENTRADA foi modificada" in codigo


def test_recusa_output_existente_e_dentro_do_repo(codigo):
    assert "output ja existe" in codigo
    assert "caminho dentro do repositorio" in codigo


def test_exige_diretorio_isolado(codigo):
    assert "nao esta isolado/vazio" in codigo


def test_postsave_reabre_o_salvo(codigo):
    assert "-ProjectPath $outputPath" in codigo
    assert "--mode=postsave" in codigo


def test_text_read_gap_nao_e_aprovado(codigo):
    assert "PENDENTE DE REVISAO HUMANA" in codigo
    assert "'text_read_gap'" in codigo


def test_processo_por_nome_derivado(codigo):
    assert "GetFileNameWithoutExtension($Exe)" in codigo
    assert "MT8500*" not in codigo


def test_arquivo_legivel_pelo_powershell_5_1():
    dados = open(WRAPPER_PATH, "rb").read()
    tem_bom = dados[:3] == b"\xef\xbb\xbf"
    e_ascii = all(byte < 128 for byte in bytearray(dados))
    assert tem_bom or e_ascii
