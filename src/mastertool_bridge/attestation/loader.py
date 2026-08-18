"""A maturidade medida, carregada em runtime — nunca escrita no código.

POR QUE ESTE MÓDULO EXISTE
==========================
Até 2026-08-03 o `EXECUTOR_CONTRACT` do planner carregava, por operação:

    "cataloged": True, "field_proven": True,
    "evidence": "docs/46 (W6, run-033)"

Dezenove entradas assim. Enquanto a árvore era só interna, isso era um resumo
do que estava medido ali do lado. Publicado, virou outra coisa: o pacote
público **promove capacidades a `field_proven` por literal escrito no código**,
citando documentos que não estão nele. Qualquer instalação herda a promoção sem
carregar evidência nenhuma.

É o mesmo fail-open que `docs/42` §4 fechou uma vez — uma spec com
FUNCTION_BLOCK saía `executable: True` porque a API estava catalogada, embora
ninguém tivesse provado que um FB sobrevive a `save_as` e compila. A distinção
entre "a API existe" e "a operação funciona na cadeia" foi reintroduzida pela
publicação, num nível acima: agora é "o código diz que foi provado" contra "há
evidência carregada de que foi".

    EXECUTOR_CONTRACT        propriedade TÉCNICA da operação
    CAPABILITY_ATTESTATION   maturidade MEDIDA, carregada e conferível

Sem attestation carregada e válida, a maturidade efetiva de qualquer
capacidade é `discovered`. O core não infere maturidade de comentário, de nome
de run, de documento ausente nem de histórico embutido.

DUAS PERGUNTAS DIFERENTES, DOIS CAMPOS DIFERENTES
=================================================
`structurally_valid` responde "este documento está bem formado?".
`evidence_confirmed` responde "a evidência que ele cita foi conferida?".

Um documento bem formado **não é** um documento respaldado. Fundir as duas
respostas faria uma attestation sintaticamente perfeita, apontando para um
bundle que ninguém abriu, valer o mesmo que uma conferida — e é justamente
essa diferença que separa medição de declaração neste projeto.

Conferência que não pôde ser feita entra em `unresolved`, nunca em confirmada.
Ausência de conferência não é conferência bem-sucedida.

RECUSA, NUNCA FALLBACK
======================
Attestation inválida **não** faz o carregador ignorá-la e voltar ao
comportamento anterior. Voltar ao anterior seria promover por código estático
outra vez — exatamente o que este módulo remove. Documento inválido derruba a
maturidade para `discovered` e diz por quê.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastertool_bridge.templates.profile import (
    MATURITY_SCALE,
    MIN_INDEPENDENT_RUNS,
)

ATTESTATION_SCHEMA_VERSION = 1

# O grau que vale quando não há evidência carregada. É o primeiro da escala de
# propósito: `discovered` significa "catalogada, nunca exercida", e é
# exatamente o que o core pode afirmar sozinho.
MATURITY_FLOOR = MATURITY_SCALE[0]

REASON_NOT_LOADED = "capability_attestation_not_loaded"
REASON_REFUSED = "capability_attestation_refused"
REASON_BELOW_REQUIRED = "capability_maturity_below_required"
REASON_EVIDENCE_NOT_CONFIRMED = "capability_evidence_not_confirmed"
REASON_CONTEXT_MISSING = "capability_attestation_validation_context_missing"
REASON_CONTRACT_MISMATCH = "capability_attestation_core_contract_mismatch"

# Sentinela: "use o registro canônico". Existe para que passar `None` NÃO
# desligue a conferência de nome de capacidade — o chamador pode SUBSTITUIR o
# registro, nunca dispensá-lo. Ver `planner/capabilities.py` (achado RV1-3).
_CANONICO = object()

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

# Campos aceitos, nível a nível. Conjunto FECHADO: campo desconhecido recusa o
# documento inteiro, em vez de ser ignorado. Um campo que o carregador não
# entende pode ser justamente aquele que mudaria o significado do resto.
_TOPO_OBRIGATORIOS = frozenset((
    "schema_version", "core_contract_sha256", "issued_from_commit",
    "product", "product_version", "template_profile", "capabilities",
))
_TOPO_OPCIONAIS = frozenset(("generated_at", "notes"))

_CAP_OBRIGATORIOS = frozenset((
    "maturity", "bundle_sha256", "evidence_id",
))

# `independent_runs` saiu dos obrigatórios e virou DERIVADO (achado RV2-2).
# Enquanto ele era a fonte, o grau `repeatable` das treze capacidades da
# árvore interna vinha de um inteiro digitado — sem id de execução, sem
# pacote por execução, sem comparação. Ele continua aceito na serialização,
# mas agora só como redundância conferida: o valor que decide é
# `len(set(qualification_evidence.run_ids))`.
#
# `run_ids` deixou de ser campo de topo e passou a viver dentro de
# `qualification_evidence`, junto do relatório que os compara. Separá-los
# permitia listar dez ids sem nada que dissesse que as dez execuções foram
# equivalentes entre si e independentes duas a duas.
_CAP_OPCIONAIS = frozenset((
    "independent_runs", "qualification_evidence", "notes",
))


@dataclass
class AttestationLoad:
    """O resultado de carregar uma attestation.

    `capabilities` é a maturidade EFETIVA por capacidade — o que o planner deve
    usar. Capacidade ausente do documento não aparece aqui, e o chamador a
    trata como `discovered`; ausência não é erro, é ausência.
    """

    schema_version: int | None = None
    core_contract_sha256: str | None = None
    issued_from_commit: str | None = None
    product: str | None = None
    product_version: str | None = None
    template_profile: str | None = None

    structurally_valid: bool = False
    capabilities: dict[str, str] = field(default_factory=dict)
    evidence_confirmed: dict[str, bool] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def declared_maturity_of(self, capability: str) -> str:
        """O que a attestation ESCREVE. Não é o que o planner pode usar.

        Existe para diagnóstico e para o relatório — nunca para decidir. Quem
        decide é `effective_maturity_of`.
        """
        if not self.structurally_valid:
            return MATURITY_FLOOR
        return self.capabilities.get(capability, MATURITY_FLOOR)

    def effective_maturity_of(self, capability: str) -> str:
        """O grau que o planner pode usar — declarado E respaldado.

        ACHADO RV1-1, e ele é o motivo desta separação existir: o carregador
        CALCULAVA `evidence_confirmed` e ninguém consumia o resultado. Uma
        attestation apontando para um bundle que ninguém abriu promovia igual
        a uma conferida, e a distinção entre validade estrutural e confiança na
        evidência era decorativa.

        Evidência não confirmada derruba a capacidade para o piso. NÃO
        invalida o documento nem as outras capacidades: lacuna individual de
        evidência é diferente de erro estrutural global.
        """
        declarada = self.declared_maturity_of(capability)
        if declarada == MATURITY_FLOOR:
            return MATURITY_FLOOR
        if not self.evidence_confirmed.get(capability):
            return MATURITY_FLOOR
        return declarada

    def reason_for(self, capability: str) -> str | None:
        """Por que esta capacidade não está no grau que alguém esperava."""
        if not self.structurally_valid:
            return REASON_REFUSED
        if capability not in self.capabilities:
            return REASON_NOT_LOADED
        if not self.evidence_confirmed.get(capability):
            return REASON_EVIDENCE_NOT_CONFIRMED
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "core_contract_sha256": self.core_contract_sha256,
            "issued_from_commit": self.issued_from_commit,
            "product": self.product,
            "product_version": self.product_version,
            "template_profile": self.template_profile,
            "structurally_valid": self.structurally_valid,
            "declared_capabilities": dict(self.capabilities),
            "effective_capabilities": {
                nome: self.effective_maturity_of(nome)
                for nome in self.capabilities},
            "evidence_confirmed": dict(self.evidence_confirmed),
            "problems": list(self.problems),
            "unresolved": list(self.unresolved),
        }


DEFAULT_ATTESTATION_DIR = "config/attestation"


def load_default_attestation(repo_root: Path | str, **kwargs) -> AttestationLoad | None:
    """Carrega a attestation que a árvore versiona, se houver uma.

    Devolve `None` quando não há — e no pacote PÚBLICO não há, de propósito:
    `config/attestation/` não é publicado porque cita bundles e runs internos.
    Lá o resultado é `None`, toda capacidade fica `discovered`, e o planner
    recusa plano de autoria. Esse é o comportamento correto do núcleo, não uma
    degradação: ele não tem evidência, e não deve fingir que tem.

    Mais de um arquivo é RECUSA, não escolha. Duas attestations na mesma
    árvore levantam a pergunta "qual vale?", e responder por ordem alfabética
    seria decidir por acaso.
    """
    raiz = Path(repo_root) / DEFAULT_ATTESTATION_DIR
    if not raiz.is_dir():
        return None
    arquivos = sorted(raiz.glob("*.json"))
    if not arquivos:
        return None
    if len(arquivos) > 1:
        recusa = AttestationLoad()
        recusa.problems.append(
            "%d attestations em %s: %s. Qual delas vale é decisão de quem as "
            "emitiu, e escolher por ordem alfabética seria decidir por acaso"
            % (len(arquivos), raiz, ", ".join(a.name for a in arquivos)))
        return recusa
    try:
        payload = json.loads(arquivos[0].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        recusa = AttestationLoad()
        recusa.problems.append("%s ilegível: %s" % (arquivos[0], exc))
        return recusa
    return load_attestation(payload, **kwargs)


def canonical_bytes(payload: Any) -> bytes:
    """Representação canônica de uma attestation.

    Chaves ordenadas, sem espaço supérfluo, UTF-8. Existe para que o mesmo
    conteúdo lógico produza sempre o mesmo digest — duas construções com as
    chaves em ordem diferente não podem valer documentos diferentes, senão o
    hash deixa de identificar o conteúdo e passa a identificar a digitação.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _conferir_igual(nome: str, declarado: Any, esperado: Any,
                    problems: list[str], unresolved: list[str]) -> None:
    """Confere um campo de identidade contra o que o chamador espera.

    Esperado ausente NÃO é conferência bem-sucedida: entra em `unresolved`. O
    O caso concreto é `product_version` e `template_profile`: o carregador não
    tem como saber contra qual produto ou template o chamador espera operar.
    Tratar "não sei" como "confere" faria a attestation de um contexto valer
    para outro.
    """
    if esperado is None:
        unresolved.append(
            "%s não foi conferido: o chamador não informou o valor esperado. "
            "Ausência de conferência não é conferência" % nome)
        return
    if declarado != esperado:
        problems.append(
            "%s: a attestation declara %r e o esperado é %r. Uma attestation "
            "vale para o que ela mediu, e para mais nada"
            % (nome, declarado, esperado))


def load_attestation(payload: Any, *,
                     expected_product: str | None = None,
                     expected_product_version: str | None = None,
                     expected_template_profile: str | None = None,
                     bundle_root: Path | str | None = None,
                     known_capabilities: Any = _CANONICO) -> AttestationLoad:
    """Carrega e confere uma attestation. Nunca levanta.

    `known_capabilities` é o conjunto de operações que o `EXECUTOR_CONTRACT`
    conhece. Informado, uma capacidade fora dele recusa o documento: attestar
    o que o planner não sabe executar é declarar sobre coisa nenhuma.

    `bundle_root` é onde os Evidence Bundles vivem. Ausente, a integridade do
    bundle entra em `unresolved` — o documento pode continuar estruturalmente
    válido, e a confiança na evidência fica explicitamente não confirmada.
    """
    resultado = AttestationLoad()

    if payload is None:
        resultado.problems.append(
            "attestation ausente. Sem ela nenhuma capacidade passa de %r — o "
            "core não infere maturidade de comentário nem de documento que não "
            "está no pacote" % MATURITY_FLOOR)
        return resultado

    if not isinstance(payload, dict):
        resultado.problems.append(
            "attestation: esperado objeto, recebido %s"
            % type(payload).__name__)
        return resultado

    # --- topo -------------------------------------------------------------
    desconhecidos = sorted(set(payload) - _TOPO_OBRIGATORIOS - _TOPO_OPCIONAIS)
    if desconhecidos:
        resultado.problems.append(
            "campo(s) desconhecido(s) no topo: %s. O conjunto é fechado — um "
            "campo que este carregador não entende pode ser o que mudaria o "
            "significado dos outros" % ", ".join(desconhecidos))

    faltando = sorted(_TOPO_OBRIGATORIOS - set(payload))
    if faltando:
        resultado.problems.append(
            "campo(s) obrigatório(s) ausente(s): %s" % ", ".join(faltando))
        return resultado

    resultado.schema_version = payload.get("schema_version")
    resultado.core_contract_sha256 = payload.get("core_contract_sha256")
    resultado.issued_from_commit = payload.get("issued_from_commit")
    resultado.product = payload.get("product")
    resultado.product_version = payload.get("product_version")
    resultado.template_profile = payload.get("template_profile")

    if resultado.schema_version != ATTESTATION_SCHEMA_VERSION:
        resultado.problems.append(
            "schema_version %r desconhecido: este carregador entende %d. "
            "Ler um documento de versão que não se conhece é adivinhar o "
            "significado dos campos"
            % (resultado.schema_version, ATTESTATION_SCHEMA_VERSION))
        return resultado

    if not isinstance(resultado.issued_from_commit, str) or not _COMMIT_RE.match(
            resultado.issued_from_commit or ""):
        resultado.problems.append(
            "issued_from_commit %r não parece um commit (7 a 40 hex)"
            % (resultado.issued_from_commit,))

    # O VÍNCULO NORMATIVO é o contrato, e não o commit.
    #
    # `issued_from_commit` NÃO é comparado com o `HEAD`, de propósito: uma
    # attestation versionada dentro da árvore nunca aponta para o commit que a
    # contém, e comparar com o HEAD a faria nascer inválida. Ele é
    # proveniência — serve para achar de onde ela veio, nunca para decidir se
    # ela vale.
    #
    # Divergência de contrato é INCOMPATIBILIDADE GLOBAL, e não lacuna de uma
    # capacidade: o documento inteiro foi medido sob outras regras.
    if not isinstance(resultado.core_contract_sha256, str) or not _SHA256_RE.match(
            resultado.core_contract_sha256 or ""):
        resultado.problems.append(
            "core_contract_sha256 %r não é hex de 64 caracteres"
            % (resultado.core_contract_sha256,))
    else:
        from mastertool_bridge.contract.fingerprint import core_contract_sha256

        corrente = core_contract_sha256()
        if resultado.core_contract_sha256.lower() != corrente:
            resultado.problems.append(
                "%s: a attestation foi emitida sob o contrato %s e este núcleo "
                "aplica %s. Capacidades, mapeamento, pisos de execução ou "
                "política de evidência mudaram — a medição de campo continua "
                "existindo, mas não descreve mais este sistema"
                % (REASON_CONTRACT_MISMATCH,
                   resultado.core_contract_sha256[:12], corrente[:12]))

    _conferir_igual("product", resultado.product, expected_product,
                    resultado.problems, resultado.unresolved)
    _conferir_igual("product_version", resultado.product_version,
                    expected_product_version,
                    resultado.problems, resultado.unresolved)
    _conferir_igual("template_profile", resultado.template_profile,
                    expected_template_profile,
                    resultado.problems, resultado.unresolved)

    capacidades = payload.get("capabilities")
    if not isinstance(capacidades, dict):
        resultado.problems.append("capabilities: esperado objeto")
        return resultado
    if not capacidades:
        resultado.problems.append(
            "capabilities vazio. Uma attestation que não atesta nada não é "
            "uma attestation — se a intenção é não promover nada, o caminho é "
            "não carregar documento nenhum")
        return resultado

    # `None` NÃO desliga a conferência (achado RV1-3): ele cai no registro
    # canônico, igual à omissão. Substituir o conjunto é possível — um teste
    # precisa disso —, dispensá-lo não.
    if known_capabilities is _CANONICO or known_capabilities is None:
        from mastertool_bridge.planner.capabilities import KNOWN_CAPABILITIES

        conhecidas = set(KNOWN_CAPABILITIES)
    else:
        conhecidas = set(known_capabilities)

    # --- capacidade a capacidade -------------------------------------------
    for nome in sorted(capacidades):
        entrada = capacidades[nome]
        rotulo = "capabilities[%r]" % nome

        if nome not in conhecidas:
            resultado.problems.append(
                "%s: capacidade não existe no contrato do executor. Attestar "
                "o que o planner não sabe executar é declarar sobre coisa "
                "nenhuma" % rotulo)
            continue

        if not isinstance(entrada, dict):
            resultado.problems.append("%s: esperado objeto" % rotulo)
            continue

        extras = sorted(set(entrada) - _CAP_OBRIGATORIOS - _CAP_OPCIONAIS)
        if extras:
            resultado.problems.append(
                "%s: campo(s) desconhecido(s): %s" % (rotulo, ", ".join(extras)))
        ausentes = sorted(_CAP_OBRIGATORIOS - set(entrada))
        if ausentes:
            resultado.problems.append(
                "%s: campo(s) obrigatório(s) ausente(s): %s"
                % (rotulo, ", ".join(ausentes)))
            continue

        maturidade = entrada.get("maturity")
        if maturidade not in MATURITY_SCALE:
            resultado.problems.append(
                "%s: maturidade %r fora da escala: %s"
                % (rotulo, maturidade, ", ".join(MATURITY_SCALE)))
            continue

        # `independent_runs`, quando presente, é REDUNDÂNCIA conferida — nunca
        # a fonte. Ele existe para que um documento lido por humano mostre o
        # número sem obrigar a contar a lista; discordar da lista é erro dele.
        runs_declarado = entrada.get("independent_runs")
        if runs_declarado is not None and (
                not isinstance(runs_declarado, int)
                or isinstance(runs_declarado, bool) or runs_declarado < 0):
            resultado.problems.append(
                "%s: independent_runs %r não é inteiro não negativo"
                % (rotulo, runs_declarado))
            continue

        # PISO DERIVADO, e nao tabelado: qualquer grau acima de `discovered`
        # exige ao menos UMA execucao.
        #
        # ACHADO na revisao adversarial: `MIN_INDEPENDENT_RUNS` so tem entrada
        # de `repeatable` para cima, entao `field_proven` com
        # `independent_runs: 0` era ACEITO -- e `field_proven` e exatamente o
        # limiar que o planner exige para considerar um plano executavel. O
        # buraco ficava no unico ponto que decide.
        #
        # `field_proven` significa "exercida contra o produto real numa cadeia
        # que persistiu e compilou". Zero execucoes contradiz a definicao, e
        # aceitar isso seria promover por declaracao — o que este modulo
        # inteiro existe para impedir.
        if maturidade != MATURITY_FLOOR and runs_declarado == 0:
            resultado.problems.append(
                "%s: %r com 0 execucoes. Qualquer grau acima de %r significa "
                "que alguem exerceu a operacao pelo menos uma vez; zero "
                "execucoes e declaracao, nao medicao"
                % (rotulo, maturidade, MATURITY_FLOOR))
            continue

        # DE `repeatable` PARA CIMA A EVIDÊNCIA É DE CONJUNTO (achado RV2-2).
        #
        # O conjunto de graus que exigem isso não é uma lista nova: é
        # exatamente `MIN_INDEPENDENT_RUNS`, que já é a norma de quantas
        # execuções cada grau pede. Uma segunda lista aqui poderia divergir
        # daquela, e duas versões da mesma norma são uma a mais do que existe.
        #
        # `field_proven` fica de fora de propósito: ele pede UMA execução
        # completa e verificável, e isso o pacote citado já prova sozinho.
        minimo = MIN_INDEPENDENT_RUNS.get(maturidade)
        qualificacao = entrada.get("qualification_evidence")
        if minimo is not None:
            if not isinstance(qualificacao, dict):
                resultado.problems.append(
                    "%s: %r exige qualification_evidence com os ids das "
                    "execuções e o relatório que as compara. Um inteiro "
                    "declarando %s execuções não distingue dez execuções de "
                    "uma execução copiada nove vezes"
                    % (rotulo, maturidade, minimo))
                continue
            ids = qualificacao.get("run_ids")
            if isinstance(ids, list) and runs_declarado is not None and (
                    runs_declarado != len(set(x for x in ids
                                              if isinstance(x, str)))):
                resultado.problems.append(
                    "%s: declara independent_runs=%d e lista %d id(s) "
                    "distinto(s). Os dois descrevem a mesma coisa, e o que "
                    "vale é a lista"
                    % (rotulo, runs_declarado,
                       len(set(x for x in ids if isinstance(x, str)))))
                continue
        elif qualificacao is not None and not isinstance(qualificacao, dict):
            resultado.problems.append(
                "%s: qualification_evidence: esperado objeto" % rotulo)
            continue

        sha = entrada.get("bundle_sha256")
        if not isinstance(sha, str) or not _SHA256_RE.match(sha or ""):
            resultado.problems.append(
                "%s: bundle_sha256 %r não é hex de 64 caracteres. Referência "
                "documental não substitui hash de pacote: um caminho de "
                "documento não prova integridade de nada"
                % (rotulo, entrada.get("bundle_sha256")))
            continue

        evidencia = entrada.get("evidence_id")
        if not isinstance(evidencia, str) or not evidencia.strip():
            resultado.problems.append(
                "%s: evidence_id obrigatório e não vazio" % rotulo)
            continue

        resultado.capabilities[nome] = maturidade

        # AS DUAS CONDIÇÕES, e ambas rodam. Parar na primeira esconderia a
        # segunda de quem lê o diagnóstico, e é o conjunto de problemas que
        # diz o que precisa ser medido de novo.
        confirmado = _conferir_bundle(
            rotulo, sha, bundle_root, resultado.problems, resultado.unresolved)
        if minimo is not None:
            from mastertool_bridge.evidence.qualification import (
                verify_qualification,
            )

            check = verify_qualification(nome, qualificacao, bundle_root,
                                         minimo)
            resultado.problems.extend(check.problems)
            resultado.unresolved.extend(check.unresolved)
            confirmado = confirmado and check.confirmed
        resultado.evidence_confirmed[nome] = confirmado

    if not resultado.capabilities:
        resultado.problems.append(
            "nenhuma capacidade sobreviveu à conferência")

    resultado.structurally_valid = not resultado.problems
    if not resultado.structurally_valid:
        # RECUSA, e não "ignora e usa o de antes". Voltar ao comportamento
        # anterior seria promover por código estático outra vez, que é o que
        # este módulo existe para remover.
        resultado.capabilities = {}
        resultado.evidence_confirmed = {}
    return resultado


def _conferir_bundle(rotulo: str, sha: str, bundle_root: Path | str | None,
                     problems: list[str], unresolved: list[str]) -> bool:
    """Confere que o bundle citado existe, está íntegro e é aquele mesmo.

    Devolve se a evidência foi CONFIRMADA. Não confirmar não derruba a validade
    estrutural — derruba a confiança, que é registrada em separado.
    """
    if bundle_root is None:
        unresolved.append(
            "%s: integridade do bundle não conferida (nenhum `bundle_root` "
            "informado). O documento pode estar bem formado e mesmo assim "
            "apontar para um pacote que ninguém abriu" % rotulo)
        return False

    from mastertool_bridge.evidence.bundle import verify_bundle

    raiz = Path(bundle_root)
    candidatos = [d for d in (raiz.iterdir() if raiz.is_dir() else [])
                  if d.is_dir()]
    for pacote in candidatos:
        manifesto = pacote / "manifest.json"
        if not manifesto.is_file():
            continue
        try:
            dados = json.loads(manifesto.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if dados.get("bundle_sha256") != sha:
            continue
        verificacao = verify_bundle(pacote)
        if not verificacao.intact:
            problems.append(
                "%s: o bundle %s existe e NÃO está íntegro: %s. Pacote "
                "alterado depois do selo não respalda nada"
                % (rotulo, sha[:12], "; ".join(verificacao.problems)))
            return False

        # ÍNTEGRO NÃO É COMPLETO — distinção do achado RV1, e a completude
        # agora vem RECOMPUTADA do layout (achado RV2-1).
        #
        # Antes ela era lida de `manifest.status`. O `bundle_sha256` cobre o
        # conjunto de ARQUIVOS e o próprio selo exclui o manifesto ao hashear,
        # então `status` e `missing_required` ficavam fora de tudo que o hash
        # protege: bastava remover um arquivo obrigatório, recomputar `files` e
        # `bundle_sha256` pelo mesmo algoritmo, escrever `sealed_complete`, e a
        # guarda inteira passava. Quem tivesse escrita no `bundle_root`
        # fabricava a evidência que libera edição.
        #
        # `verificacao.complete` percorre o disco. O manifesto ainda participa,
        # mas só para ACRESCENTAR faltas que o layout estático não conhece —
        # `rollback/` numa execução que alterou objeto preexistente. Ele não
        # remove nenhuma.
        #
        # Isto não recusa o documento: um bundle incompleto ainda registra uma
        # execução que aconteceu, e recusar apagaria o registro do que deu
        # errado. O que ele não pode é contar como evidência confirmada.
        if not verificacao.complete:
            unresolved.append(
                "%s: o bundle %s está íntegro mas incompleto (falta: %s; "
                "manifesto declara %s). Íntegro não é completo, e completude "
                "recomputada do layout não é o que o manifesto diz de si"
                % (rotulo, sha[:12],
                   ", ".join(verificacao.effective_missing_required),
                   dados.get("status")))
            return False
        if verificacao.inconsistencies:
            unresolved.append(
                "%s: o bundle %s é completo, com divergência de manifesto "
                "registrada: %s" % (rotulo, sha[:12],
                                    "; ".join(verificacao.inconsistencies)))
        return True

    problems.append(
        "%s: nenhum bundle com sha256 %s foi encontrado em %s. Attestation "
        "que cita evidência inexistente é declaração, não medição"
        % (rotulo, sha[:12], raiz))
    return False
