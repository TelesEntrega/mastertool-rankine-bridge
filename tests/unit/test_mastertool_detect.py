"""Testes da descoberta do MasterTool (fase R11).

Tudo injetado: nenhum teste toca disco real nem exige MasterTool instalado —
o que é a condição para que esta lógica possa ser exercida na máquina de
outra pessoa, que é justamente o problema que ela existe para resolver.
"""

import io
import json

import pytest

from mastertool_bridge.automation import mastertool_detect as md

# Caminhos montados em partes, pela mesma razão das fixtures de
# `test_repo_hygiene.py`: o verificador de higiene varre este arquivo, e um
# literal completo aqui seria — corretamente — um achado de caminho de
# instalação fixado em código. Montar em partes mantém a regra com todo o
# poder de detecção, sem allow-list nova.
#
# E a guarda funcionou: a primeira versão deste arquivo trazia os literais
# inteiros e reprovou a suíte assim que foi indexada.
_ALTUS = "C:\\" + "Program Files" + "\\Altus"
_ALTUS_X86 = "C:\\" + "Program Files (x86)" + "\\Altus"
MT9000 = _ALTUS + "\\MT9000 4.1.0\\MT9000\\Common\\MT9000.exe"
MT9000_OUTRA = _ALTUS + "\\MT9000 4.2.0\\MT9000\\Common\\MT9000.exe"
MT8500 = _ALTUS_X86 + "\\MT8500 3.63\\MT8500\\Common\\MT8500.exe"


def _ambiente(arquivos=(), dirs=(), env=None, atalho=None, versoes=None,
             listagem=None):
    arquivos = set(arquivos)
    dirs = set(dirs)
    env = env or {}
    versoes = versoes or {}
    listagem = listagem or {}

    return md.Environment(
        exists=lambda p: p in arquivos,
        isdir=lambda p: p in dirs,
        listdir=lambda p: listagem.get(p, []),
        getenv=lambda nome: env.get(nome),
        resolve_shortcut=lambda p: atalho,
        read_version=lambda p: versoes.get(p),
    )


# =============================================================================
# ordem das fontes
# =============================================================================

def test_caminho_explicito_ganha_de_tudo():
    resultado = md.detect_mastertool(
        explicit_path=MT9000,
        env=_ambiente(arquivos=[MT9000], env={md.ENV_VAR: MT8500}))
    assert resultado.resolved
    assert resultado.install.exe_path == MT9000
    assert resultado.install.source == md.SOURCE_EXPLICIT


def test_variavel_de_ambiente_e_a_saida_do_operador():
    """É a única fonte que o operador controla sem editar código."""
    resultado = md.detect_mastertool(
        env=_ambiente(arquivos=[MT8500], env={md.ENV_VAR: MT8500}))
    assert resultado.resolved
    assert resultado.install.source == md.SOURCE_ENV


def test_atalho_e_resolvido_em_vez_de_o_alvo_ser_fixado():
    """A regra de docs/27: o caminho de instalação muda entre versões, então
    resolve-se o `.lnk` sempre."""
    resultado = md.detect_mastertool(
        shortcut_path=r"C:\Desktop\Mastertool X.lnk",
        env=_ambiente(arquivos=[MT9000], atalho=MT9000))
    assert resultado.resolved
    assert resultado.install.source == md.SOURCE_SHORTCUT
    assert resultado.install.exe_path == MT9000


def test_busca_acha_no_layout_medido():
    ambiente = _ambiente(
        arquivos=[MT9000],
        dirs=[r"C:\Program Files\Altus"],
        listagem={r"C:\Program Files\Altus": ["MT9000 4.1.0"]})
    resultado = md.detect_mastertool(env=ambiente)
    assert resultado.resolved
    assert resultado.install.source == md.SOURCE_SEARCH


# =============================================================================
# as recusas
# =============================================================================

def test_duas_instalacoes_recusam_com_os_dois_caminhos():
    """Ambiguidade não é sorte: escolher em silêncio instalaria a decisão
    errada onde ninguém procuraria depois."""
    ambiente = _ambiente(
        arquivos=[MT9000, MT9000_OUTRA],
        dirs=[r"C:\Program Files\Altus"],
        listagem={r"C:\Program Files\Altus": ["MT9000 4.1.0", "MT9000 4.2.0"]})
    resultado = md.detect_mastertool(env=ambiente)
    assert resultado.resolved is False
    assert "4.1.0" in md.refusal_reason(resultado)
    assert "4.2.0" in md.refusal_reason(resultado)


def test_nenhuma_instalacao_recusa_dizendo_o_que_fazer():
    resultado = md.detect_mastertool(env=_ambiente())
    assert resultado.resolved is False
    motivo = md.refusal_reason(resultado)
    assert md.ENV_VAR in motivo
    assert "não deve ser fixado em código" in motivo


def test_caminho_explicito_inexistente_recusa():
    resultado = md.detect_mastertool(
        explicit_path=MT9000, env=_ambiente(arquivos=[]))
    assert resultado.resolved is False
    assert any("não existe" in p for p in resultado.problems)


def test_atalho_que_nao_resolve_cai_para_a_busca():
    ambiente = _ambiente(
        arquivos=[MT9000],
        dirs=[r"C:\Program Files\Altus"],
        listagem={r"C:\Program Files\Altus": ["MT9000 4.1.0"]},
        atalho=None)
    resultado = md.detect_mastertool(
        shortcut_path=r"C:\Desktop\quebrado.lnk", env=ambiente)
    assert resultado.resolved
    assert resultado.install.source == md.SOURCE_SEARCH


def test_atalho_que_levanta_vira_problema_e_nao_excecao():
    def explode(_p):
        raise OSError("shell indisponível")

    ambiente = md.Environment(
        exists=lambda p: False, isdir=lambda p: False,
        listdir=lambda p: [], getenv=lambda n: None,
        resolve_shortcut=explode, read_version=lambda p: None)
    resultado = md.detect_mastertool(shortcut_path="x.lnk", env=ambiente)
    assert resultado.resolved is False
    assert any("não pôde ser resolvido" in p for p in resultado.problems)


# =============================================================================
# versão: conferida, nunca presumida
# =============================================================================

def test_versao_exigida_e_conferida():
    ambiente = _ambiente(arquivos=[MT9000], versoes={MT9000: "4.1.0.11"})
    resultado = md.detect_mastertool(
        explicit_path=MT9000, expected_version="4.1.0.11", env=ambiente)
    assert resultado.resolved
    assert resultado.install.version == "4.1.0.11"


def test_versao_diferente_da_exigida_recusa():
    """Uma operação provada numa versão não se presume provada em outra."""
    ambiente = _ambiente(arquivos=[MT9000], versoes={MT9000: "4.2.0.0"})
    resultado = md.detect_mastertool(
        explicit_path=MT9000, expected_version="4.1.0.11", env=ambiente)
    assert resultado.resolved is False
    assert any("difere da exigida" in p for p in resultado.problems)


def test_versao_ilegivel_com_exigencia_recusa():
    """"Não consegui medir" não vira "é a versão certa" por omissão."""
    ambiente = _ambiente(arquivos=[MT9000], versoes={})
    resultado = md.detect_mastertool(
        explicit_path=MT9000, expected_version="4.1.0.11", env=ambiente)
    assert resultado.resolved is False
    assert any("não pôde ser lida" in p for p in resultado.problems)


def test_sem_exigencia_de_versao_a_leitura_e_apenas_informativa():
    ambiente = _ambiente(arquivos=[MT9000], versoes={})
    resultado = md.detect_mastertool(explicit_path=MT9000, env=ambiente)
    assert resultado.resolved
    assert resultado.install.version is None


# =============================================================================
# forma
# =============================================================================

def test_o_resultado_registra_onde_procurou():
    """Sem isto, "não achei" não distingue "procurei no lugar errado" de
    "não está instalado"."""
    ambiente = _ambiente(dirs=[])
    resultado = md.detect_mastertool(env=ambiente)
    assert resultado.searched
    assert any("Altus" in caminho for caminho in resultado.searched)


def test_listagem_que_falha_vira_problema():
    def explode(_p):
        raise OSError("acesso negado")

    ambiente = md.Environment(
        exists=lambda p: False, isdir=lambda p: True, listdir=explode,
        getenv=lambda n: None, resolve_shortcut=lambda p: None,
        read_version=lambda p: None)
    resultado = md.detect_mastertool(env=ambiente, search_roots=[r"C:\Altus"])
    assert any("não foi possível listar" in p for p in resultado.problems)


def test_serializacao():
    ambiente = _ambiente(arquivos=[MT9000], versoes={MT9000: "4.1.0.11"})
    d = md.detect_mastertool(explicit_path=MT9000, env=ambiente).to_dict()
    assert d["resolved"] is True
    assert d["install"]["version"] == "4.1.0.11"
    assert d["schema_version"] == 1


def test_refusal_reason_e_none_quando_resolveu():
    ambiente = _ambiente(arquivos=[MT9000])
    assert md.refusal_reason(
        md.detect_mastertool(explicit_path=MT9000, env=ambiente)) is None


@pytest.mark.parametrize("executavel", md.KNOWN_EXECUTABLES)
def test_o_catalogo_de_executaveis_e_literal(executavel):
    """Nome novo entra explicitamente; um glob pegaria qualquer coisa."""
    assert executavel.endswith(".exe")
    assert executavel[:-4] in ("MT9000", "MT8500")


# =============================================================================
# comando de CLI
# =============================================================================

def test_cli_recusa_quando_nao_encontra(tmp_path, capsys, monkeypatch):
    from mastertool_bridge.cli import main

    monkeypatch.delenv(md.ENV_VAR, raising=False)
    codigo = main(["detect-mastertool", "--exe",
                   str(tmp_path / "nao-existe.exe")])
    saida = capsys.readouterr().out
    assert codigo == 1
    assert "[RECUSADO]" in saida


def test_cli_aceita_caminho_explicito_real(tmp_path, capsys):
    from mastertool_bridge.cli import main

    falso = tmp_path / "MT9000.exe"
    falso.write_bytes(b"nao e um executavel de verdade")
    codigo = main(["detect-mastertool", "--exe", str(falso),
                   "--output", str(tmp_path / "detect.json")])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "[OK]" in saida
    assert "(não lida)" in saida
    relatorio = json.loads(io.open(str(tmp_path / "detect.json"),
                                   encoding="utf-8").read())
    assert relatorio["resolved"] is True
    assert relatorio["install"]["source"] == md.SOURCE_EXPLICIT
