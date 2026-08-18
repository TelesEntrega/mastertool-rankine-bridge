"""R9.5A — o pacote de decisões: bloqueadores viram perguntas fechadas.

POR QUE ELE É GERADO, E NÃO ESCRITO
===================================
Um pacote escrito à mão descola do modelo na primeira revisão do corpus, e aí
os responsáveis passam a decidir sobre um retrato antigo. Gerado, ele é sempre
a leitura corrente de R9.2/R9.3/R9.4 — e a rastreabilidade até documento,
seção e célula vem de graça.

O QUE ELE FAZ, E O QUE ELE SE PROÍBE
====================================
Ele torna a revisão **executável**: cada bloqueador vira o que falta, quem
responde, o que está afetado, quais campos preencher e como saber que a
resposta chegou.

Ele **não propõe respostas**. Para o handshake, entrega tabela VAZIA — sugerir
`Req/Ack/Done` faria o responsável revisar a nossa proposta em vez de projetar
a interface dele, e o resultado pareceria confirmado quando seria só aceito.

`options` só existe quando o corpus sustenta alternativas. Onde não sustenta,
o campo fica vazio — e isso é informação, não omissão.

SAÍDA FORA DO REPOSITÓRIO
=========================
O pacote gerado carrega nomes de sequência, TAG e trechos do descritivo do
cliente. O GERADOR é publicável e testado com fixture sintética; a SAÍDA vai
para onde o operador mandar, e nunca para dentro da árvore.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "decision_package"

# Estados de uma decisão. `answered` não é `incorporated`: uma resposta que
# chegou e não foi refletida no modelo ainda bloqueia tudo que bloqueava.
DECISION_STATES = ("open", "sent", "answered", "incorporated", "withdrawn")

# Quem responde. Lista FECHADA — "alguém" não é destinatário.
RESPONDENTS = (
    "engenharia_de_seguranca",
    "engenharia_eletrica",
    "engenharia_de_automacao",
    "fornecedor_externo",
    "cliente",
)


@dataclass
class Decision:
    decision_id: str
    title: str
    missing: str
    respondent: str
    sources: tuple = ()
    affected_requirements: tuple = ()
    affected_equipment: tuple = ()
    affected_sequences: tuple = ()
    blocked_artifacts: tuple = ()
    options: tuple = ()
    fields_to_fill: tuple = ()
    resolution_criterion: str = ""
    impact_if_unresolved: str = ""
    state: str = "open"

    def __post_init__(self) -> None:
        if self.respondent not in RESPONDENTS:
            raise ValueError("destinatário %r fora de %s: 'alguém' não é "
                             "destinatário" % (self.respondent,
                                               list(RESPONDENTS)))
        if self.state not in DECISION_STATES:
            raise ValueError("estado %r fora de %s"
                             % (self.state, list(DECISION_STATES)))
        if not self.resolution_criterion:
            raise ValueError(
                "decisão %r sem critério objetivo de resolução: sem ele "
                "ninguém sabe quando a resposta chegou" % self.decision_id)
        if not self.fields_to_fill:
            raise ValueError(
                "decisão %r sem campos a preencher: uma pergunta sem campos "
                "produz prosa, e prosa não fecha bloqueador"
                % self.decision_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id, "title": self.title,
            "missing": self.missing, "respondent": self.respondent,
            "state": self.state,
            "sources": list(self.sources),
            "affected_requirements": list(self.affected_requirements),
            "affected_equipment": list(self.affected_equipment),
            "affected_sequences": list(self.affected_sequences),
            "blocked_artifacts": list(self.blocked_artifacts),
            "options": list(self.options),
            "fields_to_fill": list(self.fields_to_fill),
            "resolution_criterion": self.resolution_criterion,
            "impact_if_unresolved": self.impact_if_unresolved,
        }


@dataclass
class DecisionPackage:
    project: str
    decisions: list = field(default_factory=list)

    def by_multiplier(self) -> list:
        """Ordenadas por quanto DESTRAVAM, e não por ordem de descoberta.

        Quem revisa tem tempo finito: uma decisão que solta 51 contratos em 13
        sequências vale ser lida antes de uma que solta três artefatos.

        `affected_equipment` NÃO entra no peso. Ele mede a abrangência do
        SUJEITO, não do desbloqueio — a decisão sobre famílias de FB toca 65
        dispositivos e destrava três artefatos, e somá-los a colocaria à
        frente do handshake. Ele fica só como desempate.
        """
        def peso(d):
            return (-(len(d.affected_sequences) + len(d.blocked_artifacts)),
                    -len(d.affected_equipment), d.decision_id)
        return sorted(self.decisions, key=peso)

    def summary(self) -> dict[str, Any]:
        por_destinatario: dict = {}
        for d in self.decisions:
            por_destinatario[d.respondent] = por_destinatario.get(
                d.respondent, 0) + 1
        return {
            "decisions": len(self.decisions),
            "by_respondent": dict(sorted(por_destinatario.items())),
            "open": sum(1 for d in self.decisions if d.state == "open"),
            "incorporated": sum(1 for d in self.decisions
                                if d.state == "incorporated"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "project": self.project,
            "decisions": [d.to_dict() for d in self.by_multiplier()],
            "summary": self.summary(),
        }


# =============================================================================
# construção a partir do rascunho
# =============================================================================

def _fontes(origem) -> tuple:
    if not origem:
        return ()
    partes = [origem.get("document")]
    if origem.get("sheet"):
        partes.append("aba %s" % origem["sheet"])
    if origem.get("locator"):
        partes.append(origem["locator"])
    if origem.get("version"):
        partes.append("versão %s" % origem["version"])
    return tuple(p for p in partes if p)


def _handshake(draft) -> Decision | None:
    """A maior multiplicadora: ela atinge todas as interações de fronteira."""
    contratos = draft.boundary_contracts
    if not contratos:
        return None
    sequencias = tuple(sorted({c["source_sequence"] for c in contratos}))
    return Decision(
        decision_id="DEC-HANDSHAKE",
        title="Fronteiras e contrato de interface",
        missing=("%d interação(ões) atravessam fronteira de dono e nenhuma "
                 "tem produtor, consumidor ou sinais definidos"
                 % len(contratos)),
        respondent="engenharia_de_automacao",
        sources=("descritivo lógico — interações detectadas por verbo",),
        affected_sequences=sequencias,
        blocked_artifacts=("inter_plc_requirements", "GVL_Communication",
                           "FB_InterPlcInterface", "DUTs de interface"),
        # SEM opções: o corpus não sustenta alternativa nenhuma aqui.
        options=(),
        fields_to_fill=(
            "fronteira real (robô / CLP / equipamento de terceiro)",
            "produtor", "consumidor", "quem inicia a operação",
            "condição de pronto", "confirmação de execução", "conclusão",
            "falha", "reset", "timeout",
            "comportamento na perda de comunicação", "ownership do sinal",
        ),
        resolution_criterion=("cada interação listada tem produtor, consumidor "
                              "e a tabela de sinais preenchida"),
        impact_if_unresolved=("sem isto, gerar a interface inventaria o "
                              "contrato mais crítico do projeto"),
    )


def _seguranca(draft, plant) -> Decision | None:
    """NR-12 e I/O de segurança vão JUNTOS.

    São duas lacunas correlacionadas — comportamento ausente do descritivo e
    classes vazias na planilha —, e separá-las produziria duas respostas
    parciais que não fecham nenhuma das duas.
    """
    inventario = [b for b in draft.blockers
                  if b.blocker_id.startswith("BLK-INV")]
    documentais = [b for b in draft.blockers
                   if "seguran" in b.detail.lower() or "NR-12" in b.detail]
    if not inventario and not documentais:
        return None
    return Decision(
        decision_id="DEC-SEGURANCA",
        title="NR-12 e classes de I/O de segurança",
        missing=("%d classe(s) de I/O de segurança declaradas e vazias, e "
                 "%d pendência(s) documental(is) de segurança"
                 % (len(inventario), len(documentais))),
        respondent="engenharia_de_seguranca",
        sources=tuple(sorted({s for b in inventario + documentais
                              for s in _fontes(b.origin)})),
        affected_equipment=tuple(sorted(
            p.tag for p in plant.points
            if any(t in (p.description.value or "").lower()
                   for t in ("emerg", "barreira", "safety")))),
        blocked_artifacts=("GVL_Safety_Requirements", "device_channel_map",
                           "io_addressing", "mapa físico → variável"),
        options=("arquitetura safety dedicada (CPS)",
                 "arquitetura convencional com relé de segurança"),
        fields_to_fill=(
            "dispositivos e canais", "classificação (EDS/SDS/ED-CPS/SD-CPS)",
            "controlador responsável", "arquitetura safety ou convencional",
            "estados seguros", "zonas", "reset", "rearme", "diagnóstico",
            "interface com a automação padrão",
        ),
        resolution_criterion=("as quatro colunas de segurança preenchidas na "
                              "planilha e as zonas NR-12 descritas"),
        impact_if_unresolved=("o endereçamento fica incompleto e a GVL de "
                              "segurança permanece bloqueada. Mesmo com a "
                              "resposta, GERAR lógica de segurança segue fora "
                              "da v1"),
    )


def _sequencias_em_prosa(draft) -> Decision | None:
    prosa = [s for s in draft.sequence_architecture
             if s["sequence_status"] == "requires_human_structuring"]
    if not prosa:
        return None
    return Decision(
        decision_id="DEC-SEQUENCIAS",
        title="Sequências sem tabela de estado",
        missing=("%d sequência(s) descrevem comportamento só em prosa"
                 % len(prosa)),
        respondent="engenharia_de_automacao",
        sources=("descritivo lógico — subseções sem tabela",),
        affected_sequences=tuple(s["sequence_id"] for s in prosa),
        blocked_artifacts=("FB_SequenceState", "behavior_complete"),
        options=(),
        fields_to_fill=("estado", "ação", "condição de avanço",
                        "feedback esperado", "próximo estado", "falha",
                        "timeout", "reset/retomada"),
        resolution_criterion=("cada sequência listada tem tabela no mesmo "
                              "nível das já estruturadas"),
        impact_if_unresolved=("extraí-las de prosa produziria máquina de "
                              "estados plausível e não medida"),
    )


def _familias_de_fb(draft) -> Decision | None:
    familias = [e for e in draft.elements
                if e.kind == "fb" and e.name.startswith("FB_")
                and "CLASSES de I/O" in e.rationale]
    if not familias:
        return None
    return Decision(
        decision_id="DEC-FAMILIAS-FB",
        title="Famílias de FUNCTION_BLOCK",
        missing=("%d família(s) derivadas das classes de I/O observadas, sem "
                 "comparação com o padrão da empresa" % len(familias)),
        respondent="engenharia_de_automacao",
        sources=("R9.2 inventário — classes de I/O por dispositivo",),
        affected_equipment=tuple(sorted(
            {t for e in familias for t in e.satisfies})),
        blocked_artifacts=tuple(e.name for e in familias),
        options=("manter as famílias derivadas",
                 "especializar por tipo de equipamento",
                 "reusar FBs já existentes",
                 "separar diagnóstico, comando e I/O"),
        fields_to_fill=("padrão de nomes", "entradas obrigatórias",
                        "saídas obrigatórias", "temporizações", "contadores",
                        "alarmes", "modo manual/automático",
                        "permissivos não críticos"),
        resolution_criterion="cada família aprovada, substituída ou recusada",
        impact_if_unresolved=("os FBs propostos podem divergir do padrão real "
                              "e obrigariam a refazer a arquitetura"),
    )


def _terceiros(draft) -> list:
    """`1800FZ` e FAT: impacto DERIVADO das referências, nunca da sigla."""
    saida = []
    for bloqueador in draft.blockers:
        baixo = bloqueador.detail.lower()
        if "fornecedor" not in baixo and "confirmar com" not in baixo:
            continue
        saida.append(Decision(
            decision_id="DEC-%s" % bloqueador.subject,
            title="Informação de terceiro — %s" % bloqueador.subject,
            missing=bloqueador.detail[:240],
            respondent="fornecedor_externo",
            sources=_fontes(bloqueador.origin),
            affected_requirements=tuple(bloqueador.affected_requirements),
            blocked_artifacts=tuple(bloqueador.affected_elements),
            options=(),
            fields_to_fill=("resposta do fornecedor",
                            "documento de referência",
                            "sequência(s) afetada(s) confirmada(s)"),
            resolution_criterion=("resposta registrada e ligada à(s) "
                                  "sequência(s) que a citam"),
            impact_if_unresolved=("o alcance permanece o medido pelas "
                                  "referências do corpus, e não pode ser "
                                  "ampliado nem reduzido por interpretação"),
        ))
    return saida


def build_package(*, draft, plant, project: str = "planta") -> DecisionPackage:
    pacote = DecisionPackage(project=project)
    for decisao in (_handshake(draft), _seguranca(draft, plant),
                    _sequencias_em_prosa(draft), _familias_de_fb(draft)):
        if decisao is not None:
            pacote.decisions.append(decisao)
    pacote.decisions.extend(_terceiros(draft))
    return pacote


# =============================================================================
# renderização
# =============================================================================

def _lista(itens, vazio="—") -> str:
    return "\n".join("- %s" % i for i in itens) if itens else vazio


def render_decision(decisao: Decision) -> str:
    partes = [
        "# %s — %s" % (decisao.decision_id, decisao.title),
        "",
        "> **Destinatário:** `%s` · **Estado:** `%s`"
        % (decisao.respondent, decisao.state),
        "",
        "## O que falta",
        "",
        decisao.missing,
        "",
        "## Origem",
        "",
        _lista(decisao.sources),
        "",
        "## Afetados",
        "",
        "**Sequências**", "", _lista(decisao.affected_sequences),
        "",
        "**Equipamentos / pontos**", "", _lista(decisao.affected_equipment),
        "",
        "**Requisitos**", "", _lista(decisao.affected_requirements),
        "",
        "## Artefatos bloqueados",
        "",
        _lista(decisao.blocked_artifacts),
        "",
    ]
    if decisao.options:
        partes += ["## Opções que o corpus sustenta", "",
                   _lista(decisao.options), ""]
    else:
        partes += ["## Opções", "",
                   "_O corpus não sustenta alternativas aqui. Nenhuma opção "
                   "é sugerida — sugerir faria a revisão avaliar a nossa "
                   "proposta em vez de projetar a solução._", ""]
    partes += [
        "## Campos a preencher",
        "",
        "| Campo | Resposta |",
        "|---|---|",
    ]
    partes += ["| %s | |" % c for c in decisao.fields_to_fill]
    partes += [
        "",
        "## Critério objetivo de resolução",
        "",
        decisao.resolution_criterion,
        "",
        "## Impacto de não resolver",
        "",
        decisao.impact_if_unresolved,
        "",
    ]
    return "\n".join(partes)


def render_index(pacote: DecisionPackage) -> str:
    linhas = [
        "# Decisões pendentes — %s" % pacote.project,
        "",
        "> Gerado a partir do rascunho de arquitetura. **Nenhuma resposta é "
        "proposta aqui.**",
        "",
        "Ordenadas por quanto **destravam** — quem revisa tem tempo finito.",
        "",
        "| # | Decisão | Destinatário | Sequências | Artefatos | Estado |",
        "|---|---|---|---:|---:|---|",
    ]
    for ordem, d in enumerate(pacote.by_multiplier(), start=1):
        linhas.append("| %d | [%s](%s.md) — %s | `%s` | %d | %d | `%s` |"
                      % (ordem, d.decision_id, d.decision_id, d.title,
                         d.respondent, len(d.affected_sequences),
                         len(d.blocked_artifacts), d.state))
    linhas += [
        "",
        "## O que NÃO está aqui",
        "",
        "- nenhuma sugestão de `Req`/`Ack`/`Done`;",
        "- nenhuma lógica de segurança;",
        "- nenhuma alocação entre controladores;",
        "- nenhuma máquina de estados extraída de prosa.",
        "",
        "## Quando uma decisão fecha",
        "",
        "`answered` **não é** `incorporated`. Uma resposta que chegou e não "
        "foi refletida no modelo continua bloqueando o que bloqueava.",
        "",
    ]
    return "\n".join(linhas)


def write_package(pacote: DecisionPackage, destino) -> list:
    """Grava o pacote. O destino fica FORA da árvore do repositório: o
    conteúdo carrega nome de sequência, TAG e trecho de descritivo."""
    raiz = Path(destino)
    raiz.mkdir(parents=True, exist_ok=True)
    escritos = []

    alvo = raiz / "DECISOES-PENDENTES.md"
    alvo.write_text(render_index(pacote), encoding="utf-8", newline="\n")
    escritos.append(alvo)

    for decisao in pacote.decisions:
        alvo = raiz / ("%s.md" % decisao.decision_id)
        alvo.write_text(render_decision(decisao), encoding="utf-8",
                        newline="\n")
        escritos.append(alvo)

    alvo = raiz / "decision-status.json"
    alvo.write_text(json.dumps(pacote.to_dict(), ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
    escritos.append(alvo)
    return escritos
