"""A spec INVERSA de uma alteração — a quarta palavra do gate da fase R2.

Módulo puro, offline. Recebe o que uma execução mediu e devolve a spec que
desfaz o que ela fez. Não abre o MasterTool, não adivinha texto e **não
inverte o que não foi medido**.

POR QUE ISTO NÃO É "GUARDAR UM BACKUP"
======================================
Copiar o arquivo de entrada antes de escrever seria trivial, e não provaria
reversibilidade: provaria que existe uma cópia. O que a fase R2 pede é que a
alteração seja desfeita **pelo mesmo mecanismo que a fez**, com o mesmo rigor —
`expected_before_sha256` conferido no campo, build verde, comparação
antes×depois. Uma reversão que pula a conferência é escrita cega com outro
nome.

A INVERSÃO É EXATA, E ELA TROCA OS DOIS HASHES DE LADO
======================================================
Na alteração:  antes = `expected_before_sha256` (medido)   →  depois = `text`
Na reversão:   antes = hash do `text` que foi escrito      →  depois = o texto anterior

O `antes` da reversão **não** é declarado de memória: ele é o
`planned_after_sha256` do passo, que o plano computou do texto que ele mesmo
autorizou. Se a saída não contiver exatamente aquele texto, a reversão para —
e é isso que se quer, porque significa que alguém mexeu no arquivo entre as
duas operações.

O TEXTO ANTERIOR VEM DO CAMPO, NUNCA DAQUI
==========================================
Este módulo não sabe qual era o texto. Ele exige o artefato `before-texts.json`
que o `probes/46` grava **no instante em que confere o hash**, e recusa quando
o hash gravado ali não bate com o que o plano mediu. Sem esse artefato não há
reversão — e a recusa diz isso, em vez de emitir uma spec que apaga o objeto.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# O prefixo que distingue alteração de criação em `text_hashes` do plano.
MODIFY_PREFIX = "modify"


@dataclass
class RollbackSpec:
    spec: dict[str, Any] | None = None
    reverted: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and self.spec is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": self.ok,
            "reverted": list(self.reverted),
            "problems": list(self.problems),
            "spec": self.spec,
        }


def _sha256_of_text(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _indice_de_textos_anteriores(payload: Any,
                                 problems: list[str]) -> dict[str, dict]:
    """`{source_location: entrada}` a partir de `before-texts.json`.

    Entrada sem texto **ou** com hash que não confere com o próprio texto é
    recusada aqui, e não adiante: um artefato corrompido que passasse desta
    função viraria uma spec de reversão que escreve conteúdo errado com hash
    certo, que é o pior desfecho possível.
    """
    if not isinstance(payload, dict):
        problems.append(
            "before-texts.json: esperado objeto, recebido %s"
            % type(payload).__name__)
        return {}
    objetos = payload.get("objects")
    if not isinstance(objetos, list):
        problems.append("before-texts.json sem lista `objects`")
        return {}

    indice: dict[str, dict] = {}
    for posicao, item in enumerate(objetos):
        if not isinstance(item, dict):
            problems.append("before-texts.json[%d]: esperado objeto" % posicao)
            continue
        chave = item.get("source_location")
        texto = item.get("text")
        declarado = item.get("sha256")
        if not isinstance(chave, str) or not chave:
            problems.append(
                "before-texts.json[%d] sem `source_location`" % posicao)
            continue
        if not isinstance(texto, str):
            problems.append(
                "before-texts.json[%d] (%s) sem `text`: hash não reconstrói "
                "texto, e sem o texto não há reversão" % (posicao, chave))
            continue
        medido = _sha256_of_text(texto)
        if not isinstance(declarado, str) or declarado.lower() != medido:
            problems.append(
                "before-texts.json[%d] (%s): o texto guardado tem hash %s e a "
                "entrada declara %r. Artefato inconsistente — reverter a "
                "partir dele escreveria conteúdo que ninguém conferiu"
                % (posicao, chave, medido, declarado))
            continue
        indice[chave] = {"text": texto, "sha256": medido}
    return indice


def build_rollback_spec(plan: Any, before_texts: Any,
                        output_project_sha256: str | None = None
                        ) -> RollbackSpec:
    """Emite a spec que desfaz as alterações de `plan`.

    `plan` é o plano de autoria normalizado (o mesmo que o executor rodou);
    `before_texts` é o `before-texts.json` da execução. Um plano SEM alteração
    devolve recusa e não spec vazia: "não há o que reverter" e "a reversão está
    pronta" são estados diferentes, e quem chama precisa distingui-los.
    """
    resultado = RollbackSpec()

    if not isinstance(plan, dict):
        resultado.problems.append(
            "plano: esperado objeto, recebido %s" % type(plan).__name__)
        return resultado

    passos = plan.get("steps")
    if not isinstance(passos, list):
        resultado.problems.append("plano sem lista `steps`")
        return resultado

    anteriores = _indice_de_textos_anteriores(before_texts,
                                              resultado.problems)
    if resultado.problems:
        return resultado

    modificacoes = []
    for passo in passos:
        if not isinstance(passo, dict):
            continue
        origem = passo.get("source_location")
        if not isinstance(origem, str) or not origem.startswith(
                MODIFY_PREFIX + ":"):
            continue

        partes = origem.split(":")
        if len(partes) != 4:
            resultado.problems.append(
                "passo com `source_location` %r fora da forma "
                "`modify:familia:nome:campo`" % origem)
            continue
        _, familia, nome, campo = partes

        # O ANTES da reversão é o DEPOIS da alteração, e ele vem do plano —
        # que o computou do texto que autorizou. Declarar outro valor aqui
        # seria reintroduzir exatamente o hash de memória que a fase R2 existe
        # para eliminar.
        escrito = passo.get("planned_after_sha256")
        if not isinstance(escrito, str) or not escrito:
            resultado.problems.append(
                "%s: passo sem `planned_after_sha256`. Sem ele a reversão não "
                "sabe contra o que conferir" % origem)
            continue

        entrada = anteriores.get(origem)
        if entrada is None:
            resultado.problems.append(
                "%s: a execução não registrou o texto anterior. Reverter sem "
                "ele exigiria adivinhar o conteúdo" % origem)
            continue

        modificacoes.append({
            "family": familia,
            "name": nome,
            "field": campo,
            "expected_before_sha256": escrito.lower(),
            "text": entrada["text"],
        })
        resultado.reverted.append("%s:%s:%s" % (familia, nome, campo))

    if resultado.problems:
        return resultado
    if not modificacoes:
        resultado.problems.append(
            "o plano não tem alteração de objeto preexistente — não há o que "
            "reverter. Isso não é uma reversão pronta")
        return resultado

    template = plan.get("template")
    sha_alvo = output_project_sha256 or (
        template.get("sha256") if isinstance(template, dict) else None)
    if not isinstance(sha_alvo, str) or not sha_alvo:
        resultado.problems.append(
            "sem sha256 do projeto ALVO da reversão. O alvo é a SAÍDA da "
            "execução, não o template dela — e um hash anterior só vale para "
            "o arquivo onde foi medido")
        return resultado

    resultado.spec = {
        "schema_version": 1,
        "template": {"id": "rollback-target", "sha256": sha_alvo.lower()},
        "modifications": modificacoes,
    }
    return resultado
