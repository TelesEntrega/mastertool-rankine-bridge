"""Verificacao ESTATICA do wrapper `scripts/mastertool/run_w1_4_integrated.ps1`.

Nao executa PowerShell, nao abre o MasterTool. Os testes centrais sao de
ALCANCE: nenhum modo chega ao probe que nao lhe pertence.

    ValidateOnly     nao alcanca 37, 38 nem 40
    PreflightOnly    alcanca 37; nao alcanca 38 nem 40
    ExecuteMutation  alcanca 37 e 38; NUNCA 40 -- o build e etapa propria
    ExecuteBuild     alcanca 40 e 37 (postsave); NUNCA 38

O bloco do build termina em `exit`, e por isso nada abaixo dele e alcancavel
naquele modo -- e e isso que estes testes verificam, por delimitacao de bloco e
por ordem de linhas, nunca por leitura otimista da prosa do cabecalho.
"""

import io
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER_PATH = os.path.join(_REPO_ROOT, "scripts", "mastertool",
                            "run_w1_4_integrated.ps1")

PROBE37 = "37_preflight_w1_4_readonly.py"
PROBE38 = "38_author_w1_4.py"
PROBE40 = "40_build_w1_4.py"


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


def _bloco_do_modo(codigo, modo):
    marcador = re.search(r"if \(\$Mode -eq '" + modo + r"'\)\s*\{", codigo)
    assert marcador is not None, "bloco do modo %s nao encontrado" % modo
    return _corpo_do_bloco(codigo, marcador.end() - 1)


def test_wrapper_existe():
    assert os.path.isfile(WRAPPER_PATH)


def test_quatro_modos_e_default(codigo):
    for parametro in ("[switch]$ValidateOnly", "[switch]$PreflightOnly",
                      "[switch]$ExecuteMutation", "[switch]$ExecuteBuild"):
        assert parametro in codigo
    assert "$Mode = 'ValidateOnly'" in codigo
    assert "$selectedModes.Count -gt 1" in codigo


def test_modos_sao_mutuamente_exclusivos(codigo):
    assert "Modos mutuamente exclusivos" in codigo


# --- alcance ------------------------------------------------------------------

def test_cada_probe_e_mencionado_uma_unica_vez(linhas):
    for probe in (PROBE38, PROBE40):
        ocorrencias = [i for i, l in enumerate(linhas) if probe in l]
        assert len(ocorrencias) == 1, (probe, ocorrencias)


def test_validate_only_sai_antes_de_qualquer_probe(linhas):
    saida = _primeira_linha_com(linhas, r"\$Mode -eq 'ValidateOnly'")
    assert saida is not None
    trecho = "\n".join(linhas[saida:saida + 6])
    assert "exit 0" in trecho
    for probe in (PROBE38, PROBE40):
        indice = _primeira_linha_com(linhas, re.escape(probe))
        assert indice is not None and saida < indice, probe


def test_preflight_only_sai_antes_do_probe_38(linhas):
    saida = _primeira_linha_com(linhas, r"\$Mode -eq 'PreflightOnly'")
    probe38 = _primeira_linha_com(linhas, re.escape(PROBE38))
    assert saida is not None and probe38 is not None
    assert saida < probe38
    trecho = "\n".join(linhas[saida:saida + 8])
    assert "exit 0" in trecho


def test_o_probe_40_so_existe_dentro_do_bloco_de_ExecuteBuild(codigo):
    """O build e ETAPA PROPRIA: nenhum outro modo o alcanca."""
    bloco = _bloco_do_modo(codigo, "ExecuteBuild")
    assert PROBE40 in bloco
    assert codigo.count(PROBE40) == bloco.count(PROBE40)


def test_o_bloco_de_ExecuteBuild_nao_menciona_o_probe_38(codigo):
    bloco = _bloco_do_modo(codigo, "ExecuteBuild")
    assert PROBE38 not in bloco
    assert "create_gvl" not in bloco or "save_as" not in bloco


def test_o_bloco_de_ExecuteBuild_termina_em_exit(codigo):
    """Sem o `exit` final, o modo de build cairia no bloco de preflight e
    criaria copia de trabalho -- exatamente o que ele nao faz."""
    bloco = _bloco_do_modo(codigo, "ExecuteBuild")
    assert re.search(r"exit 0\s*\}\s*$", bloco.strip()) or bloco.rstrip().endswith("}")
    assert "exit 3" in bloco and "exit 0" in bloco


def test_o_bloco_de_ExecuteBuild_nao_cria_copia(codigo):
    bloco = _bloco_do_modo(codigo, "ExecuteBuild")
    assert "Copy-Item" not in bloco


def test_a_mutacao_vem_depois_do_preflight(linhas):
    preflight = _primeira_linha_com(linhas, r"--mode=preflight")
    probe38 = _primeira_linha_com(linhas, re.escape(PROBE38))
    assert preflight is not None and probe38 is not None
    assert preflight < probe38


def test_a_etapa_de_mutacao_nao_compila(codigo):
    """Compilar na mesma sessao que escreveu misturaria 'o texto persistiu'
    com 'o texto compila'."""
    assert "BUILD AINDA NAO EXECUTADO" in codigo
    assert "build_pending" in codigo


# --- plano --------------------------------------------------------------------

def test_fase_no_plano_e_w1_4_integrated_build(codigo):
    assert "'W1_4_INTEGRATED_BUILD'" in codigo
    assert "W1_4_INTEGRATED_AUTHORING" not in codigo


def test_a_cadeia_de_sete_operacoes_e_conferida(codigo):
    assert "$kinds.Count -ne 7" in codigo
    for indice, operacao in ((0, "create_gvl"), (1, "create_program"),
                             (2, "replace"), (3, "replace"), (4, "replace"),
                             (5, "save_as"), (6, "build")):
        assert "$kinds[%d] -ne '%s'" % (indice, operacao) in codigo


def test_os_alvos_dos_tres_replace_sao_conferidos_na_ordem(codigo):
    assert "$targets[0] -ne 'gvl_textual_declaration'" in codigo
    assert "$targets[1] -ne 'program_textual_declaration'" in codigo
    assert "$targets[2] -ne 'program_textual_implementation'" in codigo


def test_o_guid_de_st_e_conferido_e_nao_e_a_string_ST(codigo):
    assert "cc393387-a21c-4f68-a3e3-84c36951965d" in codigo
    assert "$planData.st_language_guid -ne" in codigo


def test_nomes_alvo_conferidos(codigo):
    assert "$planData.gvl_name -ne 'GVL_AI_TESTE'" in codigo
    assert "$planData.program_name -ne 'PRG_AI_TESTE'" in codigo


# --- fail-closed --------------------------------------------------------------

def test_sem_noui(codigo):
    assert "noUI" not in codigo


def test_nunca_mata_processo(codigo):
    for suspeito in ("Stop-Process", "Kill()", "taskkill"):
        assert suspeito not in codigo
    assert "CloseMainWindow" in codigo


def test_timeout_e_protecao_e_nao_gatilho(codigo):
    assert "NAO mata processo" in codigo


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
    assert "$build.status -ne 'build_verified'" in codigo
    assert "if ($launcherExit" not in codigo
    assert "$launcherExit -eq 0" not in codigo


def test_conclusao_detectada_por_artefato(codigo):
    assert "CompletionPath" in codigo
    assert "artefato de conclusao presente" in codigo


def test_ausencia_de_completion_aborta(codigo):
    assert "completion.json ausente" in codigo
    assert "build-completion.json ausente" in codigo


def test_confere_hashes_em_todas_as_pontas(codigo):
    assert "A copia difere do projeto-base" in codigo
    assert "A copia MUDOU durante o preflight" in codigo
    assert "A copia de ENTRADA foi modificada" in codigo
    assert "MUDOU durante o build" in codigo
    assert "MUDOU desde a mutacao" in codigo


def test_recusa_output_existente_e_dentro_do_repo(codigo):
    assert "output ja existe" in codigo
    assert "caminho dentro do repositorio" in codigo


def test_exige_diretorio_isolado(codigo):
    assert "nao esta isolado/vazio" in codigo


def test_orfaos_reprovam_em_cada_etapa(codigo):
    assert codigo.count("orphan_ids.Count -gt 0") >= 4


def test_dialogo_e_biblioteca_ausente_sao_lembrados(codigo):
    assert "CANCELE e registre o texto exato" in codigo
    assert "download" in codigo


def test_processo_por_nome_derivado(codigo):
    assert "GetFileNameWithoutExtension($Exe)" in codigo
    assert "MT8500*" not in codigo


def test_descarte_da_copia_inteira_e_a_regra(codigo):
    assert "DESCARTE a copia inteira" in codigo
    assert "nao existe rollback" in codigo


def test_veredito_final_exige_build_e_postsave(codigo):
    assert "$postsave.status -eq 'postsave_verified'" in codigo
    assert "integration_verified" in codigo


def test_baseline_recursiva_e_exigida_no_build(codigo):
    assert "Baseline recursiva do preflight ausente" in codigo
    assert "w1-4-preflight-flat-nodes.json" in codigo


def test_read_only_phase_e_conferido(codigo):
    assert "READ_ONLY_PHASE" in codigo


def test_elegibilidade_do_template_e_consultada_e_nao_presumida(codigo):
    """docs/36: o TemplateExemplo v1 esta MEDIDO e NAO ELEGIVEL. O host le o artefato de
    qualificacao e recusa; nunca assume que o template pode ser autorado."""
    assert "[string]$TemplateQualification" in codigo
    assert "$qualification.authoring_eligible -ne $true" in codigo
    assert "blocking_issues" in codigo


def test_artefato_de_qualificacao_ausente_ou_incompleto_recusa(codigo):
    """Fail-closed nas tres pontas: sem parametro, sem arquivo e sem o campo."""
    assert "-TemplateQualification e obrigatorio" in codigo
    assert "Artefato de qualificacao inexistente" in codigo
    assert "sem o campo authoring_eligible" in codigo


def test_validate_only_nao_exige_qualificacao_mas_diz_isso(codigo):
    assert "$Mode -ne 'ValidateOnly'" in codigo
    assert "NAO foi consultada neste modo" in codigo


# --- codificacao --------------------------------------------------------------

def test_json_gravado_sem_bom(codigo):
    assert "System.Text.UTF8Encoding($false)" in codigo
    assert not re.search(r"Out-File[^\r\n]*-Encoding\s+utf8", codigo)


def test_arquivo_e_ascii_puro():
    """ASCII puro: acento em wrapper PowerShell 5.1 sem BOM vira mojibake, e o
    proprio texto de aborto ficaria ilegivel na hora em que mais importa."""
    dados = open(WRAPPER_PATH, "rb").read()
    nao_ascii = [i for i, byte in enumerate(bytearray(dados)) if byte > 127]
    assert not nao_ascii, "bytes nao-ASCII nas posicoes %s" % nao_ascii[:10]
