# -*- coding: utf-8 -*-
"""Acesso defensivo ao projeto aberto no MasterTool.

Convencoes do CODESYS ScriptEngine (a CONFIRMAR na Fase 0):
  - global 'projects' com propriedade 'primary' (projeto aberto);
  - projeto com propriedade 'path'.
Todo acesso e guardado; ausencia vira None + registro de erro, nunca excecao.
"""
from __future__ import print_function

from common import compatibility


def get_projects_object(script_globals=None):
    if script_globals is not None and "projects" in script_globals:
        return script_globals["projects"]
    return compatibility.get_scriptengine_global("projects")


def get_primary_project(script_globals=None):
    """Retorna (projeto, erro). erro=None em caso de sucesso."""
    projects = get_projects_object(script_globals)
    if projects is None:
        return None, "Objeto global 'projects' nao encontrado no ScriptEngine."
    try:
        if hasattr(projects, "primary"):
            primary = projects.primary
            if primary is None:
                return None, "'projects.primary' existe mas e None (nenhum projeto aberto?)."
            return primary, None
        return None, ("Objeto 'projects' existe mas nao possui atributo "
                      "'primary'. Membros: %s" % ", ".join(safe_dir(projects)[:40]))
    except Exception as exc:
        return None, "Falha ao acessar 'projects.primary': %s" % exc


def open_project_readonly(path, script_globals=None):
    """SEGUNDA PORTA de aquisicao (contrato docs/84). Devolve (projeto, erro).

    `get_primary_project` acima OBSERVA um estado global assincrono: ela
    pergunta "qual e o projeto primario agora?" e depende de o host ja ter
    terminado de abrir. Em 30 execucoes medidas (docs/81), 27% morreram com
    `projects.primary is None` antes de varrer qualquer coisa.

    Esta aqui AFIRMA: "abra exatamente esta copia e me entregue exatamente esse
    objeto". A autoridade passa a ser o valor RETORNADO, e `projects.primary`
    nao e consultado -- nem depois, porque `primary=False` garante que a
    abertura nao o altera.

    A funcao anterior NAO e substituida: ela e o braco de controle do
    experimento LEGACY x DIRECT, e sua variancia ja esta medida. Trocar a
    aquisicao no lugar destruiria o unico baseline que temos.

    O PERFIL E FIXO E NAO E PARAMETRIZAVEL. Nao ha argumento para `primary`,
    `update_flags` nem `allow_readonly`: oferecer o parametro criaria a
    possibilidade de passar o valor errado, e a unica combinacao qualificada
    pelo contrato e uma so. Quem precisar de outra combinacao precisa de outro
    contrato, nao de outro argumento.
    """
    from common import safety

    projects = get_projects_object(script_globals)
    if projects is None:
        return None, "Objeto global 'projects' nao encontrado no ScriptEngine."
    if not hasattr(projects, "open"):
        return None, ("Objeto 'projects' existe mas nao possui 'open'. "
                      "Catalogado por reflexao em docs/api secao "
                      "IScriptProjects; ausencia em runtime e achado.")

    # O enum e OBRIGATORIO: a run-137 mediu que o inteiro e recusado com
    # `expected VersionUpdateFlags, got int` -- o IronPython nao converte int
    # para enum .NET neste parametro.
    #
    # `clr.AddReference` NAO E OPCIONAL, e a razao e um erro meu de medicao. A
    # run-138 testou quatro rotas de importacao e as quatro passaram, entao usei
    # a mais curta, sem `AddReference`. A run-139 falhou com
    # `No module named _3S.CoDeSys.VersionCompatibilityManager`.
    #
    # A sonda rodara em modo LEGACY, com `--project=`: o host ja tinha ABERTO um
    # projeto, e por isso o assembly ja estava carregado. No braco DIRECT nao ha
    # `--project=` -- o host nao abre nada, e o assembly so existe se alguem o
    # referenciar. Medir a rota num contexto que nao e o de uso deu quatro luzes
    # verdes, tres delas dependentes de contexto.
    try:
        import clr
        clr.AddReference("VersionCompatibilityManager")
        from _3S.CoDeSys.VersionCompatibilityManager import VersionUpdateFlags
    except Exception as exc:                                       # noqa: BLE001
        return None, ("VersionUpdateFlags indisponivel (%s). Sem o enum nao ha "
                      "forma segura de chamar `open`: o inteiro e recusado pelo "
                      "runtime, e omitir o argumento delegaria a decisao ao "
                      "default do produto." % exc)

    try:
        safety.assert_project_open_allowed(
            primary=False,
            update_flags=VersionUpdateFlags.NoUpdates,
            allow_readonly=True)
    except Exception as exc:                                       # noqa: BLE001
        return None, "Perfil de abertura recusado pelo gate: %s" % exc

    try:
        # Os TRES nomeados, com valor demonstravel estaticamente, sempre --
        # inclusive `update_flags`, que coincide com o default do produto.
        # Default e propriedade do produto e pode mudar entre versoes; contrato
        # nao depende do que ninguem declarou.
        #
        # `VersionUpdateFlags.NoUpdates` INLINE, e nunca por variavel: a forma
        # pontuada e verificavel pela guarda estatica (docs/84 secao 5) e diz o
        # proprio nome, o que a torna mais auditavel que o literal `1` que a
        # primeira versao usava.
        projeto = projects.open(path,
                                primary=False,
                                update_flags=VersionUpdateFlags.NoUpdates,
                                allow_readonly=True)
    except Exception as exc:                                       # noqa: BLE001
        # SEM FALLBACK. Recusa a abrir somente-leitura e resultado NOMEADO;
        # tentar de novo sem a bandeira transformaria a garantia em preferencia.
        return None, ("project_open_readonly_refused: %s" % exc)

    if projeto is None:
        return None, "'projects.open' devolveu None para %r." % (path,)
    return projeto, None


def get_project_path(project):
    for attr in ("path", "project_path", "full_name"):
        try:
            if hasattr(project, attr):
                value = getattr(project, attr)
                if value:
                    return str(value)
        except Exception:
            continue
    return None


def get_object_name(obj):
    """Nome de um objeto da arvore, tentando as convencoes conhecidas."""
    try:
        if hasattr(obj, "get_name"):
            name = obj.get_name()
            if name:
                return str(name)
    except Exception:
        pass
    for attr in ("name", "path"):
        try:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value:
                    return str(value)
        except Exception:
            continue
    return None


def safe_dir(obj):
    try:
        return sorted([m for m in dir(obj) if not m.startswith("_")])
    except Exception:
        return []
