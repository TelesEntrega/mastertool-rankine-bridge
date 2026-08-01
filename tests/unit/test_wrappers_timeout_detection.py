"""Nenhum wrapper pode decidir "a janela nao fechou" por EXCECAO.

`Wait-Process -Id <pid> -ErrorAction Stop` LANCA em dois casos opostos:

    o processo ainda esta rodando depois do timeout  -> a janela nao fechou
    o processo ja encerrou e o PID foi reciclado     -> a janela fechou sozinha

Os dez wrappers tratavam os dois como o primeiro (`catch { $timedOut = $true }`),
e o resultado apareceu na run-022: o probe 40 terminou sozinho por
`system.exit(0)`, e o host anunciou

    [TIMEOUT] A janela nao fechou. Provavelmente ha um dialogo aberto.
              Este host NAO mata processo. Verifique a tela.

sobre um processo que nao existia mais. O MELHOR desfecho relatado como o PIOR.

Isso e pior que um erro cosmetico. Este aviso e o unico canal que diz ao
operador "ha um dialogo modal esperando voce" -- e um aviso que dispara no caso
limpo ensina o leitor a ignora-lo, justamente para que ele nao seja lido na vez
em que for verdadeiro.

A correcao e perguntar ao PROCESSO (`HasExited`), e nao a excecao. A pergunta
"a janela fechou?" e sobre o processo; o `catch` responde outra coisa -- se o
cmdlet reclamou.

A varredura e por diretorio, e nao por lista fixa: o defeito nasceu de copia
entre wrappers, e uma lista fixa deixaria o proximo de fora.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WRAPPERS_DIR = REPO_ROOT / "scripts" / "mastertool"

USA_WAIT_PROCESS = re.compile(r"Wait-Process\b", re.IGNORECASE)

# `catch { $timedOut = $true }` -- a forma exata do defeito, e qualquer variante
# que atribua verdadeiro a variavel de timeout dentro de um catch.
CATCH_DECIDE_TIMEOUT = re.compile(
    r"catch\s*(\[[^\]]*\]\s*)?\{[^}]*\$timedOut\s*=\s*\$true", re.IGNORECASE)

# A forma correta: o veredito sai de HasExited.
DECIDE_POR_HASEXITED = re.compile(
    r"\$timedOut\s*=\s*-not\s+\$proc\.HasExited", re.IGNORECASE)


def _wrappers() -> list[Path]:
    return sorted(WRAPPERS_DIR.glob("*.ps1"))


def _codigo_sem_comentario(caminho: Path) -> str:
    """Texto do wrapper sem as linhas de comentario.

    Sem isto, o proprio comentario que EXPLICA o defeito derrubaria o teste, e
    documentar a correcao viraria a causa da falha -- mesma armadilha que
    `test_wrappers_artifact_encoding` ja evita.
    """
    linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    return "\n".join(ln for ln in linhas if not ln.lstrip().startswith("#"))


def test_existe_wrapper_para_varrer() -> None:
    """Ancora: uma varredura que nao encontra nada passa por vacuidade."""
    assert _wrappers(), "nenhum .ps1 em scripts/mastertool"


def test_ha_wrapper_que_de_fato_espera_processo() -> None:
    """Segunda ancora: se nenhum wrapper usasse `Wait-Process`, os testes
    abaixo passariam sem examinar linha nenhuma."""
    com_wait = [w.name for w in _wrappers()
                if USA_WAIT_PROCESS.search(_codigo_sem_comentario(w))]
    assert len(com_wait) >= 10, com_wait


@pytest.mark.parametrize("wrapper", _wrappers(), ids=lambda p: p.name)
def test_nenhum_catch_declara_timeout(wrapper: Path) -> None:
    codigo = _codigo_sem_comentario(wrapper)
    achado = CATCH_DECIDE_TIMEOUT.search(codigo)
    assert achado is None, (
        f"{wrapper.name}: decide timeout dentro de um catch -- "
        f"{achado.group(0)[:80] if achado else ''}. `Wait-Process` lanca "
        "tambem quando o processo JA encerrou, e o aviso sairia no caso limpo."
    )


@pytest.mark.parametrize("wrapper", _wrappers(), ids=lambda p: p.name)
def test_quem_espera_processo_decide_por_hasexited(wrapper: Path) -> None:
    codigo = _codigo_sem_comentario(wrapper)
    if not USA_WAIT_PROCESS.search(codigo):
        pytest.skip("wrapper nao espera processo")
    assert DECIDE_POR_HASEXITED.search(codigo), (
        f"{wrapper.name}: usa Wait-Process mas nao decide por "
        "`-not $proc.HasExited`. A pergunta 'a janela fechou?' e sobre o "
        "processo, nao sobre o cmdlet ter reclamado."
    )


@pytest.mark.parametrize("wrapper", _wrappers(), ids=lambda p: p.name)
def test_o_wait_process_nao_pode_ficar_sem_timeout(wrapper: Path) -> None:
    """Com `catch { }` engolindo o erro, um `Wait-Process` sem `-Timeout`
    bloquearia para sempre diante de um dialogo modal -- e o host nao mata
    processo. O timeout e o que garante que a sessao termina."""
    codigo = _codigo_sem_comentario(wrapper)
    for linha in codigo.splitlines():
        if USA_WAIT_PROCESS.search(linha):
            assert "-Timeout" in linha, (
                f"{wrapper.name}: `Wait-Process` sem `-Timeout`: {linha.strip()}"
            )
