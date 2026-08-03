"""Testes de `tools/check_repo_hygiene.py`.

Cada regra é testada nos dois sentidos — uma entrada que passa e uma que
falha — porque uma guarda que nunca falha não é guarda (ver
`docs/18-estado-e-proximo-passo.md`: "teste verde não é evidência até falhar
quando deve").

O teste `test_checker_e_limpo_sobre_o_repositorio_real` roda o verificador
sobre este próprio repositório. Se ele encontrar um achado real, o teste
**deve falhar** — não é permitido enfraquecer a regra nem o allow-list só
para fazer este teste passar (ver contrato do slice). Uma falha aqui é
achado a ser reportado, nunca suprimido.
"""

import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import check_repo_hygiene as hygiene  # noqa: E402


# --- fixtures montadas em partes, de propósito -------------------------------
#
# O verificador varre os arquivos **rastreados** (`git ls-files`), e este
# arquivo é um deles. Uma fixture escrita como literal completo — uma chave AWS
# de brinquedo, o caminho absoluto desta máquina — é indistinguível, para o
# checker, de uma ocorrência real: ele acha, e acha com razão. Foi exatamente o
# que aconteceu no commit `3d2d7a6`, que passou verde antes de rastrear este
# arquivo e reprovou depois de rastreá-lo.
#
# Três saídas existiam. Ampliar a allow-list e registrar a fixture como dívida
# na catraca são as duas ruins: a catraca exige que a dívida ENCOLHA, e uma
# fixture permanente nunca encolhe; pior, a chave da catraca é
# `(regra, arquivo, padrão)` **sem linha**, então a entrada mascararia um
# caminho absoluto de verdade que alguém acrescentasse a este mesmo arquivo
# depois. Silenciar a guarda para caber a fixture inverteria o propósito dela.
#
# Esta é a terceira: montar o valor em partes. Nenhuma linha rastreada contém o
# padrão inteiro, o repositório fica genuinamente sem o literal, a regra
# mantém 100% do poder de detecção e nenhuma superfície de supressão nova é
# criada. As funções sob teste recebem a string completa, montada em tempo de
# execução — o que elas veem é idêntico ao caso real.
#
# Se um formatador juntar estas partes de volta, o teste que varre o
# repositório real volta a reprovar, apontando para cá. A regressão tem guarda.
_USUARIO_LOCAL = "Rankine"
_HOME_LOCAL = "C:\\Users\\" + _USUARIO_LOCAL + "\\Documents"
_RUNS_DIR_LOCAL = "C:\\" + "mastertool-rankine-bridge-runs"
_AWS_KEY_FIXTURE = "AKIA" + "ABCDEFGHIJKLMNOP"
# Conteúdo do arquivo plantado nos repositórios sintéticos. Montado em partes
# pelo mesmo motivo dos demais — e por um motivo a mais, descoberto depois:
# enquanto a regra só casava UMA barra invertida, estas duas linhas ficaram
# invisíveis mesmo escrevendo o caminho por extenso. A regra corrigida as vê, e
# elas passam a ser montadas como todas as outras.
_ARQUIVO_SUJO = 'CAMINHO = r"' + _HOME_LOCAL + '\\qualquer"\n'
_PEM_HEADER_FIXTURE = "-----BEGIN RSA PRIVATE" + " KEY-----"
_SEGREDO_ATRIBUIDO_FIXTURE = 'api_key = "sk-' + '1234567890abcdef1234567890"'


# --- (a) dado de cliente -----------------------------------------------------

def test_texto_sem_identificador_de_cliente_nao_gera_achado():
    texto = "GVL_AI_TESTE : BOOL;\nPROGRAM PRG_AI_TESTE\nEND_PROGRAM\n"
    assert hygiene.find_client_data_findings("src/exemplo.py", texto) == []


@pytest.mark.skipif(
    not hygiene.CLIENT_IDENTIFIER_PATTERNS,
    reason=("os padrões de cliente vivem em `tools/client_identifiers.py`, que NÃO é publicado. Na cópia publicada a lista é vazia e não há o que detectar — quem barra identificador de cliente é o sanitizador, antes."))
def test_texto_com_tc_quimica_gera_achado():
    """`ExemploPlanta` é nome real de projeto de cliente — README.md o cita
    como validado em runtime real (ver achado reportado no fechamento do
    slice)."""
    texto = "confirmado contra `ExemploPlanta V1.0.project`\n"
    achados = hygiene.find_client_data_findings("docs/qualquer.md", texto)
    assert len(achados) == 1
    assert achados[0].rule == "client_data"
    assert "cliente_tc_quimica" in achados[0].message


def test_tmf_v1_nao_e_dado_de_cliente():
    """Ancora de uma decisão que já foi tomada errado uma vez.

    A primeira versão desta guarda classificou `TemplateExemplo v1.project` como dado de
    cliente, apoiada em `docs/37`, que o chama de "projeto-base real do
    cliente". Quem classificou o arquivo quando ele foi adotado foi o
    CHANGELOG, e ele diz **"projeto sintético com controlador NX3008 e cartões
    de I/O configurados"**. "Real" ali se opõe a "fixture", não a "sintético".

    Bloquear o nome do próprio template de teste tornaria impossível
    documentar a baseline -- e a baseline é justamente o que precisa estar
    documentado. Se algum dia o template virar arquivo de cliente de verdade,
    este teste é o lugar de reverter a decisão, com o motivo escrito.
    """
    texto = "sobre o `TemplateExemplo v1.project`, com cartoes de I/O\n"
    assert hygiene.find_client_data_findings("docs/qualquer.md", texto) == []


def test_arquivo_no_allowlist_de_cliente_nao_gera_achado(monkeypatch):
    """O allow-list existe para menção de POLÍTICA (não de uso real). Vazio
    por padrão -- este teste prova que, se um caminho for adicionado, ele é
    de fato ignorado."""
    monkeypatch.setattr(
        hygiene, "CLIENT_IDENTIFIER_ALLOWLIST",
        frozenset({"docs/politica-de-dados.md"}))
    texto = "nunca versionar `ExemploPlanta V1.0.project`\n"
    achados = hygiene.find_client_data_findings("docs/politica-de-dados.md", texto)
    assert achados == []


# --- (b) tamanho e extensão --------------------------------------------------

def test_arquivo_pequeno_com_extensao_permitida_nao_gera_achado():
    achados = hygiene.find_size_extension_findings("src/modulo.py", 2048)
    assert achados == []


def test_arquivo_acima_do_limite_gera_achado():
    achados = hygiene.find_size_extension_findings(
        "tests/fixtures/grande.txt", hygiene.DEFAULT_MAX_FILE_BYTES + 1)
    assert len(achados) == 1
    assert achados[0].rule == "oversized_file"


def test_extensao_proibida_gera_achado():
    achados = hygiene.find_size_extension_findings("output/export.project", 500)
    assert len(achados) == 1
    assert achados[0].rule == "disallowed_extension"
    assert ".project" in achados[0].message


def test_fixture_sintetica_na_allowlist_de_extensao_nao_gera_achado():
    """`tests/fixtures/plcopen/ladder_sample.xml` é a única exceção conhecida
    e documentada -- fixture sintética, sanitizada e coberta por teste
    próprio."""
    achados = hygiene.find_size_extension_findings(
        "tests/fixtures/plcopen/ladder_sample.xml", 500)
    assert achados == []


def test_extensao_proibida_fora_da_allowlist_continua_reprovando():
    """Mesma extensão do teste anterior, caminho diferente: a allowlist é
    por caminho exato, não por extensão inteira."""
    achados = hygiene.find_size_extension_findings(
        "tests/fixtures/outro_export.xml", 500)
    assert len(achados) == 1
    assert achados[0].rule == "disallowed_extension"


# --- (c) caminho absoluto local ----------------------------------------------

def test_documentacao_pode_citar_caminho_absoluto():
    """docs/ não é diretório guardado: documentação pode citar caminho real
    de execução como evidência (ver docs/18)."""
    texto = "executado em " + _HOME_LOCAL + "\\projeto"
    achados = hygiene.find_local_path_findings("docs/18-estado.md", texto)
    assert achados == []


def test_codigo_com_caminho_absoluto_local_gera_achado():
    texto = 'BASE = r"' + _HOME_LOCAL + '\\qualquer"'
    achados = hygiene.find_local_path_findings("src/mastertool_bridge/x.py", texto)
    assert len(achados) == 1
    assert achados[0].rule == "local_absolute_path"


def test_caminho_de_runs_em_tools_gera_achado():
    texto = 'RUNS_DIR = "' + _RUNS_DIR_LOCAL + '"'
    achados = hygiene.find_local_path_findings("tools/algum_script.py", texto)
    assert len(achados) == 1
    assert "local_path_runs_dir" in achados[0].message


def test_caminho_com_barra_ESCAPADA_gera_achado():
    """A regressão que este teste guarda custou um probe inteiro.

    Um literal Python escreve o caminho com barra dupla (`"C:\\\\Program
    Files\\\\Altus\\\\MT9000"`), e a primeira versão da regra casava uma barra
    só. Resultado: `probes/43_bind_program_to_task.py` tinha o caminho de
    instalação fixo e produzia ZERO achados. Os outros três probes eram pegos
    por acidente, porque repetem o caminho na docstring com barra simples — a
    regra pegava a ocorrência redundante e perdia a que estava no código."""
    escapado = 'STUB = ("C:' + "\\\\" + 'Program Files' + "\\\\" + 'Altus' \
        + "\\\\" + 'MT9000 4.1.0")'
    achados = hygiene.find_local_path_findings(
        "scripts/mastertool/probes/qualquer.py", escapado)
    assert len(achados) == 1
    assert "local_path_mastertool_x_install" in achados[0].message


def test_as_duas_formas_de_barra_geram_o_MESMO_achado():
    """Simples e dupla descrevem o mesmo caminho: a regra não pode tratar uma
    como violação e a outra como texto inocente."""
    simples = hygiene.find_local_path_findings(
        "src/x.py", 'BASE = r"' + _HOME_LOCAL + '"')
    duplo = hygiene.find_local_path_findings(
        "src/x.py", 'BASE = "C:' + "\\\\" + 'Users' + "\\\\" + _USUARIO_LOCAL + '"')
    assert len(simples) == 1
    assert len(duplo) == 1
    assert simples[0].message.split(":")[0] == duplo[0].message.split(":")[0]


def test_probe_43_esta_na_catraca_e_nao_solto():
    """Dívida que a regra passou a ver entra na catraca — não vira exceção.

    A diferença importa: na catraca ela é listada, não reprova, e só pode
    encolher. Fora dela, seria dívida invisível de novo, por outro caminho."""
    chave = ("local_absolute_path",
             "scripts/mastertool/probes/43_bind_program_to_task.py",
             "local_path_mastertool_x_install")
    assert chave in hygiene.LOCAL_PATH_DEBT_BASELINE


@pytest.mark.parametrize("relpath,esperado", [
    ("src/mastertool_bridge/x.py", True),
    ("tests/unit/test_x.py", True),
    ("tools/y.py", True),
    ("scripts/mastertool/probes/1.py", True),
    ("docs/18-estado.md", False),
    ("README.md", False),
    ("config/scanner-defaults.yaml", False),
])
def test_is_guarded_path_for_local_paths(relpath, esperado):
    assert hygiene.is_guarded_path_for_local_paths(relpath) is esperado


# --- (d) segredo genérico -----------------------------------------------------

def test_texto_comum_sem_segredo_nao_gera_achado():
    texto = "api_key = obter_da_variavel_de_ambiente()\n"
    assert hygiene.find_secret_findings("src/config.py", texto) == []


def test_aws_access_key_id_gera_achado():
    texto = "key_id = '" + _AWS_KEY_FIXTURE + "'\n"
    achados = hygiene.find_secret_findings("src/x.py", texto)
    assert len(achados) == 1
    assert achados[0].rule == "secret"
    assert "secret_aws_access_key_id" in achados[0].message


def test_cabecalho_de_chave_privada_gera_achado():
    texto = _PEM_HEADER_FIXTURE + "\nMIIB...\n"
    achados = hygiene.find_secret_findings("config/qualquer.yaml", texto)
    assert any(a.rule == "secret" for a in achados)


def test_literal_atribuido_a_variavel_de_segredo_gera_achado():
    texto = _SEGREDO_ATRIBUIDO_FIXTURE + "\n"
    achados = hygiene.find_secret_findings("src/x.py", texto)
    assert len(achados) == 1
    assert "secret_assigned_literal" in achados[0].message


def test_marcador_de_escape_suprime_o_achado_de_segredo():
    """Documentação que precisa MOSTRAR a forma de uma chave (sem versionar
    uma real) escapa com o marcador -- e o teste prova que o escape só
    funciona por causa do marcador, não por acidente de regex."""
    texto = "key_id = 'AKIAABCDEFGHIJKLMNOP'  # hygiene: allow-secret-pattern\n"
    assert hygiene.find_secret_findings("docs/exemplo.md", texto) == []


# --- orquestração -------------------------------------------------------------

def test_format_finding_com_e_sem_linha():
    achado_com_linha = hygiene.Finding("client_data", "docs/x.md", 3, "motivo")
    achado_sem_linha = hygiene.Finding("oversized_file", "a.bin", None, "motivo")
    assert hygiene.format_finding(achado_com_linha) == "[client_data] docs/x.md:3 -- motivo"
    assert hygiene.format_finding(achado_sem_linha) == "[oversized_file] a.bin -- motivo"


def test_get_tracked_files_devolve_arquivos_reais_do_repositorio():
    """Prova de que a leitura é feita via `git ls-files` (rastreados), não
    via varredura de diretório: `pyproject.toml` está rastreado e um nome
    inventado não pode aparecer."""
    arquivos = hygiene.get_tracked_files(REPO_ROOT)
    assert "pyproject.toml" in arquivos
    assert "arquivo-que-nao-existe-e-nunca-foi-commitado.txt" not in arquivos


def test_run_checks_e_deterministico_sobre_arvore_sintetica(tmp_path):
    """Sobre uma árvore git sintética e minúscula, `run_checks` deve achar
    exatamente o violador plantado e nada mais."""
    import subprocess

    repo = tmp_path / "repo_sintetico"
    repo.mkdir()
    (repo / "src").mkdir()
    limpo = repo / "src" / "limpo.py"
    limpo.write_text("x = 1\n", encoding="utf-8")
    sujo = repo / "src" / "sujo.py"
    sujo.write_text(_ARQUIVO_SUJO, encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "teste@example.com"],
                    cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "teste"],
                    cwd=str(repo), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "inicial"], cwd=str(repo), check=True)

    achados = hygiene.run_checks(str(repo))
    assert len(achados) == 1
    assert achados[0].rule == "local_absolute_path"
    assert achados[0].relpath.replace("\\", "/") == "src/sujo.py"


def test_main_retorna_exit_ok_quando_limpo(tmp_path, capsys):
    import subprocess

    repo = tmp_path / "repo_limpo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "limpo.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "teste@example.com"],
                    cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "teste"],
                    cwd=str(repo), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "inicial"], cwd=str(repo), check=True)

    codigo = hygiene.main(["--root", str(repo)])
    assert codigo == hygiene.EXIT_OK


def test_main_retorna_exit_failed_quando_sujo(tmp_path):
    import subprocess

    repo = tmp_path / "repo_sujo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "sujo.py").write_text(_ARQUIVO_SUJO, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "teste@example.com"],
                    cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "teste"],
                    cwd=str(repo), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "inicial"], cwd=str(repo), check=True)

    codigo = hygiene.main(["--root", str(repo)])
    assert codigo == hygiene.EXIT_FAILED


# --- o repositório real -------------------------------------------------------

def test_checker_nao_tem_achado_fatal_no_perfil_interno():
    """Gate do slice R0. Se este teste falhar, é achado real a ser
    reportado -- NUNCA motivo para enfraquecer regra ou ampliar allow-list
    sem justificativa documentada.

    "Sem achado fatal" não é "sem achado": os identificadores de cliente e a
    dívida de caminho absoluto continuam sendo encontrados e listados. Eles
    não reprovam **aqui** porque esta árvore não tem remote -- e reprovam no
    perfil `publicacao`, que é o portão que importa para eles.
    """
    achados = hygiene.run_checks(REPO_ROOT)
    fatais, _publicacao, _conhecidos, obsoletos = hygiene.classify(
        achados, hygiene.PROFILE_INTERNO, hygiene.load_debt_baseline(REPO_ROOT))
    mensagens = "\n".join(hygiene.format_finding(a) for a in fatais)
    assert fatais == [], (
        "%d achado(s) FATAL de higiene no repositorio real -- reportar ao "
        "operador, nao suprimir:\n%s" % (len(fatais), mensagens))
    # A exigência de a catraca ENCOLHER vale só na árvore que a possui. Na
    # cópia sanitizada parte da dívida desaparece com a troca de caminhos, e
    # cobrar o encolhimento lá reprovaria um repositório por ser mais limpo
    # que o original.
    if hygiene.owns_debt_baseline(REPO_ROOT):
        assert obsoletos == [], (
            "a catraca lista dívida que não existe mais; remova de "
            "LOCAL_PATH_DEBT_BASELINE: %r" % (obsoletos,))


@pytest.mark.skipif(
    not hygiene.CLIENT_IDENTIFIER_PATTERNS,
    reason=("os padrões de cliente vivem em `tools/client_identifiers.py`, que NÃO é publicado. Na cópia publicada a lista é vazia e não há o que detectar — quem barra identificador de cliente é o sanitizador, antes."))
def test_perfil_publicacao_reprova_identificador_de_cliente_no_repo_real():
    """A contraprova do teste acima.

    Sem isto, "nenhum achado fatal no perfil interno" poderia significar que a
    regra de dado de cliente parou de encontrar qualquer coisa -- guarda verde
    por não olhar para nada. Este teste exige que ela ainda encontre, e que o
    portão de publicação ainda reprove.
    """
    achados = hygiene.run_checks(REPO_ROOT)
    fatais, _pub, _conhecidos, _obsoletos = hygiene.classify(
        achados, hygiene.PROFILE_PUBLICACAO, hygiene.load_debt_baseline(REPO_ROOT))
    de_cliente = [a for a in fatais if a.rule == "client_data"]
    assert de_cliente, (
        "o perfil `publicacao` não encontrou nenhum identificador de cliente "
        "no repositório interno; ou a sanitização já foi feita nesta árvore "
        "(e então esta expectativa mudou), ou a regra parou de funcionar"
    )


def test_catraca_nao_se_aplica_a_outra_raiz(tmp_path):
    """A catraca lista caminhos DESTE repositório.

    Aplicá-la a outra raiz faria toda entrada aparecer como "dívida que não
    existe mais" e reprovaria um repositório limpo -- foi exatamente o que
    aconteceu na primeira versão.
    """
    assert hygiene.load_debt_baseline(str(tmp_path)) == frozenset()
    assert hygiene.load_debt_baseline(REPO_ROOT) == hygiene.LOCAL_PATH_DEBT_BASELINE


def test_a_DONA_da_catraca_e_a_arvore_que_tem_o_sanitizador(tmp_path):
    """A cópia publicada roda esta mesma suíte, e nela parte da dívida some
    (o diretório pessoal é trocado) enquanto o caminho de instalação do MT9000
    sobrevive — ele é do produto, não da máquina.

    Por isso a catraca continua valendo lá (senão a dívida que sobrevive
    viraria achado novo), e só a exigência de ENCOLHER não vale."""
    # A asserção é sobre a REGRA, não sobre esta árvore: a cópia publicada roda
    # esta mesma suíte, e lá `REPO_ROOT` é a cópia. Um teste que afirmasse
    # "esta árvore é a dona" reprovaria lá — e reprovaria dizendo a verdade,
    # o que é a pior forma de teste quebrado.
    import os as _os

    sem_marcador = tmp_path / "copia"
    sem_marcador.mkdir()
    assert hygiene.owns_debt_baseline(str(sem_marcador)) is False

    com_marcador = tmp_path / "dona"
    (com_marcador / "tools").mkdir(parents=True)
    (com_marcador / "tools" / "sanitize_for_publication.py").write_text(
        "# marcador", encoding="utf-8")
    assert hygiene.owns_debt_baseline(str(com_marcador)) is True
    assert _os.path.isfile(_os.path.join(
        str(com_marcador), "tools", "sanitize_for_publication.py"))


def test_catraca_separa_novo_de_conhecido_e_de_obsoleto():
    """Os três caminhos da catraca, num só exercício."""
    conhecido = hygiene.Finding(
        "local_absolute_path", "scripts/x.ps1", 3, "padrao_a: motivo")
    novo = hygiene.Finding(
        "local_absolute_path", "scripts/novo.ps1", 9, "padrao_a: motivo")
    baseline = frozenset({
        ("local_absolute_path", "scripts/x.ps1", "padrao_a"),
        ("local_absolute_path", "scripts/ja_limpo.ps1", "padrao_a"),
    })
    novos, conhecidos, obsoletos = hygiene.apply_debt_ratchet(
        [conhecido, novo], baseline)
    assert novos == [novo]
    assert conhecidos == [conhecido]
    assert obsoletos == [("local_absolute_path", "scripts/ja_limpo.ps1", "padrao_a")]


def test_regra_desconhecida_e_fatal_em_todo_perfil():
    """Fail-closed: regra nova que ninguém classificou não entra valendo
    menos que as outras."""
    for perfil in hygiene.PROFILES:
        assert hygiene.severity_of("regra_inventada", perfil) == hygiene.SEVERITY_FATAL
