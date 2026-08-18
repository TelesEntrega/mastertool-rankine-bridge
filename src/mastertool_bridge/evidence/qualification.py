"""O relatório de qualificação — a prova de que N execuções são N execuções.

POR QUE ELE EXISTE (achado RV2-2)
=================================
A attestation dizia `independent_runs: 10` e mais nada. O número era um
inteiro digitado num documento: nenhum id, nenhuma referência a pacote,
nenhuma comparação. Todas as 13 capacidades da árvore interna estavam
promovidas a `repeatable` por esse inteiro, e a ausência de prova não caía
nem em `problems` nem em `unresolved` — passava calada.

Independência é justamente o que N=10 deveria provar. Declará-la é o mesmo
erro que declarar maturidade, uma camada abaixo.

O QUE ESTE MÓDULO **NÃO** FAZ
=============================
Não compara nada. O comparador N-ário já existe e está certo:
`automation/generation_equivalence.compare_many` usa referência para
equivalência (igualdade é transitiva, comparar todos contra uma basta) e
**todos os pares** para independência (anti-reflexiva e não transitiva — com
n=10 são 45 pares). Reimplementar isso aqui criaria uma segunda opinião sobre
a mesma norma.

Este módulo SELA o veredito daquele comparador num artefato endereçado por
conteúdo, e o CONFERE na hora de promover. A separação importa: quem compara
roda em campo, uma vez; quem confere roda a cada carregamento de attestation,
sem o produto por perto e sem confiar em quem gerou o arquivo.

COMO O RELATÓRIO É LOCALIZADO
=============================
Por hash do conteúdo, sob `<bundle_root>/qualification/`. Nunca por caminho:
caminho é onde o arquivo está hoje, e trocar o conteúdo mantendo o nome é a
forma mais barata de forjar evidência. O nome do arquivo é irrelevante — se o
sha256 bate, é aquele; se não bate, não existe.

Mesma disciplina dos bundles, e pelo mesmo motivo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# Subdiretório de `bundle_root`. Os relatórios não moram dentro de nenhum
# bundle: eles falam SOBRE um conjunto de bundles, e guardá-los dentro de um
# deles elegeria arbitrariamente um dos dez como dono da conclusão.
QUALIFICATION_DIRNAME = "qualification"


class QualificationError(RuntimeError):
    """Uso incorreto — relatório malformado na construção."""


# --- construção (roda em campo, uma vez) ------------------------------------

def build_report(capability: str, run_ids: list[str], repeatability: Any,
                 *, metadata: dict | None = None) -> dict[str, Any]:
    """Monta o relatório canônico a partir do veredito de `compare_many`.

    `equivalent` e `pairwise_independent` são DERIVADOS do resultado da
    comparação, nunca recebidos por parâmetro. Aceitá-los prontos deixaria o
    chamador escrever `True` — que é exatamente o defeito uma camada acima.
    """
    ids = list(run_ids)
    if len(set(ids)) != len(ids):
        raise QualificationError(
            "run_ids repetidos: %s. Dois ids iguais são uma execução contada "
            "duas vezes" % ", ".join(sorted(ids)))
    if not ids:
        raise QualificationError("run_ids vazio")

    comparacao = repeatability.to_dict()
    # `generations` são caminhos locais da máquina de campo. Eles não são
    # evidência — os `run_ids` são —, e caminho de disco de cliente não entra
    # em artefato que pode ser citado fora daqui.
    comparacao.pop("generations", None)

    return {
        "schema_version": SCHEMA_VERSION,
        "capability": capability,
        "run_ids": ids,
        "equivalent": bool(repeatability.all_equivalent),
        "pairwise_independent": not repeatability.independence_violations,
        "minimum_required": int(repeatability.minimum_required),
        "repeatable": bool(repeatability.repeatable),
        "independence_violations": list(repeatability.independence_violations),
        "problems": list(repeatability.problems),
        "comparison": comparacao,
        "metadata": dict(metadata or {}),
    }


def report_bytes(report: dict) -> bytes:
    """Serialização canônica — a mesma disciplina do fingerprint do contrato.

    Se a ordem das chaves mudasse o hash, ele identificaria a digitação em vez
    do conteúdo.
    """
    return (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def report_sha256(report: dict) -> str:
    return hashlib.sha256(report_bytes(report)).hexdigest()


def write_report(bundle_root: Path | str, report: dict) -> tuple[Path, str]:
    """Grava sob `qualification/` e devolve `(caminho, sha256)`.

    O nome do arquivo é o próprio hash: um relatório reescrito com outro
    conteúdo é outro arquivo, e nunca sobrescreve o anterior em silêncio.
    """
    destino = Path(bundle_root) / QUALIFICATION_DIRNAME
    destino.mkdir(parents=True, exist_ok=True)
    dados = report_bytes(report)
    sha = hashlib.sha256(dados).hexdigest()
    caminho = destino / ("%s.json" % sha)
    caminho.write_bytes(dados)
    return caminho, sha


# --- conferência (roda a cada carregamento) ---------------------------------

@dataclass
class QualificationCheck:
    """Resultado da conferência. `confirmed` é derivado de tudo, nunca dito."""

    capability: str
    problems: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    report_sha256: str | None = None
    run_ids: list[str] = field(default_factory=list)
    confirmed_runs: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return not self.problems and not self.unresolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "confirmed": self.confirmed,
            "report_sha256": self.report_sha256,
            "run_ids": list(self.run_ids),
            "confirmed_runs": list(self.confirmed_runs),
            "problems": list(self.problems),
            "unresolved": list(self.unresolved),
        }


def find_report(bundle_root: Path | str, sha: str) -> dict[str, Any] | None:
    """O relatório cujo conteúdo hasheia para `sha`, ou `None`.

    Percorre o diretório e hasheia cada candidato. Não confia no nome do
    arquivo nem em índice nenhum: um índice seria mais um lugar onde mentir.
    """
    pasta = Path(bundle_root) / QUALIFICATION_DIRNAME
    if not pasta.is_dir():
        return None
    for caminho in sorted(pasta.glob("*.json")):
        try:
            dados = caminho.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(dados).hexdigest() != sha:
            continue
        try:
            return json.loads(dados.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
    return None


def _bundles_por_run_id(bundle_root: Path | str) -> dict[str, Path]:
    from mastertool_bridge.evidence.bundle import MANIFEST_NAME

    raiz = Path(bundle_root)
    mapa: dict[str, Path] = {}
    if not raiz.is_dir():
        return mapa
    for pasta in sorted(raiz.iterdir()):
        if not pasta.is_dir():
            continue
        manifesto = pasta / MANIFEST_NAME
        if not manifesto.is_file():
            continue
        try:
            dados = json.loads(manifesto.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        run_id = dados.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in mapa:
            mapa[run_id] = pasta
    return mapa


def verify_qualification(capability: str, evidence: dict,
                         bundle_root: Path | str | None,
                         minimum_runs: int) -> QualificationCheck:
    """Confere que as N execuções existem, são distintas e foram comparadas.

    A ordem das conferências é a ordem em que uma fraude ficaria mais barata:
    primeiro o relatório existe, depois ele fala da mesma capacidade e dos
    mesmos ids, depois o veredito dele é positivo, e só então cada execução é
    localizada e aberta. Parar no primeiro problema esconderia os demais, e
    por isso todas rodam.
    """
    check = QualificationCheck(capability=capability)
    rotulo = "capabilities[%r].qualification_evidence" % capability

    ids = evidence.get("run_ids")
    if not isinstance(ids, list) or not all(isinstance(r, str) and r
                                            for r in ids):
        check.problems.append("%s: run_ids: esperado lista de strings não "
                              "vazias" % rotulo)
        return check
    if len(set(ids)) != len(ids):
        check.problems.append(
            "%s: run_ids tem repetição. Dois ids iguais são UMA execução "
            "contada duas vezes, e independência é exatamente o que a "
            "contagem deveria provar" % rotulo)
        return check
    check.run_ids = list(ids)

    if len(ids) < minimum_runs:
        check.problems.append(
            "%s: %d execução(ões) listada(s) e o grau exige %d"
            % (rotulo, len(ids), minimum_runs))

    sha = evidence.get("comparison_report_sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        check.problems.append(
            "%s: comparison_report_sha256 ausente ou malformado. Dez ids "
            "distintos provam que os ids são distintos, não que as execuções "
            "são independentes" % rotulo)
        return check
    check.report_sha256 = sha

    if bundle_root is None:
        check.unresolved.append(
            "%s: relatório de comparação não conferido (nenhum `bundle_root`)"
            % rotulo)
        return check

    relatorio = find_report(bundle_root, sha)
    if relatorio is None:
        check.problems.append(
            "%s: nenhum relatório de comparação com sha256 %s em %s/. "
            "Relatório citado e inexistente é declaração, não medição"
            % (rotulo, sha[:12], QUALIFICATION_DIRNAME))
        return check

    if relatorio.get("schema_version") != SCHEMA_VERSION:
        check.problems.append(
            "%s: relatório com schema_version %r; esperado %d"
            % (rotulo, relatorio.get("schema_version"), SCHEMA_VERSION))
    if relatorio.get("capability") != capability:
        check.problems.append(
            "%s: o relatório fala da capacidade %r. Relatório de outra "
            "capacidade não respalda esta"
            % (rotulo, relatorio.get("capability")))

    ids_relatorio = relatorio.get("run_ids")
    if not isinstance(ids_relatorio, list):
        check.problems.append("%s: relatório sem run_ids" % rotulo)
    elif set(ids_relatorio) != set(ids):
        so_doc = sorted(set(ids) - set(ids_relatorio))
        so_rel = sorted(set(ids_relatorio) - set(ids))
        check.problems.append(
            "%s: os ids do documento e os do relatório divergem (só no "
            "documento: %s; só no relatório: %s). A comparação precisa ser "
            "sobre as execuções que o documento cita"
            % (rotulo, ", ".join(so_doc) or "-", ", ".join(so_rel) or "-"))

    # Os dois vereditos, conferidos CONTRA o relatório — e não lidos do
    # documento. Aceitar o que o documento diz sobre a comparação seria repor
    # o defeito num campo novo.
    for campo in ("equivalent", "pairwise_independent"):
        no_relatorio = relatorio.get(campo)
        if no_relatorio is not True:
            check.problems.append(
                "%s: o relatório registra %s=%r. O grau depende da medição, e "
                "a medição diz que não" % (rotulo, campo, no_relatorio))
        declarado = evidence.get(campo)
        if declarado is not None and declarado != no_relatorio:
            check.problems.append(
                "%s: o documento declara %s=%r e o relatório registra %r. "
                "Documento que contradiz a própria evidência não é conferível"
                % (rotulo, campo, declarado, no_relatorio))

    # Cada execução, aberta. Existir no relatório não prova que o pacote da
    # execução está em disco, íntegro e completo.
    from mastertool_bridge.evidence.bundle import verify_bundle

    mapa = _bundles_por_run_id(bundle_root)
    for run_id in ids:
        pacote = mapa.get(run_id)
        if pacote is None:
            check.problems.append(
                "%s: a execução %r não tem pacote em %s. Id citado sem pacote "
                "é linha de texto" % (rotulo, run_id, Path(bundle_root)))
            continue
        verificacao = verify_bundle(pacote)
        if not verificacao.intact:
            check.problems.append(
                "%s: o pacote da execução %r NÃO está íntegro: %s"
                % (rotulo, run_id, "; ".join(verificacao.problems)))
            continue
        if not verificacao.complete:
            check.unresolved.append(
                "%s: o pacote da execução %r está íntegro mas incompleto "
                "(falta: %s). Uma das N não sustenta o conjunto"
                % (rotulo, run_id,
                   ", ".join(verificacao.effective_missing_required)))
            continue
        check.confirmed_runs.append(run_id)

    return check
