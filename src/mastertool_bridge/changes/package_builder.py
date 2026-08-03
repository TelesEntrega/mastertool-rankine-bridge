"""Montagem do pacote de change set — SUPERADO por `evidence.bundle`.

Este módulo era um stub que levantava `NotImplementedPhaseError` e descrevia um
layout planejado (`workspace/change-sets/<id>/{change-set.json, summary.md,
risk-assessment.md, approval.md, original/, proposed/, diffs/, validation/}`).

O que a fase R2 construiu foi o **Evidence Bundle**
(`mastertool_bridge.evidence.bundle`), com o layout que `docs/ROADMAP.md` §2.7
declara — `source/`, `plan/`, `execution/`, `verification/`, `output/`,
`approval/` — e com o que o layout antigo não previa: manifesto com sha256 por
arquivo, hash do conjunto, e verificação capaz de detectar arquivo alterado,
removido ou acrescentado depois do selo.

O nome antigo continua aqui, e continua LEVANTANDO, por dois motivos. Primeiro,
os dois layouts não são o mesmo pacote: quem chamasse `build_package`
esperando o layout de change set e recebesse um Evidence Bundle receberia
diretórios diferentes dos que pediu, em silêncio. Segundo, ninguém chama esta
função — a busca por `build_package` em `src/`, `tests/`, `tools/` e `scripts/`
não retorna nenhum chamador —, então redirecioná-la seria escrever
compatibilidade para um chamador que não existe.

A exceção agora **aponta para o substituto**, que é o que faltava.
"""

from __future__ import annotations

from mastertool_bridge.exceptions import NotImplementedPhaseError


def build_package(*_args, **_kwargs):
    raise NotImplementedPhaseError(
        "O pacote de evidência da fase R2 é `mastertool_bridge.evidence."
        "bundle.EvidenceBundle`, com o layout de docs/ROADMAP.md §2.7 e "
        "verificação por manifesto. Este nome descrevia um layout de change "
        "set que não foi construído; se ele voltar a ser necessário, entra "
        "como decisão própria e não como apelido do bundle.")
