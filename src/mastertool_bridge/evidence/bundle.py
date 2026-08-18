"""Evidence Bundle — o pacote imutável de uma execução (fase R2).

Estrutura declarada em `docs/ROADMAP.md` §2.7. Roda no host, é puro em
CPython 3, e não abre o MasterTool: recebe artefatos já produzidos e os fecha
num pacote que se pode conferir depois, por qualquer pessoa, sem confiar em
quem o montou.

O QUE "IMUTÁVEL" SIGNIFICA AQUI, EXATAMENTE
===========================================
Significa **verificável**, não *impossível de alterar*. Selar grava um
`manifest.json` com o sha256 de cada arquivo e um hash do próprio conjunto;
alterar qualquer coisa depois disso é possível no sistema de arquivos e passa
a ser DETECTÁVEL por `verify_bundle`. Prometer imutabilidade de verdade exigiria
mídia ou serviço fora do escopo deste projeto — e prometer o que não se entrega
é pior que entregar menos.

Três decisões que o pacote materializa:

* **seção é lista literal, não convenção de nome.** Um arquivo gravado numa
  seção que o layout não declara é recusado no momento da gravação, e não
  descoberto na hora de ler;
* **selar exige completude.** Faltando artefato obrigatório, o pacote fecha
  como `incomplete` e o manifesto NOMEIA o que falta. Um bundle incompleto
  continua sendo evidência — do que não foi produzido;
* **depois de selado, nada entra.** `add` levanta. Acrescentar arquivo a um
  pacote fechado invalidaria silenciosamente o hash que alguém já citou.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"

# Layout LITERAL. Cada seção declara os arquivos que a fase R2 espera; o que
# está marcado como obrigatório é o que faz um pacote ser completo.
#
# `execution/journal.jsonl` é obrigatório e os demais da mesma seção não são:
# um probe pode não produzir stdout, mas uma execução sem journal não é
# auditável de forma nenhuma.
BUNDLE_LAYOUT: dict[str, dict[str, tuple[str, ...]]] = {
    "source": {
        "required": ("project.sha256",),
        "optional": ("inventory.json",),
    },
    "plan": {
        "required": ("specification.json", "normalized_plan.json", "plan.sha256"),
        "optional": (),
    },
    "execution": {
        "required": ("journal.jsonl",),
        "optional": ("stdout.log", "mastertool_messages.json"),
    },
    "verification": {
        "required": ("reopened_inventory.json", "build_report.json"),
        "optional": ("textual_diff.json", "structural_diff.json",
                     "unexpected_changes.json"),
    },
    "output": {
        "required": ("project.sha256",),
        "optional": (),
    },
    "approval": {
        "required": (),
        "optional": ("decision.json",),
    },
    # REVERSIBILIDADE (fase R2). Os dois arquivos são `optional` AQUI porque
    # execução que não altera objeto preexistente não tem o que reverter, e o
    # layout é estático — ele não sabe o que a execução fez.
    #
    # Quem sabe é `evidence/from_run.py`: se o plano tem alteração e estes
    # arquivos faltam, ele os registra como FALTANDO, e o pacote sela
    # incompleto. A condição mora onde a condição é conhecível.
    "rollback": {
        "required": (),
        "optional": ("before-texts.json", "rollback-spec.json"),
    },
}

SECTIONS = tuple(BUNDLE_LAYOUT)

STATUS_SEALED_COMPLETE = "sealed_complete"
STATUS_SEALED_INCOMPLETE = "sealed_incomplete"
STATUS_OPEN = "open"


class BundleError(RuntimeError):
    """Uso incorreto do pacote — seção desconhecida, gravação após o selo."""


def _sha256_of(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(65536), b""):
            digest.update(bloco)
    return digest.hexdigest()


def allowed_names(section: str) -> tuple[str, ...]:
    layout = BUNDLE_LAYOUT.get(section)
    if layout is None:
        return ()
    return tuple(layout["required"]) + tuple(layout["optional"])


def missing_required_in(root: Path | str) -> list[str]:
    """O que falta no pacote, RECOMPUTADO do layout percorrendo o disco.

    Função livre, e não método, porque quem confere uma evidência tem um
    caminho — não tem o objeto que montou o pacote. Enquanto a única
    implementação era o método, conferir completude de um bundle alheio só
    dava para ler `manifest.missing_required`, que é o campo que o achado
    RV2-1 mostrou ser forjável.
    """
    raiz = Path(root)
    faltando: list[str] = []
    for secao, layout in BUNDLE_LAYOUT.items():
        for nome in layout["required"]:
            if not (raiz / secao / nome).is_file():
                faltando.append("%s/%s" % (secao, nome))
    return faltando


@dataclass
class BundleManifest:
    run_id: str
    status: str
    files: dict[str, str] = field(default_factory=dict)
    missing_required: list[str] = field(default_factory=list)
    bundle_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.status == STATUS_SEALED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "status": self.status,
            "complete": self.complete,
            "files": dict(sorted(self.files.items())),
            "missing_required": list(self.missing_required),
            "bundle_sha256": self.bundle_sha256,
            "metadata": dict(self.metadata),
        }


class EvidenceBundle:
    """Montagem incremental de um pacote, terminando em `seal()`."""

    def __init__(self, root: Path | str, run_id: str) -> None:
        self.root = Path(root)
        self.run_id = run_id
        self._sealed = False

    # --- construção ---------------------------------------------------------

    def create(self) -> EvidenceBundle:
        for secao in SECTIONS:
            (self.root / secao).mkdir(parents=True, exist_ok=True)
        return self

    @property
    def sealed(self) -> bool:
        return self._sealed or (self.root / MANIFEST_NAME).is_file()

    def add(self, section: str, name: str, content: Any) -> Path:
        """Grava um artefato. Recusa seção/nome fora do layout e pacote selado.

        `content` em `bytes` vai como está; `str` vai como UTF-8; qualquer
        outra coisa é serializada como JSON. Adivinhar o formato pelo nome do
        arquivo escolheria em silêncio.
        """
        if self.sealed:
            raise BundleError(
                "pacote %r já está selado: acrescentar arquivo invalidaria em "
                "silêncio um hash que alguém já pode ter citado" % self.run_id)
        if section not in BUNDLE_LAYOUT:
            raise BundleError(
                "seção %r não existe no layout; seções: %s"
                % (section, ", ".join(SECTIONS)))
        if name not in allowed_names(section):
            raise BundleError(
                "arquivo %r não é declarado na seção %r; declarados: %s"
                % (name, section, ", ".join(allowed_names(section)) or "(nenhum)"))

        destino = self.root / section / name
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            destino.write_bytes(content)
        elif isinstance(content, str):
            destino.write_text(content, encoding="utf-8", newline="\n")
        else:
            destino.write_text(
                json.dumps(content, ensure_ascii=False, indent=2,
                           sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")
        return destino

    # --- fechamento ---------------------------------------------------------

    def missing_required(self) -> list[str]:
        return missing_required_in(self.root)

    def seal(self, metadata: dict | None = None,
             extra_missing: list[str] | None = None) -> BundleManifest:
        """Fecha o pacote e grava o manifesto.

        Um pacote incompleto SELA assim mesmo, como `sealed_incomplete`, com a
        lista do que falta. Recusar-se a selar deixaria a evidência do
        fracasso solta em disco, sem hash e sem manifesto — e é justamente a
        execução que deu errado que mais precisa ficar registrada.

        `extra_missing` existe porque nem toda obrigatoriedade é estática.
        `BUNDLE_LAYOUT` sabe quais arquivos toda execução deve ter; ele **não**
        sabe que uma execução que ALTEROU objeto preexistente também deve
        trazer o texto anterior, porque isso depende do plano. Quem sabe é
        `evidence/from_run.py`, e sem este parâmetro o que ele descobria ficava
        só na saída do comando: o selo dizia `sealed_complete` com a seção
        `rollback/` vazia.

        Foi assim que os dez primeiros pacotes de reversão selaram completos
        faltando `rollback-spec.json` — e a nota do `ROADMAP` §2.7 prometia o
        contrário. Promessa em prosa que o código não cumpre é o modo de falha
        que este projeto persegue; aqui ele apareceu do lado de dentro.
        """
        if self.sealed:
            raise BundleError("pacote %r já está selado" % self.run_id)

        arquivos: dict[str, str] = {}
        for caminho in sorted(self.root.rglob("*")):
            if not caminho.is_file() or caminho.name == MANIFEST_NAME:
                continue
            rel = caminho.relative_to(self.root).as_posix()
            arquivos[rel] = _sha256_of(caminho)

        # Ordenado e sem repetição: `extra_missing` vem de outro módulo, e um
        # mesmo nome chegando dos dois lados não deve aparecer duas vezes no
        # manifesto.
        faltando = sorted(set(self.missing_required())
                          | set(extra_missing or []))
        manifesto = BundleManifest(
            run_id=self.run_id,
            status=(STATUS_SEALED_COMPLETE if not faltando
                    else STATUS_SEALED_INCOMPLETE),
            files=arquivos,
            missing_required=faltando,
            metadata=dict(metadata or {}),
        )
        # Hash do CONJUNTO: depende de cada nome e de cada conteúdo, e por isso
        # muda se um arquivo for renomeado, removido ou alterado.
        resumo = "\n".join("%s %s" % (nome, arquivos[nome])
                           for nome in sorted(arquivos))
        manifesto.bundle_sha256 = hashlib.sha256(
            resumo.encode("utf-8")).hexdigest()

        (self.root / MANIFEST_NAME).write_text(
            json.dumps(manifesto.to_dict(), ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
        self._sealed = True
        return manifesto


@dataclass
class BundleVerification:
    """Íntegro e completo são DUAS perguntas, e cada uma tem sua fonte.

    `intact` é sobre adulteração: os arquivos declarados ainda têm o conteúdo
    declarado. Ela se responde recomputando hashes.

    `complete` é sobre suficiência: o pacote tem tudo que o layout exige. Ela
    se responde **percorrendo o disco**, e é o achado RV2-1 — enquanto ela foi
    lida de `manifest.status`, quem tinha escrita no diretório removia um
    arquivo obrigatório, recomputava `files` e `bundle_sha256` pelo mesmo
    algoritmo do selo, escrevia `sealed_complete`, e o pacote passava íntegro
    E completo.
    """

    run_id: str | None = None
    problems: list[str] = field(default_factory=list)
    checked_files: int = 0
    status: str | None = None
    # Recomputado do layout, percorrendo o disco. Esta é a fonte.
    recomputed_missing_required: list[str] = field(default_factory=list)
    # Lido do manifesto. Diagnóstico — e mais uma coisa, ver `effective`.
    manifest_missing_required: list[str] = field(default_factory=list)
    inconsistencies: list[str] = field(default_factory=list)

    @property
    def intact(self) -> bool:
        return not self.problems

    @property
    def effective_missing_required(self) -> list[str]:
        """A união, e a direção da confiança é o ponto.

        O manifesto pode ACRESCENTAR faltas, nunca removê-las. Ele acrescenta
        porque sabe coisas que o layout estático não sabe: `rollback/` é
        opcional no layout, e obrigatório quando o plano ALTEROU objeto
        preexistente — condição que só quem montou o pacote conhece, e que
        chega ao selo por `extra_missing`.

        Confiar nele nos dois sentidos reabriria o RV2-1. Descartá-lo
        desfaria a guarda condicional de reversibilidade, que custou dez
        pacotes selados errado para existir. Monotonicidade resolve os dois:
        declarar falta é aceito, declarar completude não é.
        """
        return sorted(set(self.recomputed_missing_required)
                      | set(self.manifest_missing_required))

    @property
    def complete(self) -> bool:
        return not self.effective_missing_required

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "intact": self.intact,
            "complete": self.complete,
            "status": self.status,
            "checked_files": self.checked_files,
            "recomputed_missing_required": list(self.recomputed_missing_required),
            "manifest_missing_required": list(self.manifest_missing_required),
            "effective_missing_required": list(self.effective_missing_required),
            "inconsistencies": list(self.inconsistencies),
            "problems": list(self.problems),
        }


def verify_bundle(root: Path | str) -> BundleVerification:
    """Recomputa hashes E completude, e compara os dois com o manifesto.

    Detecta: arquivo alterado, removido, acrescentado depois do selo,
    manifesto ausente ou ilegível, e — desde RV2-1 — manifesto que declara
    completude que o disco não sustenta.

    Nunca levanta: quem decide o que fazer com um pacote adulterado é o
    chamador.
    """
    raiz = Path(root)
    resultado = BundleVerification()

    # ANTES de qualquer retorno: um pacote sem manifesto legível não pode sair
    # daqui com `complete` verdadeiro só porque a lista ficou vazia por falta
    # de execução. Ausência de conferência não é conferência.
    resultado.recomputed_missing_required = missing_required_in(raiz)

    caminho_manifesto = raiz / MANIFEST_NAME
    if not caminho_manifesto.is_file():
        resultado.problems.append(
            "manifesto ausente: o pacote nunca foi selado, e sem manifesto não "
            "há o que conferir")
        return resultado

    try:
        dados = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        resultado.problems.append("manifesto ilegível: %s" % exc)
        return resultado

    if not isinstance(dados, dict) or not isinstance(dados.get("files"), dict):
        resultado.problems.append("manifesto malformado: sem mapa `files`")
        return resultado

    resultado.run_id = dados.get("run_id")
    resultado.status = dados.get("status")
    declarados: dict[str, str] = dados["files"]

    declarado_faltando = dados.get("missing_required")
    if isinstance(declarado_faltando, list) and all(
            isinstance(x, str) for x in declarado_faltando):
        resultado.manifest_missing_required = list(declarado_faltando)
    elif declarado_faltando is not None:
        resultado.inconsistencies.append(
            "missing_required do manifesto não é lista de strings: %r"
            % (declarado_faltando,))

    # As duas divergências possíveis, e elas NÃO são simétricas.
    so_no_disco = sorted(set(resultado.recomputed_missing_required)
                         - set(resultado.manifest_missing_required))
    if so_no_disco:
        resultado.inconsistencies.append(
            "o manifesto não registra falta que o layout exige: %s. O pacote é "
            "INCOMPLETO — completude vem do disco, e este é o sentido em que o "
            "manifesto não pode ser acreditado" % ", ".join(so_no_disco))
    if resultado.status == STATUS_SEALED_COMPLETE and (
            resultado.effective_missing_required):
        resultado.inconsistencies.append(
            "manifesto declara %s e falta: %s"
            % (STATUS_SEALED_COMPLETE,
               ", ".join(resultado.effective_missing_required)))
    if resultado.status == STATUS_SEALED_INCOMPLETE and (
            not resultado.effective_missing_required):
        resultado.inconsistencies.append(
            "manifesto declara %s e nada falta; o pacote é aceito como completo "
            "com esta divergência registrada" % STATUS_SEALED_INCOMPLETE)

    presentes = {
        caminho.relative_to(raiz).as_posix()
        for caminho in raiz.rglob("*")
        if caminho.is_file() and caminho.name != MANIFEST_NAME
    }

    for rel, sha_declarado in sorted(declarados.items()):
        caminho = raiz / rel
        if not caminho.is_file():
            resultado.problems.append("arquivo do manifesto sumiu: %s" % rel)
            continue
        resultado.checked_files += 1
        if _sha256_of(caminho) != sha_declarado:
            resultado.problems.append("conteúdo alterado depois do selo: %s" % rel)

    for rel in sorted(presentes - set(declarados)):
        resultado.problems.append(
            "arquivo acrescentado depois do selo: %s" % rel)

    resumo = "\n".join("%s %s" % (nome, declarados[nome])
                       for nome in sorted(declarados))
    esperado = hashlib.sha256(resumo.encode("utf-8")).hexdigest()
    if dados.get("bundle_sha256") != esperado:
        resultado.problems.append(
            "hash do conjunto não confere com a lista de arquivos declarada: "
            "o próprio manifesto foi editado")

    return resultado
