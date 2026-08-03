"""O que mudou além do que foi autorizado — o invariante central da fase R2.

Módulo puro, offline. Compara o estado ANTES e DEPOIS de uma execução, contra
a lista do que o plano autorizou mudar, e devolve o que sobrou. O que sobra é
o achado: alteração transacional significa **só os alvos declarados mudaram**,
e sem esta comparação a frase é só uma escrita com nome melhor.

DUAS CAMADAS, PORQUE SÃO DUAS PERGUNTAS
=======================================
* **estrutural** — a árvore ganhou ou perdeu objeto? Um `replace` de texto não
  deve mexer na árvore (medido em W1.3A: nove filhos antes e nove depois), e
  se mexeu, isso é achado mesmo que o texto esteja perfeito;
* **textual** — algum documento que ninguém autorizou tem hash diferente?

Elas falham por motivos diferentes e por isso são relatadas separadas. Fundi-las
num "mudou / não mudou" faria o operador investigar a árvore quando o problema
é texto, e vice-versa.

O QUE ESTE MÓDULO SE RECUSA A CHAMAR DE "SEM MUDANÇA"
=====================================================
Ausência de dado. Se o artefato de antes não existe, ou o de depois não existe,
o resultado é `incomparável` — nunca "nada mudou". A diferença importa: um lote
sem artefato de comparação e um lote comprovadamente idêntico são estados
opostos, e o segundo é o único que autoriza aprovar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# Campos de um nó que identificam o objeto para efeito de comparação. NÃO
# inclui `object_guid`: ele é sorteado a cada criação, e incluí-lo faria toda
# comparação entre gerações independentes acusar mudança em tudo.
NODE_IDENTITY_FIELDS = ("name", "type_guid")

VERDICT_UNCHANGED = "only_authorized_changed"
VERDICT_UNEXPECTED = "unexpected_changes_found"
VERDICT_INCOMPARABLE = "incomparable"

VERDICTS = (VERDICT_UNCHANGED, VERDICT_UNEXPECTED, VERDICT_INCOMPARABLE)


@dataclass
class UnexpectedChangeReport:
    verdict: str = VERDICT_INCOMPARABLE
    added_objects: list[str] = field(default_factory=list)
    removed_objects: list[str] = field(default_factory=list)
    unauthorized_text_changes: list[str] = field(default_factory=list)
    authorized_and_changed: list[str] = field(default_factory=list)
    authorized_but_unchanged: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """DERIVADO. Só é limpo quando a comparação FOI POSSÍVEL e não sobrou
        nada — `incomparable` nunca é limpo."""
        return self.verdict == VERDICT_UNCHANGED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "verdict": self.verdict,
            "clean": self.clean,
            "added_objects": list(self.added_objects),
            "removed_objects": list(self.removed_objects),
            "unauthorized_text_changes": list(self.unauthorized_text_changes),
            "authorized_and_changed": list(self.authorized_and_changed),
            "authorized_but_unchanged": list(self.authorized_but_unchanged),
            "problems": list(self.problems),
        }


def _identidades(nos: Any) -> set[tuple] | None:
    if isinstance(nos, dict):
        nos = nos.get("nodes")
    if not isinstance(nos, list):
        return None
    saida = set()
    for no in nos:
        if not isinstance(no, dict):
            continue
        saida.add(tuple(no.get(campo) for campo in NODE_IDENTITY_FIELDS))
    # Zero nós NÃO é "árvore vazia": é leitura que falhou. Um projeto do
    # MasterTool sempre tem nós, e aceitar o vazio como medição faria TODO o
    # estado seguinte parecer acrescentado — um veredito enganoso no lugar de
    # uma recusa. Mesmo princípio do inventário vazio em
    # `spec/modification_source.py`.
    if not saida:
        return None
    return saida


def _textos(payload: Any) -> dict[str, str] | None:
    """Normaliza o artefato de textos para `familia:nome:campo -> sha256`."""
    if not isinstance(payload, dict):
        return None
    objetos = payload.get("objects")
    if not isinstance(objetos, list):
        return None
    saida: dict[str, str] = {}
    for objeto in objetos:
        if not isinstance(objeto, dict):
            continue
        for texto in objeto.get("texts") or []:
            if not isinstance(texto, dict):
                continue
            chave = "%s:%s:%s" % (objeto.get("family"), objeto.get("name"),
                                  texto.get("field"))
            saida[chave] = texto.get("sha256_observed")
    # Pelo mesmo motivo dos nós: nenhum texto medido é leitura falha, e não
    # "projeto sem texto nenhum".
    if not saida:
        return None
    return saida


def compare(before_nodes: Any, after_nodes: Any,
            before_texts: Any, after_texts: Any,
            authorized: Any = ()) -> UnexpectedChangeReport:
    """Compara antes×depois e isola o que não foi autorizado.

    `authorized` são as chaves `familia:nome:campo` que o plano autorizou
    mudar. Uma chave autorizada que NÃO mudou também é relatada — não reprova,
    mas é informação: o plano pediu uma alteração que não teve efeito, e isso
    costuma ser um texto idêntico ao que já estava lá.
    """
    relatorio = UnexpectedChangeReport()

    antes_nos = _identidades(before_nodes)
    depois_nos = _identidades(after_nodes)
    antes_txt = _textos(before_texts)
    depois_txt = _textos(after_texts)

    faltando = [nome for nome, valor in (("nós antes", antes_nos),
                                         ("nós depois", depois_nos),
                                         ("textos antes", antes_txt),
                                         ("textos depois", depois_txt))
                if valor is None]
    if faltando:
        relatorio.verdict = VERDICT_INCOMPARABLE
        relatorio.problems.append(
            "artefato(s) ausente(s) ou ilegível(is): %s. Sem os quatro, o "
            "resultado é INCOMPARÁVEL — e incomparável nunca é 'nada mudou'"
            % ", ".join(faltando))
        return relatorio

    autorizadas = set(authorized or ())

    # --- camada estrutural ---------------------------------------------------
    for identidade in sorted(depois_nos - antes_nos, key=str):
        relatorio.added_objects.append(":".join(str(p) for p in identidade))
    for identidade in sorted(antes_nos - depois_nos, key=str):
        relatorio.removed_objects.append(":".join(str(p) for p in identidade))

    # --- camada textual ------------------------------------------------------
    for chave in sorted(set(antes_txt) | set(depois_txt)):
        anterior = antes_txt.get(chave)
        posterior = depois_txt.get(chave)
        mudou = anterior != posterior
        if chave in autorizadas:
            if mudou:
                relatorio.authorized_and_changed.append(chave)
            else:
                relatorio.authorized_but_unchanged.append(chave)
            continue
        if mudou:
            relatorio.unauthorized_text_changes.append(chave)

    sobrou = (relatorio.added_objects or relatorio.removed_objects
              or relatorio.unauthorized_text_changes)
    relatorio.verdict = VERDICT_UNEXPECTED if sobrou else VERDICT_UNCHANGED
    return relatorio
