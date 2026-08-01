"""Verificacao ESTATICA do wrapper `scripts/mastertool/run_w1_1_create_gvl.ps1`.

Nao executa PowerShell, nao abre o MasterTool: le o texto do script e afirma
propriedades estruturais.

O teste central e o de ALCANCE: `ValidateOnly` e `PreflightOnly` terminam com
`exit 0` ANTES da primeira mencao ao probe 27. Isso e verificavel por ordem de
linhas, e ordem de linhas e exatamente o que garante que o modo default nao
alcance a mutacao.
"""

import io
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER_PATH = os.path.join(_REPO_ROOT, "scripts", "mastertool",
                            "run_w1_1_create_gvl.ps1")


@pytest.fixture(scope="module")
def linhas():
    texto = io.open(WRAPPER_PATH, encoding="utf-8-sig").read()
    return texto.split("\n")


@pytest.fixture(scope="module")
def texto():
    return io.open(WRAPPER_PATH, encoding="utf-8-sig").read()


@pytest.fixture(scope="module")
def codigo():
    """Somente CODIGO: sem o bloco de ajuda `<# ... #>` e sem linha de
    comentario.

    Necessario porque a documentacao do wrapper diz, em prosa, coisas como
    "Nunca usa --noUI" -- e uma busca literal no arquivo inteiro acusaria
    justamente a frase que promete o contrario do que procura.
    """
    bruto = io.open(WRAPPER_PATH, encoding="utf-8-sig").read()
    sem_ajuda = re.sub(r"<#.*?#>", "", bruto, flags=re.S)
    linhas_codigo = []
    for linha in sem_ajuda.split("\n"):
        sem_comentario = re.sub(r"(?<!`)#.*$", "", linha)
        linhas_codigo.append(sem_comentario)
    return "\n".join(linhas_codigo)


def _corpo_do_bloco(codigo, indice_da_chave):
    """Corpo delimitado por chaves balanceadas, a partir de `{`."""
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


def _primeira_linha_com(linhas, padrao):
    expressao = re.compile(padrao)
    for indice, linha in enumerate(linhas):
        if expressao.search(linha):
            return indice
    return None


def test_wrapper_existe():
    assert os.path.isfile(WRAPPER_PATH)


# --- modos ------------------------------------------------------------------

def test_tres_modos_declarados(texto):
    for parametro in ("[switch]$ValidateOnly", "[switch]$PreflightOnly",
                      "[switch]$ExecuteMutation"):
        assert parametro in texto


def test_default_e_validate_only(texto):
    assert "$Mode = 'ValidateOnly'" in texto
    assert "assumindo -ValidateOnly (default)" in texto


def test_modos_mutuamente_exclusivos(texto):
    assert "$selectedModes.Count -gt 1" in texto
    assert "Modos mutuamente exclusivos" in texto


def test_execute_mutation_exige_flag_literal(texto):
    """Nao ha string de modo vinda de fora: os tres modos sao switches."""
    assert "-Mode " not in texto
    assert '[string]$Mode' not in texto


# --- alcance: o probe 27 so existe no ramo da mutacao -----------------------

def test_probe_27_mencionado_uma_unica_vez_na_atribuicao(linhas):
    ocorrencias = [i for i, linha in enumerate(linhas)
                   if "27_create_gvl_w1_1.py" in linha]
    assert len(ocorrencias) == 1, ocorrencias


def test_validate_only_sai_antes_do_probe_27(linhas):
    saida_validate = _primeira_linha_com(linhas, r"\$Mode -eq 'ValidateOnly'")
    probe27 = _primeira_linha_com(linhas, r"27_create_gvl_w1_1\.py")
    assert saida_validate is not None and probe27 is not None
    assert saida_validate < probe27


def test_preflight_only_sai_antes_do_probe_27(linhas):
    saida_preflight = _primeira_linha_com(linhas, r"\$Mode -eq 'PreflightOnly'")
    probe27 = _primeira_linha_com(linhas, r"27_create_gvl_w1_1\.py")
    assert saida_preflight is not None and probe27 is not None
    assert saida_preflight < probe27


def test_cada_saida_de_modo_tem_exit_zero_logo_apos(linhas):
    for padrao in (r"\$Mode -eq 'ValidateOnly'", r"\$Mode -eq 'PreflightOnly'"):
        inicio = _primeira_linha_com(linhas, padrao)
        trecho = "\n".join(linhas[inicio:inicio + 8])
        assert "exit 0" in trecho, padrao


def test_preflight_precisa_estar_verde_para_seguir(texto):
    assert "$preflight.status -ne 'preflight_passed'" in texto
    assert "Preflight NAO passou" in texto


# --- sem fallback -----------------------------------------------------------

def test_sem_fallback_de_executavel(texto):
    assert "$exeVersion -ne $ExpectedExeVersion" in texto
    assert "Sem fallback para MT9000 4.0.0 nem para MT8500" in texto
    # nenhuma linha de codigo escolhe outro executavel
    assert "MT8500.exe" not in texto
    assert "MT9000 4.0.0\\" not in texto


def test_sem_noui(codigo):
    """Verificado no CODIGO: a prosa do cabecalho promete nao usar --noUI, e
    promessa nao e verificacao."""
    assert "noUI" not in codigo


def test_sem_retry_nem_fallback_de_lancamento(codigo):
    """Procurar a palavra "fallback" acusaria a propria mensagem de aborto
    ("Sem fallback para MT9000 4.0.0"). O que se testa e a FORMA do retry:
    nenhum laco e nenhum `catch` pode conter um lancamento do MasterTool."""
    lancamentos = [m.start() for m in re.finditer(r"Invoke-MasterTool", codigo)]
    assert lancamentos, "o wrapper deveria lancar o MasterTool em algum ponto"

    for construcao in (r"while\s*\([^)]*\)\s*\{", r"for\s*\([^)]*\)\s*\{",
                       r"foreach\s*\([^)]*\)\s*\{", r"catch\s*\{"):
        for encontrado in re.finditer(construcao, codigo):
            # Janela fixa vazaria para fora do bloco e acusaria a linha
            # seguinte. O corpo e delimitado por chaves balanceadas.
            trecho = _corpo_do_bloco(codigo, encontrado.end() - 1)
            assert "Invoke-MasterTool" not in trecho, construcao

    # Toda falha chama Fail(), e Fail() encerra o processo.
    assert re.search(r"function Fail\([^)]*\)\s*\{[^}]*exit 2", codigo, re.S)


# --- veredito vem do artefato, nunca do exit code ---------------------------

def test_exit_code_do_launcher_nao_decide(texto):
    assert "O exit code do launcher NAO decide nada" in texto
    assert "$completion.status -ne 'saved_as'" in texto
    assert "$postsave.status -eq 'postsave_verified'" in texto


def test_ausencia_de_completion_aborta(texto):
    assert "completion.json ausente" in texto
    assert "preflight-completion.json ausente" in texto


def test_launcher_exit_apenas_registrado(texto):
    """`launcher_exit_code` aparece no registro, mas nunca numa condicao."""
    assert "launcher_exit_code" in texto
    assert "if ($launcherExit" not in texto
    assert "$launcherExit -eq 0" not in texto


# --- protecoes da sessao ----------------------------------------------------

def test_verifica_instancia_aberta_pelo_nome_derivado(texto):
    assert "GetFileNameWithoutExtension($Exe)" in texto
    assert "MT8500*" not in texto


def test_verifica_gate_de_seguranca(texto):
    assert "READ_ONLY_PHASE" in texto
    assert "W1_1_CREATE_GVL" in texto


def test_confere_hash_da_base_e_da_copia(texto):
    assert "SHA-256 do projeto-base diverge do plano" in texto
    assert "A copia difere do projeto-base" in texto
    assert "A copia de ENTRADA foi modificada" in texto


def test_recusa_saida_existente_e_dentro_do_repo(texto):
    assert "output_project.path ja existe" in texto
    assert "aponta para dentro do repositorio" in texto


def test_recusa_caminho_com_espaco(texto):
    assert "contem espaco" in texto


def test_exige_diretorio_de_sessao_isolado(texto):
    assert "nao esta isolado/vazio" in texto


def test_nunca_mata_processo(texto):
    for suspeito in ("Stop-Process", "Kill()", "taskkill"):
        assert suspeito not in texto


def test_registra_pid_e_orfaos(texto):
    assert "[INFO] PID:" in texto
    assert "orphan_ids" in texto
    assert "Processos orfaos" in texto


def test_captura_stdout_e_stderr(texto):
    assert "-RedirectStandardOutput" in texto
    assert "-RedirectStandardError" in texto


def test_registra_opt_no_diretorio_isolado(texto):
    assert "*.opt" in texto
    assert ".opt confinados" in texto


def test_postsave_reabre_o_arquivo_salvo(texto):
    """O fechamento de W1.1 exige a segunda abertura: `saved_as` prova que um
    arquivo foi escrito, nao que a GVL esta dentro dele."""
    assert "-ProjectPath $outputPath" in texto
    assert "--mode=postsave" in texto


def test_text_read_gap_nao_vira_aprovado(texto):
    assert "PENDENTE DE REVISAO HUMANA" in texto
    assert "'text_read_gap'" in texto


# --- compatibilidade de leitura pelo PowerShell 5.1 -------------------------

def test_arquivo_tem_bom_ou_e_ascii():
    """PowerShell 5.1 le .ps1 sem BOM como ANSI. Sem BOM e com caractere
    fora do ASCII, o parser quebra -- foi o que aconteceu na primeira versao,
    com travessao em-dash."""
    dados = open(WRAPPER_PATH, "rb").read()
    tem_bom = dados[:3] == b"\xef\xbb\xbf"
    e_ascii = all(byte < 128 for byte in bytearray(dados))
    assert tem_bom or e_ascii
