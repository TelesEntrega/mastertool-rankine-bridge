"""Testes de `scripts/mastertool/common/device_export_inspection.py`.

O caso central: um export TRUNCADO nunca pode ser classificado como completo.
Duas exportacoes monoliticas reais deste projeto terminaram sem fechar
`</project>` e nada avisou — este modulo existe para isso nao repetir, e
estes testes existem para provar que ele avisa.

Fixtures sinteticas: o XML abaixo nao vem de projeto nenhum.
"""

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

from common import device_export_inspection as dei  # noqa: E402

XML_COMPLETO = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<project xmlns="http://www.plcopen.org/xml/tc6_0200">\n'
    '  <instances><configurations><configuration name="Sintetico">\n'
    '    <addData><data name="Device"><Device><DeviceType>\n'
    '      <Connector><HostParameterSet>\n'
    '        <Parameter ParameterId="1" type="std:WORD">\n'
    '          <Value>1</Value><Name>Sintetico</Name>\n'
    '        </Parameter>\n'
    '      </HostParameterSet></Connector>\n'
    '    </DeviceType></Device></data></addData>\n'
    '  </configuration></configurations></instances>\n'
    '</project>\n'
)

# Cortado exatamente como o export monolitico real cortava: dentro da
# subarvore de Device, sem fechar o elemento raiz.
XML_TRUNCADO = XML_COMPLETO.split("      </HostParameterSet></Connector>")[0]


def _escreve(tmp_path, nome, conteudo):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return str(caminho)


# --- ascii_slug -------------------------------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    ("Device_01", "Device_01"),
    ("NET 1", "NET_1"),
    ("Balanças", "Balan_as"),
    ("Баланс", "fallback"),
    ("", "fallback"),
    (None, "fallback"),
    ("///", "fallback"),
])
def test_ascii_slug_sempre_ascii_ou_fallback(entrada, esperado):
    resultado = dei.ascii_slug(entrada, "fallback")
    assert resultado == esperado
    assert all(ord(c) < 128 for c in resultado)


def test_ascii_slug_trunca():
    assert len(dei.ascii_slug("a" * 200, "fb", max_len=10)) == 10


# --- inspect_export_file ----------------------------------------------------

def test_arquivo_ausente_nao_finge_existir(tmp_path):
    info = dei.inspect_export_file(str(tmp_path / "nao_existe"))
    assert info["exists"] is False
    assert info["closes_root_element"] is None


def test_export_completo_e_reconhecido(tmp_path):
    caminho = _escreve(tmp_path, "completo", XML_COMPLETO)
    info = dei.inspect_export_file(caminho)
    assert info["exists"] is True
    assert info["closes_root_element"] is True
    assert info["size"] > 0


def test_export_truncado_e_reconhecido(tmp_path):
    caminho = _escreve(tmp_path, "truncado", XML_TRUNCADO)
    info = dei.inspect_export_file(caminho)
    assert info["exists"] is True
    assert info["closes_root_element"] is False


def test_arquivo_grande_so_le_a_cauda(tmp_path):
    """O sinal esta no fim; ler o arquivo inteiro seria desperdicio num
    export de centenas de KB."""
    recheio = "<!-- %s -->\n" % ("x" * 5000)
    caminho = _escreve(tmp_path, "grande",
                       XML_COMPLETO.replace("</project>", recheio + "</project>"))
    info = dei.inspect_export_file(caminho)
    assert info["closes_root_element"] is True
    assert len(info["tail"]) <= 90


def test_hash_e_injetavel(tmp_path):
    caminho = _escreve(tmp_path, "completo", XML_COMPLETO)
    info = dei.inspect_export_file(caminho, sha256_fn=lambda p: "hash-fake")
    assert info["sha256"] == "hash-fake"


def test_sem_funcao_de_hash_o_campo_fica_nulo_e_nao_inventa(tmp_path):
    caminho = _escreve(tmp_path, "completo", XML_COMPLETO)
    assert dei.inspect_export_file(caminho)["sha256"] is None


# --- classify_export_run ----------------------------------------------------

def test_tudo_certo_e_complete():
    assert dei.classify_export_run(
        {"truncated": 0, "errors": 0}) == dei.STATUS_COMPLETE


def test_erro_isolado_nao_invalida_os_demais():
    """Um dispositivo sem device description falha sozinho; os XML completos
    ja exportados continuam validos e a cobertura e que fica reduzida."""
    assert dei.classify_export_run(
        {"truncated": 0, "errors": 4}) == dei.STATUS_WITH_ERRORS


def test_truncado_tem_precedencia_sobre_erro():
    """O caso que importa: com truncamento presente, o conjunto NUNCA e
    reportado como completo, mesmo que os outros dispositivos tenham ido bem."""
    assert dei.classify_export_run(
        {"truncated": 1, "errors": 0}) == dei.STATUS_TRUNCATED
    assert dei.classify_export_run(
        {"truncated": 1, "errors": 9}) == dei.STATUS_TRUNCATED


def test_totais_ausentes_nao_levantam():
    assert dei.classify_export_run({}) == dei.STATUS_COMPLETE


# --- exit codes -------------------------------------------------------------

def test_exit_codes():
    assert dei.exit_code_for(dei.STATUS_COMPLETE) == 0
    assert dei.exit_code_for(dei.STATUS_WITH_ERRORS) == 0
    assert dei.exit_code_for(dei.STATUS_TRUNCATED) == 2
    assert dei.exit_code_for(dei.STATUS_FATAL) == 1


def test_status_desconhecido_e_tratado_como_fatal():
    assert dei.exit_code_for("status_que_nao_existe") == 1
