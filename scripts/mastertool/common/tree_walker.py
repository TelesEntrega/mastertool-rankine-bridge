# -*- coding: utf-8 -*-
"""tree_walker.py — SUSPENSO. Ver docs/api/mastertool-api-observations.md.

Motivo (2026-07-23): a versao anterior deste modulo presumia os nomes
get_children/children (e a documentacao cogitava find/get_objects/
get_all_objects) como API de navegacao da arvore do projeto, SEM nenhuma
evidencia real. O smoke test confirmou que `dir()` neste ambiente pode
retornar vazio mesmo para objetos com membros que respondem normalmente
(`projects.primary`, tipo `ExtendedObject[IScriptProject]`) — ou seja, tanto
"presumir nomes" quanto "confiar em dir() para descobrir a API" sao
inseguros aqui.

Ate que a API real de navegacao seja confirmada (via reflection estatica
adicional, via o dumper oficial `ScriptEngine.DumpScriptingApi` ou via
evidencia de runtime explicita), este modulo NAO tenta nenhum nome de
navegacao. Toda chamada as funcoes abaixo levanta TreeNavigationSuspended.

Quando a API real for conhecida, a navegacao devera ser implementada atras
de um adaptador dedicado (ex.: ProjectTreeAdapter, ainda nao criado — ver
docs/10-roadmap.md), nao diretamente neste modulo nem espalhada pelo
restante do projeto.
"""
from __future__ import print_function

SUSPENDED_REASON = (
    "Navegacao da arvore do projeto suspensa: os nomes anteriormente "
    "presumidos (get_children/children/find/get_objects/get_all_objects) "
    "nunca foram confirmados, e o smoke test de 2026-07-23 mostrou que "
    "dir() nao e confiavel neste ambiente (projects.primary e um proxy "
    "dinamico com dir() vazio, apesar de getattr direto funcionar). "
    "Aguardando confirmacao via reflection estatica adicional, via o dumper "
    "oficial (ScriptEngine.DumpScriptingApi) ou via evidencia de runtime "
    "explicita antes de reativar este modulo atraves de um adaptador "
    "dedicado (ProjectTreeAdapter).")


class TreeNavigationSuspended(Exception):
    """Levantada por qualquer tentativa de usar a navegacao de arvore ainda
    nao confirmada. Ver SUSPENDED_REASON."""
    pass


def get_children(obj):
    raise TreeNavigationSuspended(SUSPENDED_REASON)


def describe_node(obj, parent_path, depth):
    raise TreeNavigationSuspended(SUSPENDED_REASON)


def walk(root, max_depth=50):
    raise TreeNavigationSuspended(SUSPENDED_REASON)
