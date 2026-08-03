#!/usr/bin/env python
"""Guarda de higiene do repositório — parte da fase R0 (CI offline).

Executa quatro checagens, todas determinísticas, sobre a lista de arquivos
*rastreados* por `git ls-files` (nunca sobre o diretório de trabalho bruto,
que pode conter artefatos ignorados/untracked):

(a) dado de cliente     — deny-list de identificadores reais e confirmados,
                          com allow-list para menção legítima de política;
(b) tamanho e extensão  — nenhum arquivo grande nem binário proprietário
                          versionado (`.project`, `.zip`, `.exe`, `.dll`,
                          `.pdf`, export `.xml`), salvo fixture sintética
                          conhecida e explicitamente listada;
(c) caminho absoluto local — nenhum `C:\\...` desta máquina de desenvolvimento
                          dentro de `src/`, `tests/`, `tools/` ou `scripts/`
                          (documentação pode citar; código não pode depender);
(d) segredo genérico    — padrões de chave/token de alta probabilidade.

Cada regra é implementada como função pura `find_*_findings(relpath, ...)`
para ser testável nos dois sentidos (entrada que passa e entrada que falha)
em `tests/unit/test_repo_hygiene.py`, sem tocar o disco.

Uso:

    python tools/check_repo_hygiene.py [--root DIR] [--max-bytes N]

Saída: 0 se limpo, 1 se há qualquer achado. Cada achado é impresso com o
nome da regra, o arquivo, a linha (quando aplicável) e o motivo.

Este verificador é puramente offline: não abre o MasterTool, não lança
processo algum, só lê texto de arquivos já rastreados pelo git.

PONTO CEGO CONHECIDO, medido no próprio R0 — varrer só o que está rastreado
significa que **um arquivo novo é invisível até ser commitado**. O commit
`3d2d7a6` introduziu este verificador junto com o seu teste; rodada antes do
commit, a suíte ficou verde, porque o arquivo de teste ainda era untracked e
as suas fixtures (chave AWS de brinquedo, caminho absoluto de exemplo) não
foram varridas. Rodada depois do commit, a mesma suíte reprovou com seis
achados. O gate não erra o veredito — ele o dá tarde, e quem roda a suíte
antes de commitar recebe um verde que o commit desmente.

Fica DOCUMENTADO em vez de silenciosamente corrigido: incluir untracked
(`git ls-files --others --exclude-standard`) tornaria o local mais estrito que
a CI e passaria a reprovar rascunho não ignorado do desenvolvedor. A escolha
entre as duas é do operador, e está registrada na dívida técnica de
`docs/CURRENT_STATUS.md` §4. Até lá, a regra prática: **arquivo novo com
padrão de segredo ou caminho absoluto só aparece na varredura depois de
`git add`** — rode o verificador uma vez com o arquivo já indexado.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import namedtuple

EXIT_OK = 0
EXIT_FAILED = 1

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

Finding = namedtuple("Finding", ["rule", "relpath", "line", "message"])

# ---------------------------------------------------------------------------
# Perfis — a mesma regra tem peso diferente conforme para onde o codigo vai
#
# ACHADO que motivou os perfis: a primeira versao deste verificador tratava o
# NOME de um projeto de cliente como violacao fatal, e reprovou 205 ocorrencias
# em ~40 arquivos. Duas coisas estavam erradas nisso.
#
# Primeira, de fato: `TemplateExemplo v1.project` NAO e projeto de cliente. O CHANGELOG o
# classifica como "projeto sintetico com controlador NX3008 e cartoes de I/O
# configurados". `docs/37` o chama de "projeto-base real do cliente" no sentido
# de arquivo real em vez de fixture, e essa frase induziu o erro.
#
# Segunda, de escopo: esta arvore NAO TEM REMOTE, por arquitetura. A regra do
# projeto e que dado de cliente -- XML, arvore de projeto, inventario de
# dispositivo -- nunca e versionado, e ela esta cumprida. O NOME de um projeto
# em documento interno e outra coisa: e metadado que nao pode ATRAVESSAR a
# fronteira de publicacao. Conferido a cada publicacao, pelo sanitizador: o
# espelho publico nao contem identificador de cliente nem caminho local.
# (O nome nao e citado aqui de proposito -- este arquivo E publicado.)
#
# Entao a regra continua, e o que muda e onde ela e fatal.
PROFILE_INTERNO = "interno"
PROFILE_PUBLICACAO = "publicacao"
PROFILES = (PROFILE_INTERNO, PROFILE_PUBLICACAO)

SEVERITY_FATAL = "fatal"
SEVERITY_PUBLICACAO = "bloqueio_de_publicacao"

# Regra -> severidade por perfil.
RULE_SEVERITY = {
    "client_data": {
        PROFILE_INTERNO: SEVERITY_PUBLICACAO,
        PROFILE_PUBLICACAO: SEVERITY_FATAL,
    },
    "oversized_file": {
        PROFILE_INTERNO: SEVERITY_FATAL,
        PROFILE_PUBLICACAO: SEVERITY_FATAL,
    },
    "disallowed_extension": {
        PROFILE_INTERNO: SEVERITY_FATAL,
        PROFILE_PUBLICACAO: SEVERITY_FATAL,
    },
    "local_absolute_path": {
        PROFILE_INTERNO: SEVERITY_FATAL,
        PROFILE_PUBLICACAO: SEVERITY_FATAL,
    },
    "secret": {
        PROFILE_INTERNO: SEVERITY_FATAL,
        PROFILE_PUBLICACAO: SEVERITY_FATAL,
    },
}


def severity_of(rule, profile):
    """Severidade de uma regra num perfil. Regra desconhecida e FATAL.

    Fail-closed de proposito: uma regra nova que ninguem classificou nao pode
    entrar valendo menos do que as outras.
    """
    return RULE_SEVERITY.get(rule, {}).get(profile, SEVERITY_FATAL)


# ---------------------------------------------------------------------------
# (a) dado de cliente — identificadores reais, CONFIRMADOS pelo próprio texto
# do repositório (não suposição). Cada entrada carrega o motivo e a evidência
# de onde a confirmação veio.
# ---------------------------------------------------------------------------

# OS PADROES MORAM FORA, e o motivo e instrutivo.
#
# Este verificador E publicado -- a CI do repo publico o roda. Os padroes que
# ele usa para detectar nome de cliente contem nome de cliente, e na primeira
# tentativa de publicacao o sanitizador os trocou pelo nome ficticio DENTRO do
# detector: 119 falsos positivos, e o nome real deixou de ser detectado. A
# ferramenta comeu a propria guarda.
#
# Agora eles vivem em `tools/client_identifiers.py`, que NAO e publicado. Aqui
# ausente, a lista e vazia -- e isso e correto, nao degradacao: por construcao
# nenhum identificador de cliente chega a copia publicada, porque quem os
# barra e o sanitizador, antes, com recusa fail-closed.
try:
    from tools.client_identifiers import (                       # noqa: F401
        CLIENT_IDENTIFIER_PATTERNS,
    )
except ImportError:                                              # pragma: no cover
    try:
        from client_identifiers import CLIENT_IDENTIFIER_PATTERNS
    except ImportError:
        CLIENT_IDENTIFIER_PATTERNS = []

# Arquivos onde citar o identificador é legítimo porque o texto FALA SOBRE a
# regra ("nunca versionar X"), em vez de relatar um uso real de X. Vazio por
# construção: toda ocorrência encontrada até hoje neste repositório é relato
# de execução real (evidência de uso), não menção de política — ver o achado
# reportado ao operador na conclusão deste slice. Um caminho só entra aqui
# com uma linha ao lado explicando por que a menção é apenas documental.
CLIENT_IDENTIFIER_ALLOWLIST = frozenset()


def find_client_data_findings(relpath, content_text):
    """Devolve achados de dado de cliente em `content_text` (texto puro).

    Função pura: não toca o disco. `relpath` só é usado para checar o
    allow-list e para compor a mensagem do achado.
    """
    findings = []
    if relpath in CLIENT_IDENTIFIER_ALLOWLIST:
        return findings
    lines = content_text.splitlines()
    for name, pattern, reason in CLIENT_IDENTIFIER_PATTERNS:
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(Finding(
                    "client_data", relpath, lineno,
                    "%s: %s (trecho: %r)" % (name, reason, line.strip()[:120])))
    return findings


# ---------------------------------------------------------------------------
# (b) tamanho e extensão binária/proprietária indevida.
# ---------------------------------------------------------------------------

DEFAULT_MAX_FILE_BYTES = 1024 * 1024  # 1 MiB

# Extensões que não têm motivo para estar versionadas neste repositório:
# exports monolíticos e binários opacos à revisão de diff, com potencial de
# carregar dado de cliente ou de inflar o histórico sem necessidade.
DISALLOWED_EXTENSIONS = {
    ".project": "arquivo de projeto MasterTool/CODESYS — pode conter lógica e dado real do cliente",
    ".projectarchive": "arquivo de projeto compactado MasterTool — mesma razão do .project",
    ".zip": "arquivo compactado — opaco à revisão de diff, pode empacotar dado de cliente",
    ".exe": "binário executável — não pertence a um repositório de código-fonte Python",
    ".dll": "biblioteca nativa — idem, e nunca é reproduzível a partir do código versionado",
    ".pdf": "documento binário opaco — laudos/relatórios de cliente tendem a virar PDF",
    ".xml": "export PLCopen/projeto pode conter a árvore e os nomes reais do cliente",
}

# Único motivo aceitável para um arquivo com extensão listada acima estar
# versionado: fixture sintética, sanitizada, com teste que já verifica ela
# própria (ver `tests/unit/test_plcopen_ladder_parser.py` e
# `tests/unit/test_logical_topology.py`). Caminho relativo com `/`.
EXTENSION_ALLOWLIST = frozenset({
    "tests/fixtures/plcopen/ladder_sample.xml",
})


def find_size_extension_findings(relpath, size_bytes, max_bytes=DEFAULT_MAX_FILE_BYTES):
    """Devolve achados de tamanho/extensão para um arquivo rastreado.

    Função pura: recebe o tamanho já medido, nunca lê o disco.
    """
    findings = []
    posix_relpath = relpath.replace("\\", "/")
    if size_bytes > max_bytes:
        findings.append(Finding(
            "oversized_file", relpath, None,
            "%d bytes excede o limite de %d bytes" % (size_bytes, max_bytes)))
    _, ext = os.path.splitext(relpath)
    ext = ext.lower()
    if ext in DISALLOWED_EXTENSIONS and posix_relpath not in EXTENSION_ALLOWLIST:
        findings.append(Finding(
            "disallowed_extension", relpath, None,
            "extensão %r não permitida: %s" % (ext, DISALLOWED_EXTENSIONS[ext])))
    return findings


# ---------------------------------------------------------------------------
# (c) caminho absoluto local desta máquina de desenvolvimento.
# ---------------------------------------------------------------------------

# Diretórios de código: documentação pode citar caminho local como evidência
# de execução (ver docs/18); código nunca pode depender dele.
GUARDED_DIRS_FOR_LOCAL_PATHS = ("src", "tests", "tools", "scripts")

# Separador de caminho do Windows como ele aparece no TEXTO do arquivo.
#
# ACHADO que motivou isto: a primeira versão casava uma barra invertida só, e o
# texto de um literal Python traz DUAS (`"C:\\Program Files\\Altus\\..."`).
# Resultado: `probes/43_bind_program_to_task.py` carregava o caminho de
# instalação fixo e produzia ZERO achados — invisível para a regra e ausente da
# catraca de dívida. Os outros três probes eram pegos por acidente, porque
# repetem o mesmo caminho na docstring com barra simples. Uma regra que só pega
# a ocorrência redundante e perde a que está no código é pior que inexistente:
# ela produz a impressão de cobertura.
_SEP = r"\\{1,2}"

LOCAL_ABSOLUTE_PATH_PATTERNS = [
    (
        "local_path_home_rankine",
        re.compile(r"[A-Za-z]:%sUsers%sRankine" % (_SEP, _SEP), re.IGNORECASE),
        "caminho absoluto do usuário desta máquina de desenvolvimento",
    ),
    (
        "local_path_runs_dir",
        re.compile(r"[A-Za-z]:%smastertool-rankine-bridge-runs" % _SEP, re.IGNORECASE),
        "diretório de runs desta máquina (docs/18) — deve chegar por "
        "argumento/config, nunca hardcoded",
    ),
    (
        "local_path_mastertool_x_install",
        re.compile(r"[A-Za-z]:%sProgram Files%sAltus%sMT9000"
                   % (_SEP, _SEP, _SEP), re.IGNORECASE),
        "caminho de instalação local do MasterTool X — o executor deve "
        "descobrir/receber isso, nunca fixá-lo em código",
    ),
]


# --- excecao NOMEADA, que nao e divida --------------------------------------
#
# A catraca abaixo registra divida: coisa que deve ENCOLHER. Estes dois nao
# sao divida, e por isso nao entram la -- eles precisam conter os caminhos
# locais PARA SEMPRE, porque sao a definicao das substituicoes de publicacao.
# Um verificador que proiba nomear o que precisa ser substituido torna a
# substituicao impossivel de escrever.
#
# A excecao NAO e aberta por confianca: ela e limitada por outro guarda. Estes
# dois arquivos sao os unicos que `tools/sanitize_for_publication.py` recusa
# publicar (`NAO_PUBLICADOS`), e um teste amarra as duas listas. O risco que
# esta regra existe para impedir -- caminho local chegando ao repositorio
# publico -- esta estruturalmente fechado para eles.
LOCAL_PATH_EXEMPT = frozenset([
    "tools/sanitize_for_publication.py",
    "tests/unit/test_sanitize_for_publication.py",
])


# --- catraca de divida pre-existente ---------------------------------------
#
# Estes caminhos absolutos ja estavam no repositorio quando a regra foi
# escrita. Duas saidas ruins existiam: apagar a regra (a divida some do radar)
# ou reprovar a CI para sempre (a regra vira ruido e alguem a desliga). Esta e
# a terceira: a divida fica REGISTRADA, nao cresce, e so pode diminuir.
#
# A chave e (regra, arquivo, padrao) -- sem numero de linha, que muda a cada
# edicao sem que nada de fato mude. Arquivo novo com caminho absoluto reprova
# na hora. Entrada que deixou de existir tambem reprova, para que a lista
# encolha de verdade em vez de virar cemiterio.
#
# Por que cada uma e divida real, e nao excecao legitima: `docs/27` mediu que o
# caminho de instalacao do MasterTool MUDA entre versoes, e a regra do projeto
# e resolver o atalho `.lnk` sempre, nunca fixar o alvo. Um wrapper com o
# caminho fixo funciona nesta maquina e em nenhuma outra -- que e exatamente o
# que a fase R12 (qualificacao em outra instalacao) vai encontrar.
LOCAL_PATH_DEBT_BASELINE = frozenset([
    # --- wrappers de sessao supervisionada (host) --------------------------
    ("local_absolute_path", "scripts/host/run_cli_probe_test.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/host/run_supervised_snapshot.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/host/run_supervised_snapshot.ps1", "local_path_runs_dir"),
    # --- probes que fixam o caminho de instalacao do MT9000 ----------------
    ("local_absolute_path", "scripts/mastertool/probes/36_probe_project_settings_readonly.py", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/probes/41_inventory_libraries_readonly.py", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/probes/42_recon_tasks_readonly.py", "local_path_mastertool_x_install"),
    # Estava aqui desde sempre e a regra nao via: o unico literal deste probe
    # usa barra ESCAPADA (`C:\\Program Files\\...`), e o padrao antigo casava
    # uma barra so. Nao e divida nova -- e a mesma divida dos tres acima,
    # finalmente visivel. Entra na catraca para poder encolher junto com eles.
    ("local_absolute_path", "scripts/mastertool/probes/43_bind_program_to_task.py", "local_path_mastertool_x_install"),
    # --- wrappers de fase (cada um fixa home + instalacao) -----------------
    ("local_absolute_path", "scripts/mastertool/run_bind_program_call.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_bind_program_call.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_inventory_libraries.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_inventory_libraries.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_measure_iec_birth.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_measure_iec_birth.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_probe_project_settings.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_probe_project_settings.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_project_factory.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_project_factory.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_tmf_v1_qualification.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_tmf_v1_qualification.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_w1_1_create_gvl.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_w1_1_create_gvl.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_w1_2_create_program.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_w1_2_create_program.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_w1_3a_edit_gvl.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_w1_3a_edit_gvl.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_w1_3b_edit_program.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_w1_3b_edit_program.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_w1_4_integrated.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_w1_4_integrated.ps1", "local_path_mastertool_x_install"),
    ("local_absolute_path", "scripts/mastertool/run_w3_idiomatic_call.ps1", "local_path_home_rankine"),
    ("local_absolute_path", "scripts/mastertool/run_w3_idiomatic_call.ps1", "local_path_mastertool_x_install"),
    # --- divida de MAIOR prioridade: esta em `src/`, nao em wrapper --------
    # Um wrapper com caminho fixo e roteiro de sessao; codigo de biblioteca com
    # caminho fixo e a ferramenta assumindo esta maquina.
    ("local_absolute_path", "src/mastertool_bridge/automation/run_states.py", "local_path_runs_dir"),
    ("local_absolute_path", "src/mastertool_bridge/automation/supervised_run.py", "local_path_runs_dir"),
    ("local_absolute_path", "tests/unit/test_supervised_run_host.py", "local_path_runs_dir"),
])


def load_debt_baseline(root=None):
    """Catraca corrente, mas **so** para esta arvore.

    A catraca lista caminhos deste repositorio. Aplicada a outra raiz -- um
    repo sintetico de teste, um checkout parcial -- todas as entradas
    apareceriam como "divida que nao existe mais" e reprovariam um repositorio
    perfeitamente limpo. Fora daqui, a catraca e vazia e toda ocorrencia e
    tratada como nova, que e o comportamento seguro.
    """
    if root is None:
        return LOCAL_PATH_DEBT_BASELINE
    if os.path.abspath(root) == os.path.abspath(REPO_ROOT):
        return LOCAL_PATH_DEBT_BASELINE
    return frozenset()


def owns_debt_baseline(root=None):
    """Esta arvore e a DONA da catraca, ou uma copia sanitizada dela?

    A pergunta nasceu de um caso concreto: a copia publicada roda a MESMA
    suite, e nela parte da divida DESAPARECE (a sanitizacao troca o diretorio
    pessoal por um caminho ficticio) enquanto outra parte SOBREVIVE -- o
    caminho de instalacao do MT9000, que e do produto e nao da maquina.

    Zerar a catraca la seria errado: a divida que sobrevive viraria "achado
    novo" e reprovaria. Manter a queixa de "divida obsoleta" tambem seria
    errado: a divida que sumiu sumiu por sanitizacao, e nao porque alguem a
    pagou -- a copia reprovaria por ser mais limpa que o original.

    A saida e separar as duas coisas: a catraca vale SEMPRE, e a exigencia de
    ela ENCOLHER vale so aqui. O marcador e o proprio sanitizador, que e por
    definicao o unico arquivo de codigo que nunca e publicado.
    """
    raiz = os.path.abspath(root or REPO_ROOT)
    return os.path.isfile(os.path.join(raiz, "tools",
                                       "sanitize_for_publication.py"))


def debt_key(finding):
    """Chave estavel de um achado, sem numero de linha."""
    nome = finding.message.split(":", 1)[0].strip()
    return (finding.rule, finding.relpath.replace("\\", "/"), nome)


def apply_debt_ratchet(findings, baseline):
    """Separa achados em (novos, conhecidos) e detecta divida ja paga.

    Devolve `(novos, conhecidos, obsoletos)`:
      novos      -- nao estao na catraca: reprovam;
      conhecidos -- divida registrada: nao reprovam, mas sao listados;
      obsoletos  -- estao na catraca e nao existem mais: reprovam, porque a
                    catraca tem de encolher junto com a divida.
    """
    presentes = set()
    novos = []
    conhecidos = []
    for finding in findings:
        # Excecao NOMEADA: sai antes da catraca, e nao entra em `presentes`.
        # Entrar faria a catraca considerar a divida "ainda presente" para um
        # arquivo que nunca foi divida.
        if finding.relpath.replace("\\", "/") in LOCAL_PATH_EXEMPT:
            continue
        chave = debt_key(finding)
        presentes.add(chave)
        if chave in baseline:
            conhecidos.append(finding)
        else:
            novos.append(finding)
    obsoletos = sorted(baseline - presentes)
    return novos, conhecidos, obsoletos


def is_guarded_path_for_local_paths(relpath):
    posix_relpath = relpath.replace("\\", "/")
    top = posix_relpath.split("/", 1)[0]
    return top in GUARDED_DIRS_FOR_LOCAL_PATHS


def find_local_path_findings(relpath, content_text):
    """Devolve achados de caminho absoluto local em código (não em docs)."""
    findings = []
    if not is_guarded_path_for_local_paths(relpath):
        return findings
    lines = content_text.splitlines()
    for name, pattern, reason in LOCAL_ABSOLUTE_PATH_PATTERNS:
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(Finding(
                    "local_absolute_path", relpath, lineno,
                    "%s: %s (trecho: %r)" % (name, reason, line.strip()[:120])))
    return findings


# ---------------------------------------------------------------------------
# (d) segredo genérico — padrões de chave/token de alta entropia.
# ---------------------------------------------------------------------------

# Cada padrão tem comentário do que detecta e por quê. Marcador de escape
# `hygiene: allow-secret-pattern` na mesma linha permite documentação que
# precisa MOSTRAR a forma de uma chave sem versionar uma real.
SECRET_ESCAPE_MARKER = "hygiene: allow-secret-pattern"

SECRET_PATTERNS = [
    (
        "secret_aws_access_key_id",
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "formato de AWS Access Key ID",
    ),
    (
        "secret_private_key_header",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"),
        "cabeçalho de chave privada PEM",
    ),
    (
        "secret_assigned_literal",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|password)\b"
            r"\s*[:=]\s*['\"][A-Za-z0-9/+_\-]{16,}['\"]"),
        "literal atribuído a uma variável de nome típico de segredo",
    ),
]


def find_secret_findings(relpath, content_text):
    """Devolve achados de padrão de segredo genérico em `content_text`."""
    findings = []
    lines = content_text.splitlines()
    for name, pattern, reason in SECRET_PATTERNS:
        for lineno, line in enumerate(lines, start=1):
            if SECRET_ESCAPE_MARKER in line:
                continue
            if pattern.search(line):
                findings.append(Finding(
                    "secret", relpath, lineno,
                    "%s: %s (trecho: %r)" % (name, reason, line.strip()[:120])))
    return findings


# ---------------------------------------------------------------------------
# Orquestração: lê `git ls-files` e aplica as quatro regras.
# ---------------------------------------------------------------------------

def get_tracked_files(root):
    """Lista de arquivos rastreados pelo git, relativos a `root`.

    Determinístico: não inclui untracked nem ignorado. Falha alto (exceção)
    se `git` não estiver disponível ou `root` não for um repositório —
    nunca varre silenciosamente um diretório que não é o repo.
    """
    output = subprocess.check_output(
        ["git", "ls-files"], cwd=root, stderr=subprocess.STDOUT)
    text = output.decode("utf-8", errors="surrogateescape")
    return [line for line in text.splitlines() if line]


def _read_text(abspath):
    """Lê `abspath` como texto UTF-8 tolerante, ou None se for binário."""
    with open(abspath, "rb") as handle:
        data = handle.read()
    if b"\x00" in data:
        return None, len(data)
    return data.decode("utf-8", errors="replace"), len(data)


def run_checks(root, max_bytes=DEFAULT_MAX_FILE_BYTES):
    """Roda as quatro checagens sobre os arquivos rastreados de `root`.

    Devolve a lista de `Finding`, na ordem em que os arquivos aparecem em
    `git ls-files` (determinístico).
    """
    findings = []
    for relpath in get_tracked_files(root):
        abspath = os.path.join(root, relpath)
        if not os.path.isfile(abspath):
            continue
        size_bytes = os.path.getsize(abspath)
        findings.extend(find_size_extension_findings(relpath, size_bytes, max_bytes))

        text, _ = _read_text(abspath)
        if text is None:
            continue  # binário: as demais regras operam sobre texto
        findings.extend(find_client_data_findings(relpath, text))
        findings.extend(find_local_path_findings(relpath, text))
        findings.extend(find_secret_findings(relpath, text))
    return findings


def format_finding(finding):
    location = finding.relpath if finding.line is None else (
        "%s:%d" % (finding.relpath, finding.line))
    return "[%s] %s -- %s" % (finding.rule, location, finding.message)


def _reconfigure_stdout_utf8():
    """Console do Windows costuma vir em cp1252; achados citam texto com
    acentos e travessão. Sem isto, `print` de um achado real derruba o
    processo por `UnicodeEncodeError` antes de reportar nada."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


def classify(findings, profile, baseline):
    """Separa achados em fatais, bloqueios de publicacao e divida conhecida.

    Funcao pura sobre a lista de achados -- e onde perfil e catraca se
    encontram, e por isso e testada isoladamente.
    """
    com_catraca = [f for f in findings if f.rule == "local_absolute_path"]
    demais = [f for f in findings if f.rule != "local_absolute_path"]

    novos, conhecidos, obsoletos = apply_debt_ratchet(com_catraca, baseline)

    fatais = list(novos)
    publicacao = []
    for finding in demais:
        if severity_of(finding.rule, profile) == SEVERITY_FATAL:
            fatais.append(finding)
        else:
            publicacao.append(finding)
    return fatais, publicacao, conhecidos, obsoletos


def main(argv=None):
    _reconfigure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=REPO_ROOT,
                         help="raiz do repositório (padrão: raiz deste checkout)")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES,
                         help="limite de tamanho por arquivo, em bytes")
    parser.add_argument("--profile", choices=PROFILES, default=PROFILE_INTERNO,
                         help="`interno` (esta árvore, sem remote) ou "
                              "`publicacao` (portão do espelho sanitizado)")
    args = parser.parse_args(argv)

    findings = run_checks(args.root, args.max_bytes)
    fatais, publicacao, conhecidos, obsoletos = classify(
        findings, args.profile, load_debt_baseline(args.root))
    # A exigencia de a catraca ENCOLHER vale so na arvore que a possui -- ver
    # `owns_debt_baseline`. Na copia sanitizada parte da divida desaparece com
    # a troca de caminhos, e cobrar o encolhimento la reprovaria a CI publica
    # por o repositorio ser mais limpo que o original.
    if not owns_debt_baseline(args.root):
        obsoletos = []

    print("perfil: %s" % args.profile)

    if conhecidos:
        arquivos = sorted({f.relpath.replace("\\", "/") for f in conhecidos})
        print("[DIVIDA] %d ocorrência(s) de caminho absoluto local em %d "
              "arquivo(s), já registradas na catraca — não crescem, e a "
              "catraca só pode encolher:" % (len(conhecidos), len(arquivos)))
        for caminho in arquivos:
            print("    %s" % caminho)

    if publicacao:
        arquivos = sorted({f.relpath.replace("\\", "/") for f in publicacao})
        print("[PUBLICACAO] %d ocorrência(s) de identificador de cliente em "
              "%d arquivo(s). Não reprovam no perfil `interno` — esta árvore "
              "não tem remote. REPROVAM no perfil `publicacao`:"
              % (len(publicacao), len(arquivos)))
        for caminho in arquivos:
            print("    %s" % caminho)

    if obsoletos:
        print("[FATAL] a catraca lista dívida que não existe mais; remova "
              "estas entradas de LOCAL_PATH_DEBT_BASELINE:")
        for chave in obsoletos:
            print("    %r" % (chave,))

    for finding in fatais:
        print("[FATAL] %s" % format_finding(finding))

    if fatais or obsoletos:
        print("[FATAL] higiene do repositorio: %d achado(s) fatal(is), "
              "%d entrada(s) obsoleta(s) na catraca"
              % (len(fatais), len(obsoletos)))
        return EXIT_FAILED

    print("[OK] higiene do repositorio: nenhum achado fatal")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
