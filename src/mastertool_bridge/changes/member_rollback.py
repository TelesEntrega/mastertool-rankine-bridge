# -*- coding: utf-8 -*-
"""Reversão da criação de MEMBRO: o plano inverso é EMITIDO, nunca digitado.

Contrato `docs/87` §7.

`changes/rollback.py` reverte **texto de objeto preexistente**: a inversa de um
`replace` é outro `replace`, com `expected_before` vindo do
`planned_after_sha256` da ida. Aqui a operação é outra — o que se desfaz é a
**existência** de um objeto, e não o conteúdo dele. Reusar aquele módulo
produziria um `replace` com texto vazio, que deixa o membro na árvore e é
exatamente o que o gate da R2 recusa: desfazer tem de ser pelo MESMO mecanismo
e com o MESMO rigor.

**O plano inverso é derivado do plano da ida.** Digitar os nomes de novo
reintroduziria, por outro caminho, o defeito que `docs/54` fechou: um artefato
de reversão escrito à mão prova que alguém sabe escrevê-lo, e não que a ida foi
desfeita.

**Ordem INVERSA de criação.** Não porque a remoção de membros dependa da ordem
— eles são irmãos —, mas porque a ordem inversa é a única que continua correta
se um dia a superfície ganhar membro que dependa de membro. Depender de os
irmãos serem independentes seria uma premissa que nada verifica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.planner.planner import (
    EXPECTED_BEFORE_NOT_APPLICABLE,
    OPERATION_REMOVE_METHOD,
    OPERATION_SAVE_AS,
    TARGET_KIND_FUNCTION_BLOCK,
    TARGET_KIND_METHOD,
    TARGET_KIND_PROJECT,
    canonical_json,
)

import hashlib


@dataclass
class MemberRollbackResult:
    """Nunca levanta. Plano ausente com `problems` preenchido é o desfecho de
    entrada malformada — a mesma disciplina do planner."""

    problems: list[str] = field(default_factory=list)
    plan: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return not self.problems and self.plan is not None


def _passos_de_criacao_de_membro(plano: Any) -> list[dict]:
    passos = plano.get("steps") if isinstance(plano, dict) else None
    if not isinstance(passos, list):
        return []
    saida = []
    for passo in passos:
        if not isinstance(passo, dict):
            continue
        if passo.get("operation") != "create_method":
            continue
        saida.append(passo)
    return saida


def build_member_rollback_plan(plano: Any,
                               output_path: str | None = None,
                               only_members: list[str] | None = None
                               ) -> MemberRollbackResult:
    """Plano que remove EXATAMENTE os membros que `plano` criou.

    `output_path` é o destino do `save_as`; ausente, o plano sai sem passo de
    persistência e quem executa decide — a reversão em memória é legítima para
    medição, e forçar `save_as` aqui esconderia a diferença.
    """
    resultado = MemberRollbackResult()

    if not isinstance(plano, dict):
        resultado.problems.append(
            "plano de origem deve ser objeto, recebido %s"
            % type(plano).__name__)
        return resultado

    criacoes = _passos_de_criacao_de_membro(plano)

    # `only_members` existe para o ENSAIO DISCRIMINANTE: remover UM membro e
    # reabrir provando que o IRMAO sobreviveu intacto. Sem ele, "os dois
    # sumiram" seria compativel com `remove()` ter agido sobre a colecao ou
    # sobre o owner -- e a pergunta que o campo precisa responder e se ele age
    # sobre o MEMBRO EXATO.
    #
    # Nome pedido que a ida nao criou RECUSA, em vez de sair silenciosamente com
    # um plano menor: reverter menos do que se pediu, sem dizer, e a forma de
    # falha que este projeto persegue.
    if only_members is not None:
        pedidos = list(only_members)
        criados = [p.get("target_name") for p in criacoes]
        ausentes = [nome for nome in pedidos if nome not in criados]
        if ausentes:
            resultado.problems.append(
                "membro(s) pedido(s) em `only_members` que a ida nao criou: "
                + ", ".join(sorted(ausentes))
                + " — criados: " + ", ".join(sorted(n for n in criados if n)))
            return resultado
        criacoes = [p for p in criacoes if p.get("target_name") in pedidos]

    if not criacoes:
        resultado.problems.append(
            "o plano de origem não criou membro nenhum: não há o que reverter. "
            "Emitir um plano de reversão vazio faria uma execução sem efeito "
            "parecer uma reversão bem-sucedida.")
        return resultado

    passos: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for passo in reversed(criacoes):
        nome = passo.get("target_name")
        owner = passo.get("owner_name")
        especie = passo.get("owner_kind")
        if not isinstance(nome, str) or not nome:
            resultado.problems.append(
                "passo %r de create_method sem `target_name` legível"
                % (passo.get("sequence"),))
            continue
        if not isinstance(owner, str) or not owner:
            resultado.problems.append(
                "create_method %r sem `owner_name`: sem o dono não há como "
                "remover o membro certo — há homônimo possível em outro owner."
                % (nome,))
            continue
        if especie != TARGET_KIND_FUNCTION_BLOCK:
            resultado.problems.append(
                "create_method %r com owner_kind %r: o escopo qualificado é "
                "FUNCTION_BLOCK → METHOD, e a reversão não amplia escopo."
                % (nome, especie))
            continue
        if (owner, nome) in vistos:
            resultado.problems.append(
                "membro %r do owner %r criado mais de uma vez no plano de "
                "origem: a reversão seria ambígua." % (nome, owner))
            continue
        vistos.add((owner, nome))

        passos.append({
            "sequence": len(passos) + 1,
            "operation": OPERATION_REMOVE_METHOD,
            "target_kind": TARGET_KIND_METHOD,
            "target_name": nome,
            "source_location": passo.get("source_location"),
            "expected_before_kind": EXPECTED_BEFORE_NOT_APPLICABLE,
            "expected_before_sha256": None,
            "planned_after_sha256": None,
            "planned_after_normalized_sha256": None,
            "language_guid": None,
            "dut_kind": None,
            "return_type": None,
            "created_by_sequence": None,
            "task_name": None,
            "program_name": None,
            "task_properties": None,
            "owner_name": owner,
            "owner_kind": TARGET_KIND_FUNCTION_BLOCK,
        })

    if resultado.problems:
        return resultado

    if output_path:
        passos.append({
            "sequence": len(passos) + 1,
            "operation": OPERATION_SAVE_AS,
            "target_kind": TARGET_KIND_PROJECT,
            "target_name": output_path,
            "source_location": "project",
            "expected_before_kind": EXPECTED_BEFORE_NOT_APPLICABLE,
            "expected_before_sha256": None,
            "planned_after_sha256": None,
            "planned_after_normalized_sha256": None,
            "language_guid": None,
            "dut_kind": None,
            "return_type": None,
            "created_by_sequence": None,
            "task_name": None,
            "program_name": None,
            "task_properties": None,
            "owner_name": None,
            "owner_kind": None,
        })

    documento = {
        "schema_version": 1,
        "kind": "authoring_plan",
        "template": plano.get("template"),
        # Amarra a reversão à IDA. Sem isto, um plano de reversão poderia ser
        # executado contra uma saída que ele não desfez — e o registro diria
        # que desfez.
        "spec_sha256": plano.get("plan_sha256"),
        "creation_order": [],
        "steps": passos,
        # Reversão NÃO ACRESCENTA nada: as cinco listas saem vazias, e vazias
        # de propósito — omiti-las faria o schema recusar, e preenchê-las com
        # o que a ida acrescentou diria que a volta acrescenta o mesmo.
        "expected_tree": {"persistent_additions": [],
                          "task_additions": [],
                          "program_call_additions": [],
                          "text_replacements": [],
                          "library_preconditions": []},
        # Todas as famílias em ZERO, e `mutating_steps` contando os passos que
        # de fato mutam. A reversão não cria família nenhuma — mas ela MUTA, e
        # publicar `mutating_steps: 0` faria uma execução que remove objetos
        # parecer inócua no manifesto.
        "expected_diff": {"duts": 0, "gvls": 0, "functions": 0,
                          "function_blocks": 0, "programs": 0, "tasks": 0,
                          "program_calls": 0, "text_replacements": 0,
                          "mutating_steps": len(passos),
                          "total_steps": len(passos)},
        "text_hashes": {},
        "required_allowlist": sorted({"object:remove"}
                                     | ({"save_as"} if output_path else set())),
        # A LACUNA E DECLARADA, e nao implicita. Um plano `executable: False`
        # sem lacuna nenhuma e um plano que se recusa sem dizer por que -- e o
        # executor o rejeita com "nao executavel, e ainda assim nenhuma lacuna
        # declarada", que e a mensagem certa para um emissor com defeito.
        #
        # A reversao TAMBEM e run de prova: `remove_method` consome
        # `object:remove`, e nem a operacao nem o verbo foram exercidos contra o
        # produto. Declarar isso aqui e o que permite ao probe aceitar a
        # execucao pelo caminho de PROVING_OPERATIONS -- o mesmo que a ida usou
        # --, em vez de por um bypass.
        "measurement_gaps": [{
            "kind": "operation_not_field_proven",
            "capability": "remove_method",
            "required_maturity": "field_proven",
            "observed_maturity": "discovered",
            # `capability_maturity_below_required`, e nao um valor novo: o enum de
            # `reason` e FECHADO de proposito, e este descreve exatamente o
            # caso -- a capacidade existe no contrato e a maturidade dela
            # (`discovered`) esta abaixo da exigida. Acrescentar um sexto valor
            # para dizer a mesma coisa alargaria o vocabulario sem informacao
            # nova.
            "reason": "capability_maturity_below_required",
            "detail": ("a operacao de plano 'remove_method' tem API catalogada "
                       "(IScriptObject.remove, docs/api §superficie de MEMBRO), "
                       "mas nunca foi exercida contra o produto real. API "
                       "existente nao e operacao provada."),
        }],
        "verification_limits": [],
        "executable": False,
    }
    documento["plan_sha256"] = hashlib.sha256(
        canonical_json(documento).encode("utf-8")).hexdigest()
    resultado.plan = documento
    return resultado
