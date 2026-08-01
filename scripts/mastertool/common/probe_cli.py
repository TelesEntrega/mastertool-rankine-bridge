# -*- coding: utf-8 -*-
"""Argumentos e navegacao pontual compartilhados pelos probes que recebem
`--scriptargs` e precisam alcancar UM no da arvore por caminho de indices.

Existe porque a duplicacao entre os probes de varredura e de exportacao era
identica linha a linha, e porque probe que roda dentro do MasterTool nao e
testavel: a logica pura mora aqui e os testes atacam este modulo.

Nada aqui toca o projeto. `descend` so navega — le filhos e indexa, sem
escrever, sem salvar, sem tocar API de mutacao ou online.

IronPython 2.7: sem f-string, sem pathlib, sem type hints.
"""
from __future__ import print_function

import os

MAX_PATH_STEPS = 12
MAX_CHILDREN_PER_STEP = 1024


class ArgumentProblem(Exception):
    """Argumento recusado. Sempre antes de tocar o projeto."""


def find_arg(argv, name):
    """Aceita `--nome valor`, `--nome=valor` e `--nome:valor`. Nunca levanta;
    devolve None quando ausente e "" quando presente sem valor."""
    prefix = "--" + name
    argv = list(argv or [])
    for i, raw in enumerate(argv):
        if raw == prefix:
            return argv[i + 1] if i + 1 < len(argv) else ""
        for sep in ("=", ":"):
            if raw.startswith(prefix + sep):
                return raw[len(prefix) + 1:]
    return None


def validate_output_path(raw, repo_root, problems):
    """Caminho de saida obrigatorio, sem espaco e FORA do repositorio.

    Sem espaco porque o MT8500 quebra o valor de `--scriptargs` em espaco em
    branco (achado do probe 15) e o destino seria outro. Fora do repositorio
    porque a arvore de um projeto real carrega nomes de equipamento e de
    variavel do cliente, que nunca entram na arvore do repo.
    """
    if raw is None or str(raw).strip() == "":
        problems.append("--output e obrigatorio: sem caminho explicito o probe "
                        "nao adivinha onde gravar")
        return None
    path = str(raw).strip().strip('"')
    if " " in path:
        problems.append("--output contem espaco: %r. O MT8500 quebra valores "
                        "com espaco em --scriptargs, entao o destino seria "
                        "outro." % path)
        return None
    try:
        absolute = os.path.abspath(path)
    except Exception as exc:                                   # noqa: BLE001
        problems.append("--output nao pode ser resolvido: %r (%r)" % (path, exc))
        return None
    if repo_root:
        normalized = os.path.normcase(absolute)
        normalized_root = os.path.normcase(os.path.abspath(repo_root))
        if normalized == normalized_root or \
                normalized.startswith(normalized_root + os.sep):
            problems.append("--output aponta para dentro do repositorio (%s)"
                            % absolute)
            return None
    return absolute


def positive_int(raw, default, label, problems):
    """Inteiro > 0. Limite infinito nao e oferecido: uma arvore ciclica ou um
    bug de navegacao viraria varredura infinita."""
    if raw is None or raw == "":
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        problems.append("%s invalido: %r (esperado inteiro positivo)" % (label, raw))
        return None
    if value <= 0:
        problems.append("%s deve ser > 0, recebido %d" % (label, value))
        return None
    return value


def parse_bool(raw, default, label, problems):
    if raw is None or raw == "":
        return default
    text = str(raw).strip().lower()
    if text in ("1", "true", "yes", "sim"):
        return True
    if text in ("0", "false", "no", "nao"):
        return False
    problems.append("%s invalido: %r (use 0 ou 1)" % (label, raw))
    return None


def parse_node_id(raw, problems, label="--node-id"):
    """`root/1/1/0/2` -> [1, 1, 0, 2].

    Indices, nunca nomes: nome depende de encoding e do idioma do projeto, e
    o mesmo nome pode repetir em ramos diferentes.
    """
    text = str(raw or "").strip()
    if text == "":
        problems.append("%s e obrigatorio" % label)
        return None
    parts = [p for p in text.split("/") if p != ""]
    if not parts or parts[0] != "root":
        problems.append("%s deve comecar por 'root': %r" % (label, text))
        return None
    indexes = []
    for part in parts[1:]:
        try:
            value = int(part)
        except (TypeError, ValueError):
            problems.append("%s tem segmento nao numerico: %r" % (label, part))
            return None
        if value < 0:
            problems.append("%s tem indice negativo: %r" % (label, part))
            return None
        indexes.append(value)
    if not indexes:
        problems.append("%s aponta para a raiz; escolha um no filho" % label)
        return None
    if len(indexes) > MAX_PATH_STEPS:
        problems.append("%s tem %d passos (maximo %d)"
                        % (label, len(indexes), MAX_PATH_STEPS))
        return None
    return indexes


def parse_node_id_list(raw, problems, max_items, label="--node-ids"):
    """Lista fechada, separada por virgula. Sem default: uma lista embutida
    seria a estrutura de UM projeto especifico dentro do repositorio."""
    text = str(raw or "").strip()
    if text == "":
        problems.append("%s e obrigatorio: a lista de nos vem da varredura do "
                        "projeto, nunca embutida no repositorio" % label)
        return None
    items = [p.strip() for p in text.split(",") if p.strip()]
    if not items:
        problems.append("%s vazio" % label)
        return None
    if len(items) > max_items:
        problems.append("%s tem %d itens (maximo %d)"
                        % (label, len(items), max_items))
        return None
    parsed = []
    for item in items:
        indexes = parse_node_id(item, problems, label=label)
        if indexes is None:
            return None
        parsed.append((item, indexes))
    return parsed


def runtime_identity():
    """Versao/build do MT8500 e runtime de script, para o manifesto.

    Defensivo por completo: nada aqui pode derrubar um probe. Fora do
    MasterTool (CPython, testes) devolve os campos nulos com o erro
    registrado, nunca levanta.
    """
    info = {"executable": None, "file_version": None, "product_version": None,
            "script_runtime": None, "error": None}
    try:
        import sys as _sys
        info["script_runtime"] = _sys.version.replace("\n", " ").replace("\r", " ")
    except Exception:                                          # noqa: BLE001
        pass
    try:
        import clr                                             # noqa: F401
        from System.Reflection import Assembly
        from System.Diagnostics import FileVersionInfo
        asm = Assembly.GetEntryAssembly()
        if asm is None:
            info["error"] = "GetEntryAssembly() devolveu None"
            return info
        info["executable"] = asm.Location
        version_info = FileVersionInfo.GetVersionInfo(asm.Location)
        info["file_version"] = version_info.FileVersion
        info["product_version"] = version_info.ProductVersion
    except Exception as exc:                                   # noqa: BLE001
        info["error"] = repr(exc)
    return info


def assembly_name_matches(name, prefixes):
    """True quando `name` comeca por um dos `prefixes`. Nunca levanta.

    Prefixo, e nao substring: `ScriptEngine` deve casar `ScriptEngine3`, mas
    um assembly de terceiro chamado `MeuScriptEngineFalso` nao e nosso.
    """
    if not name:
        return False
    try:
        text = str(name)
    except Exception:                                          # noqa: BLE001
        return False
    for prefix in prefixes or ():
        try:
            if text.startswith(prefix):
                return True
        except Exception:                                      # noqa: BLE001
            continue
    return False


def scriptengine_version_from_assemblies(entries):
    """Versao do ScriptEngine a partir dos assemblies CARREGADOS.

    Preferida ao parse do banner de `sys.version`: o banner mudou de formato
    entre 3.63 e 3.70, e supor que o do MasterTool X siga o mesmo padrao seria
    exatamente o tipo de inferencia que este projeto nao faz. Assembly
    carregado e fato; banner e texto.

    `ScriptEngine3` tem precedencia por ser onde vivem as interfaces reais
    (docs/24). Sem ele, aceita qualquer `ScriptEngine*` e DIZ qual usou.
    """
    entries = list(entries or [])
    for entry in entries:
        try:
            if entry.get("name") == "ScriptEngine3":
                return {"version": entry.get("version"),
                        "source": "assembly ScriptEngine3 carregado"}
        except Exception:                                      # noqa: BLE001
            continue
    for entry in entries:
        try:
            name = entry.get("name") or ""
            if name.startswith("ScriptEngine"):
                return {"version": entry.get("version"),
                        "source": "assembly %s carregado" % name}
        except Exception:                                      # noqa: BLE001
            continue
    return {"version": None,
            "source": "nenhum assembly ScriptEngine* carregado encontrado"}


def descend(project, indexes, trace):
    """Desce por UM caminho, por indice. NAO e varredura: em cada passo le a
    colecao de filhos uma vez e acessa UM indice, com limite de faixa.

    Devolve o no alcancado, ou None registrando o motivo em `trace`.
    """
    current = project
    for step, index in enumerate(indexes):
        children = current.get_children(False)
        if children is None:
            trace.append({"step": step, "error": "get_children devolveu None"})
            return None
        count = children.Count
        if count < 0 or count > MAX_CHILDREN_PER_STEP:
            trace.append({"step": step,
                          "error": "Count fora de faixa: %r" % (count,)})
            return None
        if index >= count:
            trace.append({"step": step,
                          "error": "indice %d fora da faixa (Count=%d)"
                                   % (index, count)})
            return None
        current = children[index]
        trace.append({"step": step, "index": index, "sibling_count": count,
                      "name": current.get_name(False)})
    return current
