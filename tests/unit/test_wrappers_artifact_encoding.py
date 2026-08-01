"""Nenhum wrapper pode gravar artefato JSON com BOM.

`Out-File -Encoding utf8` no PowerShell 5.1 escreve BOM. O resultado apareceu
na execucao real de W1.3A (run-008): `session-verdict.json` ficou ilegivel para
qualquer leitor JSON estrito --

    json.decoder.JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig)

-- ou seja, o relatorio que existe para dar veredito da sessao nao podia ser
lido pelo mesmo pipeline que o consome. Os quatro wrappers de W1 tinham a
mesma linha, e a suite inteira (2220 testes) passou por cima dela: nenhum
teste olhava a CODIFICACAO do que o wrapper grava, so o que ele decide.

Este arquivo fecha essa lacuna para todos os wrappers de uma vez, inclusive os
que ainda nao existem -- a varredura e por diretorio, nao por lista fixa.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WRAPPERS_DIR = REPO_ROOT / "scripts" / "mastertool"

# `-Encoding utf8` em cmdlet de escrita. Pega Out-File, Set-Content e
# Add-Content na mesma regra: os tres produzem BOM no PowerShell 5.1.
CMDLET_COM_BOM = re.compile(
    r"(Out-File|Set-Content|Add-Content)\b[^\r\n]*-Encoding\s+utf8\b",
    re.IGNORECASE,
)

# A forma correta: UTF8Encoding($false) e explicitamente "sem BOM".
ESCRITA_SEM_BOM = re.compile(
    r"System\.Text\.UTF8Encoding\(\s*\$false\s*\)", re.IGNORECASE)


def _wrappers() -> list[Path]:
    return sorted(WRAPPERS_DIR.glob("*.ps1"))


def _linhas_de_codigo(caminho: Path) -> list[tuple[int, str]]:
    """Linhas ignorando comentario de linha inteira.

    Sem isto, o proprio comentario que EXPLICA o defeito ("`Out-File -Encoding
    utf8` grava BOM") derrubaria o teste -- e a documentacao da correcao viraria
    a causa da falha.
    """
    linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    return [(i + 1, ln) for i, ln in enumerate(linhas)
            if not ln.lstrip().startswith("#")]


def test_existe_wrapper_para_varrer() -> None:
    """Ancora: uma varredura que nao encontra nada passa por vacuidade."""
    assert _wrappers(), "nenhum .ps1 em scripts/mastertool"


@pytest.mark.parametrize("wrapper", _wrappers(), ids=lambda p: p.name)
def test_wrapper_nao_grava_artefato_com_bom(wrapper: Path) -> None:
    ofensas = [(n, ln.strip()) for n, ln in _linhas_de_codigo(wrapper)
               if CMDLET_COM_BOM.search(ln)]
    assert not ofensas, (
        "%s grava com `-Encoding utf8`, que produz BOM no PowerShell 5.1 e "
        "torna o artefato JSON ilegivel para leitor estrito. Use "
        "[System.IO.File]::WriteAllText(path, texto, "
        "(New-Object System.Text.UTF8Encoding($false))). Linhas: %s"
        % (wrapper.name, ofensas))


@pytest.mark.parametrize("wrapper", _wrappers(), ids=lambda p: p.name)
def test_wrapper_que_grava_json_usa_utf8_sem_bom(wrapper: Path) -> None:
    """Nao basta remover o cmdlet ruim: quem grava JSON tem de gravar pelo
    caminho explicitamente sem BOM. Sem esta metade, trocar `Out-File -Encoding
    utf8` por `Out-File` puro passaria no teste acima e continuaria errado --
    o default de `Out-File` no PowerShell 5.1 nao e UTF-8 sem BOM."""
    codigo = "\n".join(ln for _, ln in _linhas_de_codigo(wrapper))
    if "ConvertTo-Json" not in codigo:
        pytest.skip("%s nao gera artefato JSON" % wrapper.name)
    assert ESCRITA_SEM_BOM.search(codigo), (
        "%s gera JSON mas nao grava por UTF8Encoding($false)" % wrapper.name)


@pytest.mark.parametrize("wrapper", _wrappers(), ids=lambda p: p.name)
def test_artefato_json_nao_e_gravado_por_pipe_para_out_file(wrapper: Path) -> None:
    """A forma que causou o defeito era um pipe do ConvertTo-Json direto para
    Out-File. Mesmo com `-Encoding utf8NoBOM` (que nao existe no 5.1) ou sem
    parametro, o pipe deixa a codificacao a cargo do default do console."""
    linhas = _linhas_de_codigo(wrapper)
    ofensas = []
    for indice, (numero, linha) in enumerate(linhas):
        if "ConvertTo-Json" not in linha:
            continue
        # O pipe pode continuar na linha seguinte quando a linha termina em `|`.
        janela = linha
        if linha.rstrip().endswith("|") and indice + 1 < len(linhas):
            janela = janela + " " + linhas[indice + 1][1]
        if re.search(r"\|\s*Out-File", janela, re.IGNORECASE):
            ofensas.append(numero)
    assert not ofensas, (
        "%s canaliza ConvertTo-Json direto para Out-File nas linhas %s; "
        "grave por [System.IO.File]::WriteAllText com UTF8Encoding($false)"
        % (wrapper.name, ofensas))
