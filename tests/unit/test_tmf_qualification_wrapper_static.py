"""Verificacao ESTATICA do wrapper
`scripts/mastertool/run_tmf_v1_qualification.ps1`.

Nao executa PowerShell, nao abre o MasterTool. A garantia central e que o
wrapper e um instrumento SOMENTE LEITURA: nenhuma escrita, nenhum
Stop-Process, nenhum --noUI, conclusao sempre pelo artefato, e os dois modos
mutuamente exclusivos com o default fail-closed (nada aberto).
"""

import io
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER_PATH = os.path.join(_REPO_ROOT, "scripts", "mastertool",
                            "run_tmf_v1_qualification.ps1")


@pytest.fixture(scope="module")
def linhas():
    return io.open(WRAPPER_PATH, encoding="utf-8-sig").read().split("\n")


@pytest.fixture(scope="module")
def codigo():
    """Somente codigo: sem o bloco `<# ... #>` e sem linha de comentario --
    a prosa do cabecalho promete coisas ("Nunca usa --noUI") e uma busca
    literal no arquivo inteiro acusaria a propria promessa."""
    bruto = io.open(WRAPPER_PATH, encoding="utf-8-sig").read()
    sem_ajuda = re.sub(r"<#.*?#>", "", bruto, flags=re.S)
    return "\n".join([re.sub(r"(?<!`)#.*$", "", l) for l in sem_ajuda.split("\n")])


def test_wrapper_existe():
    assert os.path.isfile(WRAPPER_PATH)


def test_dois_modos_e_default(codigo):
    for parametro in ("[switch]$ValidateOnly", "[switch]$Execute"):
        assert parametro in codigo
    assert "$Mode = 'ValidateOnly'" in codigo
    assert "$selectedModes.Count -gt 1" in codigo


def test_probe_35_mencionado_uma_vez(linhas):
    ocorrencias = [i for i, l in enumerate(linhas)
                  if "35_qualify_template_readonly.py" in l]
    assert len(ocorrencias) == 1, ocorrencias


def test_modo_validateonly_sai_antes_da_execucao(linhas):
    """O caminho do probe 35 e VALIDADO (Test-Path) dentro do bloco 1, antes
    do exit do ValidateOnly -- isso e esperado, um wrapper fail-closed
    confere que o probe existe mesmo sem executar nada. O que NUNCA pode
    acontecer antes do exit do ValidateOnly e o LANCAMENTO do MasterTool
    (Invoke-MasterTool com -ProbePath $probe35)."""
    saida = None
    lancamento = None
    for i, l in enumerate(linhas):
        if re.search(r"\$Mode -eq 'ValidateOnly'", l):
            saida = i
        if "-ProbePath $probe35" in l:
            lancamento = i
    assert saida is not None and lancamento is not None
    assert saida < lancamento
    trecho = "\n".join(linhas[saida:saida + 8])
    assert "exit 0" in trecho


def test_sem_noui(codigo):
    assert "noUI" not in codigo


def test_nunca_mata_processo(codigo):
    for suspeito in ("Stop-Process", "Kill()", "taskkill"):
        assert suspeito not in codigo
    assert "CloseMainWindow" in codigo


def test_sem_fallback_de_executavel(codigo):
    assert "$exeVersion -ne $ExpectedExeVersion" in codigo
    assert "MT8500.exe" not in codigo


def test_exit_code_do_launcher_nao_decide(codigo):
    assert "$launcherExit" in codigo
    assert "if ($launcherExit" not in codigo
    assert "$launcherExit -eq 0" not in codigo


def test_conclusao_detectada_por_artefato(codigo):
    assert "CompletionPath" in codigo
    assert "artefato de conclusao presente" in codigo


def test_ausencia_de_completion_aborta(codigo):
    assert "qualify-completion.json ausente" in codigo


def test_confere_hash_da_base_e_do_tamanho(codigo):
    assert "ExpectedBaseSha256" in codigo
    assert "ExpectedBaseSizeBytes" in codigo
    assert "baseInfo.Length -ne $ExpectedBaseSizeBytes" in codigo
    assert "SHA-256 do projeto-base diverge do valor medido e congelado" in codigo


def test_confere_copia_e_base_apos_execucao(codigo):
    """Read-only tem de provar que NADA mudou -- nem a copia, nem o
    original -- depois da execucao."""
    assert "A copia MUDOU durante a qualificacao" in codigo
    assert "O PROJETO-BASE ORIGINAL foi tocado" in codigo


def test_recusa_workdir_com_espaco(codigo):
    assert "WorkDir -match '\\s'" in codigo
    assert "O MasterTool quebra --scriptargs" in codigo


def test_recusa_workdir_dentro_do_repo(codigo):
    assert "WorkDir dentro do repositorio" in codigo


def test_exige_workdir_isolado(codigo):
    assert "nao esta isolado/vazio" in codigo


def test_verifica_read_only_phase(codigo):
    assert "READ_ONLY_PHASE" in codigo
    assert "safety.py" in codigo


def test_processo_por_nome_derivado(codigo):
    assert "GetFileNameWithoutExtension($Exe)" in codigo
    assert "MT8500*" not in codigo


def test_nenhum_mutador_do_masterpool_no_wrapper(codigo):
    """O wrapper e um instrumento read-only: nenhuma das operacoes mutaveis
    do MasterTool X pode aparecer como argumento de operacao neste arquivo."""
    for mutador in ("create_gvl", "create_program", "create_pou", "replace(",
                    "save_as(", "'build'", "\"build\""):
        assert mutador not in codigo, mutador


def test_arquivo_legivel_pelo_powershell_5_1():
    dados = open(WRAPPER_PATH, "rb").read()
    tem_bom = dados[:3] == b"\xef\xbb\xbf"
    e_ascii = all(byte < 128 for byte in bytearray(dados))
    assert tem_bom or e_ascii


def test_arquivo_ascii_puro():
    """Requisito explicito do contrato: PowerShell 5.1 le .ps1 sem BOM como
    ANSI -- nada de travessoes, acentos ou simbolos fora do ASCII."""
    dados = open(WRAPPER_PATH, "rb").read()
    assert all(byte < 128 for byte in bytearray(dados))


def test_grava_artefato_por_utf8_sem_bom(codigo):
    assert "System.Text.UTF8Encoding($false)" in codigo
    assert "[System.IO.File]::WriteAllText" in codigo
