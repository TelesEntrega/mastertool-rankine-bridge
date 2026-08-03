"""Descoberta do executável do MasterTool — fase R11.

Módulo puro e injetável: ele não toca o disco por conta própria: recebe o
sistema de arquivos e o resolvedor de atalho como funções, o que o torna
inteiramente testável sem MasterTool instalado e sem Windows.

POR QUE ISTO EXISTE
===================
Doze wrappers e três probes deste repositório fixam o caminho de instalação
como padrão — `Program Files\\Altus\\MT9000 <versão>\\...\\MT9000.exe`, com a
letra de unidade escrita em código. (O caminho aparece aqui sem a letra de
unidade de propósito: escrevê-lo por extenso faria este arquivo virar mais uma
ocorrência do problema que ele existe para resolver, e o verificador de higiene
o acusaria — corretamente.)

`docs/27` mediu que **o caminho de instalação muda entre versões**, e a
regra do projeto é resolver o atalho `.lnk` sempre, nunca fixar o alvo. Um
wrapper com caminho fixo funciona nesta máquina e em nenhuma outra — que é
exatamente o que a fase R12 (qualificação em outra instalação) encontraria.

A DISCIPLINA É A MESMA DO SELETOR SEMÂNTICO
===========================================
Achar dois candidatos não é sorte: é ambiguidade, e escolher um deles em
silêncio instalaria a decisão errada num lugar onde ninguém procuraria depois.
Por isso o resultado tem cardinalidade explícita, e duas instalações
encontradas RECUSAM com os dois caminhos nomeados, em vez de devolver "a
primeira".

A versão é CONFERIDA, não presumida: encontrar um `MT9000.exe` não diz que é a
versão contra a qual as capacidades foram qualificadas, e
`docs/COMPATIBILITY_MATRIX.md` existe justamente porque uma operação provada
em 4.1.0.11 não se presume provada em outra.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# Variável de ambiente é a PRIMEIRA fonte, e de propósito: ela é a única que o
# operador controla sem editar código, e é o caminho de fuga quando a
# instalação está num lugar que nenhuma heurística acharia.
ENV_VAR = "MASTERTOOL_EXE"

# Nome do executável por geração de produto. Lista literal: um nome novo entra
# aqui explicitamente, e não por padrão glob que pegaria qualquer coisa.
KNOWN_EXECUTABLES = ("MT9000.exe", "MT8500.exe")

# Diretórios onde uma instalação costuma estar. NÃO é a lista de caminhos
# válidos — é onde procurar quando ninguém disse onde está. O que valida é a
# existência do arquivo e a conferência de versão.
SEARCH_ROOTS = (
    r"C:\Program Files\Altus",
    r"C:\Program Files (x86)\Altus",
)

SOURCE_ENV = "env"
SOURCE_SHORTCUT = "shortcut"
SOURCE_SEARCH = "search"
SOURCE_EXPLICIT = "explicit"

DETECTION_SOURCES = (SOURCE_EXPLICIT, SOURCE_ENV, SOURCE_SHORTCUT, SOURCE_SEARCH)


@dataclass(frozen=True)
class MasterToolInstall:
    exe_path: str
    source: str
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exe_path": self.exe_path,
            "source": self.source,
            "version": self.version,
        }


@dataclass
class DetectionResult:
    install: MasterToolInstall | None = None
    candidates: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    searched: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.install is not None and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "resolved": self.resolved,
            "install": self.install.to_dict() if self.install else None,
            "candidates": list(self.candidates),
            "problems": list(self.problems),
            "searched": list(self.searched),
        }


@dataclass(frozen=True)
class Environment:
    """As portas para o mundo externo, todas injetáveis.

    `read_version` devolve `None` quando não consegue ler — e `None` não vira
    "versão certa por omissão": quem exige versão recebe recusa nomeada.
    """

    exists: Callable[[str], bool] = os.path.isfile
    isdir: Callable[[str], bool] = os.path.isdir
    listdir: Callable[[str], Sequence[str]] = os.listdir
    getenv: Callable[[str], str | None] = os.environ.get
    resolve_shortcut: Callable[[str], str | None] = lambda _p: None
    read_version: Callable[[str], str | None] = lambda _p: None


def _candidatos_por_busca(env: Environment, roots: Sequence[str],
                          resultado: DetectionResult) -> list[str]:
    achados: list[str] = []
    for raiz in roots:
        resultado.searched.append(raiz)
        if not env.isdir(raiz):
            continue
        try:
            filhos = sorted(env.listdir(raiz))
        except OSError as exc:
            resultado.problems.append("não foi possível listar %s: %s"
                                      % (raiz, exc))
            continue
        for filho in filhos:
            base = os.path.join(raiz, filho)
            # Layout medido em docs/27: <raiz>/<Produto X.Y.Z>/<Produto>/Common/
            for executavel in KNOWN_EXECUTABLES:
                nome_produto = executavel[:-4]
                caminho = os.path.join(base, nome_produto, "Common", executavel)
                if env.exists(caminho):
                    achados.append(caminho)
    return achados


def detect_mastertool(
    explicit_path: str | None = None,
    shortcut_path: str | None = None,
    expected_version: str | None = None,
    search_roots: Sequence[str] | None = None,
    env: Environment | None = None,
) -> DetectionResult:
    """Acha UMA instalação, ou recusa dizendo por quê.

    Ordem das fontes: caminho explícito, variável de ambiente, atalho `.lnk`,
    busca nos diretórios conhecidos. A primeira que resolver ganha — e a ordem
    não é arbitrária: ela vai do mais deliberado (alguém digitou) ao mais
    heurístico (o programa procurou).
    """
    env = env or Environment()
    resultado = DetectionResult()
    roots = list(search_roots) if search_roots is not None else list(SEARCH_ROOTS)

    def _aceitar(caminho: str, fonte: str) -> DetectionResult | None:
        if not env.exists(caminho):
            resultado.problems.append(
                "%s aponta para %s, que não existe" % (fonte, caminho))
            return None
        versao = env.read_version(caminho)
        if expected_version is not None:
            if versao is None:
                resultado.problems.append(
                    "versão de %s não pôde ser lida, e %r era exigida: uma "
                    "versão que não se conseguiu medir não é a versão certa "
                    "por omissão" % (caminho, expected_version))
                return None
            if versao != expected_version:
                resultado.problems.append(
                    "versão %r em %s difere da exigida %r — uma operação "
                    "provada numa versão não se presume provada em outra"
                    % (versao, caminho, expected_version))
                return None
        resultado.install = MasterToolInstall(
            exe_path=caminho, source=fonte, version=versao)
        return resultado

    # 1. explícito
    if explicit_path:
        resultado.candidates.append(explicit_path)
        _aceitar(explicit_path, SOURCE_EXPLICIT)
        return resultado

    # 2. ambiente
    do_ambiente = env.getenv(ENV_VAR)
    if do_ambiente:
        resultado.candidates.append(do_ambiente)
        _aceitar(do_ambiente, SOURCE_ENV)
        return resultado

    # 3. atalho -- a regra de docs/27: resolver o `.lnk`, nunca fixar o alvo
    if shortcut_path:
        resultado.searched.append(shortcut_path)
        try:
            alvo = env.resolve_shortcut(shortcut_path)
        except Exception as exc:  # noqa: BLE001 — falha do shell é dado
            alvo = None
            resultado.problems.append(
                "atalho %s não pôde ser resolvido: %r" % (shortcut_path, exc))
        if alvo:
            resultado.candidates.append(alvo)
            _aceitar(alvo, SOURCE_SHORTCUT)
            return resultado

    # 4. busca
    achados = _candidatos_por_busca(env, roots, resultado)
    resultado.candidates.extend(achados)
    unicos = sorted(set(achados))
    if not unicos:
        resultado.problems.append(
            "nenhuma instalação encontrada. Informe o caminho explicitamente, "
            "defina %s, ou aponte o atalho `.lnk` — o caminho de instalação "
            "muda entre versões (docs/27) e não deve ser fixado em código"
            % ENV_VAR)
        return resultado
    if len(unicos) > 1:
        # Ambiguidade RECUSA, com os dois caminhos nomeados. Escolher em
        # silêncio instalaria a decisão errada onde ninguém procuraria depois.
        resultado.problems.append(
            "%d instalações encontradas e nenhuma indicação de qual usar: %s"
            % (len(unicos), ", ".join(unicos)))
        return resultado

    _aceitar(unicos[0], SOURCE_SEARCH)
    return resultado


def refusal_reason(result: DetectionResult) -> str | None:
    """Por que a detecção recusou, em texto. `None` quando resolveu."""
    if result.resolved:
        return None
    if result.problems:
        return "; ".join(result.problems)
    return "detecção não resolveu e não registrou motivo — isto é defeito"
