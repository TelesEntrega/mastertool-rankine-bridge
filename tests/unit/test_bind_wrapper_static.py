"""Verificacao ESTATICA do wrapper `scripts/mastertool/run_bind_program_call.ps1`.

Nao executa PowerShell, nao abre o MasterTool. Os testes centrais sao de
ALCANCE e de FAIL-CLOSED:

    ValidateOnly     nao alcanca probe algum e nao cria copia
    ReconOnly        alcanca o probe 42 (read-only); NUNCA o probe 43
    ExecuteMutation  alcanca 42 (recon), 43 (add + save_as) e 42 de novo
                     (postsave, sobre a SAIDA); NUNCA o build

O build nao esta aqui de proposito: vincular nao basta, mas "o vinculo
persistiu" e "o projeto compila" sao provas de naturezas diferentes, e o
instrumento do build ja existe (`probes/40`, por `run_w1_4_integrated.ps1
-ExecuteBuild`). Estes testes verificam que o wrapper DIZ isso ao operador em
vez de deixar a impressao de que o marco terminou.
"""

import io
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
WRAPPER_PATH = os.path.join(_REPO_ROOT, "scripts", "mastertool",
                            "run_bind_program_call.ps1")

PROBE42 = "42_recon_tasks_readonly.py"
PROBE43 = "43_bind_program_to_task.py"


@pytest.fixture(scope="module")
def fonte():
    return io.open(WRAPPER_PATH, encoding="utf-8-sig").read()


@pytest.fixture(scope="module")
def linhas(fonte):
    return fonte.split("\n")


@pytest.fixture(scope="module")
def codigo(fonte):
    """Somente codigo: sem o bloco `<# ... #>` e sem comentario. A prosa do
    cabecalho PROMETE coisas ("Nunca usa --noUI"), e uma busca literal no
    arquivo inteiro acusaria a propria promessa."""
    sem_ajuda = re.sub(r"<#.*?#>", "", fonte, flags=re.S)
    return "\n".join([re.sub(r"(?<!`)#.*$", "", l) for l in sem_ajuda.split("\n")])


def _primeira_linha_com(linhas, padrao):
    expressao = re.compile(padrao)
    for indice, linha in enumerate(linhas):
        if expressao.search(linha):
            return indice
    return None


def test_wrapper_existe():
    assert os.path.isfile(WRAPPER_PATH)


def test_arquivo_e_ascii_puro():
    """ASCII puro: acento em wrapper PowerShell 5.1 sem BOM vira mojibake, e o
    proprio texto de aborto ficaria ilegivel na hora em que mais importa."""
    dados = open(WRAPPER_PATH, "rb").read()
    nao_ascii = [i for i, byte in enumerate(bytearray(dados)) if byte > 127]
    assert not nao_ascii, "bytes nao-ASCII nas posicoes %s" % nao_ascii[:10]


# --- modos --------------------------------------------------------------------

def test_tres_modos_mutuamente_exclusivos_e_default_que_nao_abre_nada(codigo):
    for parametro in ("[switch]$ValidateOnly", "[switch]$ReconOnly",
                      "[switch]$ExecuteMutation"):
        assert parametro in codigo
    assert "$Mode = 'ValidateOnly'" in codigo
    assert "$selectedModes.Count -gt 1" in codigo
    assert "Modos mutuamente exclusivos" in codigo
    assert "assumindo -ValidateOnly (default)" in codigo


def test_cada_probe_e_mencionado_uma_unica_vez(linhas):
    for probe in (PROBE42, PROBE43):
        ocorrencias = [i for i, l in enumerate(linhas) if probe in l]
        assert len(ocorrencias) == 1, (probe, ocorrencias)


def test_validate_only_sai_antes_de_qualquer_lancamento(linhas):
    saida = _primeira_linha_com(linhas, r"\$Mode -eq 'ValidateOnly'")
    assert saida is not None
    trecho = "\n".join(linhas[saida:saida + 6])
    assert "exit 0" in trecho
    lancamento = _primeira_linha_com(linhas, r"\$obsRecon = Invoke-MasterTool")
    copia = _primeira_linha_com(linhas, r"Copy-Item -LiteralPath \$BaseProject")
    assert lancamento is not None and copia is not None
    assert saida < copia < lancamento


def test_recon_only_sai_antes_de_lancar_o_probe_43(codigo):
    """A ordem e medida no CODIGO, nunca no arquivo inteiro: o cabecalho cita
    `--mode=postsave` e os dois probes antes de qualquer execucao, e comparar
    com ele mediria a ordem do texto, nao a do fluxo."""
    saida = codigo.find("$Mode -eq 'ReconOnly'")
    lancamento_do_43 = codigo.find("$obsBind = Invoke-MasterTool")
    assert saida > 0 and lancamento_do_43 > saida
    trecho = codigo[saida:lancamento_do_43]
    assert "exit 0" in trecho
    assert "NENHUMA MUTACAO OCORREU" in trecho


def test_a_mutacao_so_acontece_depois_do_recon(codigo):
    recon = codigo.find("--mode=recon")
    bind = codigo.find("$obsBind = Invoke-MasterTool")
    postsave = codigo.find("--mode=postsave")
    assert recon > 0
    assert recon < bind < postsave


def test_o_recon_precisa_ter_medido_para_a_mutacao_comecar(codigo):
    assert "$reconMedido = ($recon.status -eq 'measured'" in codigo
    assert "O recon nao mediu as tasks" in codigo
    assert "nao e mutacao controlada" in codigo


# --- o build NAO pertence a este host ------------------------------------------

def test_o_wrapper_nunca_compila(codigo):
    """O probe 40 e CITADO ao operador, e nunca LANCADO: as tres aberturas
    deste host sao 42, 43 e 42 de novo."""
    assert "$probe40" not in codigo
    assert "--mode=build" not in codigo
    lancamentos = re.findall(r"-ProbePath (\$probe\d+)", codigo)
    assert lancamentos == ["$probe42", "$probe43", "$probe42"]


def test_o_wrapper_diz_que_o_build_e_etapa_propria(fonte, codigo):
    assert "O BUILD AINDA NAO FOI EXECUTADO" in codigo
    assert "probes/40_build_w1_4.py" in fonte
    assert "run_w1_4_integrated.ps1 -ExecuteBuild" in fonte
    assert "build_pending" in codigo
    assert "PERSISTIDO e NAO VALIDADO por compilacao" in codigo


# --- a copia descartavel -------------------------------------------------------

def test_wrapper_cria_a_copia_ele_mesmo_a_partir_do_base_project(codigo):
    """Achado de W1.5: aceitar caminho de copia pre-existente transforma "nao
    tocar o original" num passo manual, e passo manual e onde o erro entra."""
    assert "[string]$BaseProject" in codigo
    assert "Copy-Item -LiteralPath $BaseProject" in codigo
    assert "nunca reaproveita copia pre-existente" in codigo
    assert "nao esta isolado/vazio" in codigo


def test_base_project_e_o_do_plano_ou_recusa(codigo):
    """Duas fontes para a mesma entrada seriam duas verdades."""
    assert "$planData.input_project.base_path" in codigo
    assert "diverge do input_project.base_path do" in codigo


def test_confere_hashes_em_todas_as_pontas(codigo):
    assert "A copia difere do projeto-base." in codigo
    assert "A copia MUDOU durante o recon read-only." in codigo
    assert "O PROJETO-BASE ORIGINAL foi tocado." in codigo
    assert "A copia de ENTRADA foi modificada." in codigo
    assert "A SAIDA MUDOU durante o postsave read-only." in codigo
    # base, copia, copia apos recon, base apos recon, copia apos bind, saida,
    # saida apos postsave, plano congelado.
    assert codigo.count("Get-FileHash") >= 7


def test_recusa_output_existente_e_caminho_dentro_do_repo(codigo):
    assert "output ja existe" in codigo
    assert "caminho dentro do repositorio" in codigo


def test_espaco_e_proibido_na_copia_e_permitido_no_base(codigo):
    """O projeto do cliente MORA num caminho com espaco; quem entra em
    `--scriptargs` e a copia (achado do probe 15)."""
    assert "contem espaco" in codigo
    assert "base_path" in codigo


# --- fail-closed ---------------------------------------------------------------

def test_a_fase_de_escrita_nao_e_presumida(codigo):
    """O gate que este slice NAO abre: enquanto `W2_BIND_PROGRAM_CALL` nao
    estiver autorizada em safety.py, o modo de mutacao nem lanca o produto."""
    assert "$ExpectedPhase = 'W2_BIND_PROGRAM_CALL'" in codigo
    assert "CONTROLLED_WRITE_PHASE" in codigo
    assert "frozenset" in codigo
    assert "NAO autorizada em safety.py" in codigo
    assert "commit" in codigo and "isolado" in codigo
    assert "Ate la, use -ReconOnly." in codigo


def test_read_only_phase_e_conferido(codigo):
    assert "READ_ONLY_PHASE" in codigo


def test_guarda_de_fonte_do_probe_42_recusa_mutador(codigo):
    assert "$probe42Source" in codigo
    assert "'create_task'" in codigo
    assert "SOMENTE LEITURA e casa com" in codigo
    assert "Sessao recusada." in codigo


def test_guarda_de_fonte_do_probe_43_exige_uma_de_cada(codigo):
    """O marco autoriza DUAS mutacoes. Uma terceira chamada no fonte -- ainda
    que sobre outro receptor -- para a sessao antes de o produto abrir."""
    assert "$addCalls -ne 1" in codigo
    assert "$saveAsCalls -ne 1" in codigo
    assert "autoriza EXATAMENTE UMA" in codigo


def test_o_lookbehind_de_insert_esta_explicado(fonte, codigo):
    """`sys.path.insert(0, ...)` existe em todo probe do repositorio e nao tem
    nada a ver com a colecao de POUs: o RECEPTOR e que decide."""
    assert "(?<!sys\\.path)\\.insert" in codigo
    assert "o RECEPTOR e que decide" in fonte


def test_sem_noui_e_sem_matar_processo(codigo):
    assert "noUI" not in codigo
    for suspeito in ("Stop-Process", "Kill()", "taskkill"):
        assert suspeito not in codigo
    assert "CloseMainWindow" in codigo
    assert "NAO mata processo" in codigo


def test_sem_fallback_de_executavel(codigo):
    assert "$exeVersion -ne $ExpectedExeVersion" in codigo
    assert "MT8500.exe" not in codigo


def test_sem_retry_nem_fallback_de_lancamento(codigo):
    lancamentos = [m.start() for m in re.finditer(r"= Invoke-MasterTool", codigo)]
    assert len(lancamentos) == 3
    for construcao in (r"while\s*\([^)]*\)\s*\{", r"for\s*\([^)]*\)\s*\{",
                       r"foreach\s*\([^)]*\)\s*\{", r"catch\s*\{"):
        for encontrado in re.finditer(construcao, codigo):
            posicao = encontrado.end() - 1
            profundidade = 0
            fim = posicao
            while fim < len(codigo):
                if codigo[fim] == "{":
                    profundidade += 1
                elif codigo[fim] == "}":
                    profundidade -= 1
                    if profundidade == 0:
                        break
                fim += 1
            assert "Invoke-MasterTool" not in codigo[posicao:fim], construcao
    assert re.search(r"function Fail\([^)]*\)\s*\{[^}]*exit 2", codigo, re.S)


def test_exit_code_do_launcher_nao_decide(codigo):
    assert "O exit code do launcher NAO decide nada." in codigo
    assert "$bind.status -ne 'saved_as'" in codigo
    assert "if ($launcherExit" not in codigo
    assert "$launcherExit -eq 0" not in codigo


def test_conclusao_detectada_por_artefato(codigo):
    assert "CompletionPath" in codigo
    assert "artefato de conclusao presente" in codigo
    assert "tasks-completion.json ausente" in codigo
    assert "bind-completion.json ausente" in codigo


def test_orfaos_reprovam_em_cada_etapa(codigo):
    assert codigo.count("orphan_ids.Count -gt 0") >= 3


def test_descarte_da_copia_inteira_e_a_regra(codigo):
    assert "DESCARTE a copia inteira" in codigo
    assert "nao existe rollback" in codigo


# --- o plano -------------------------------------------------------------------

def test_o_plano_e_conferido_campo_a_campo(codigo):
    assert "$planData.phase -ne $ExpectedPhase" in codigo
    assert "'w2-bind-program-call'" in codigo
    assert "$kinds.Count -ne 2" in codigo
    assert "$kinds[0] -ne 'add'" in codigo
    assert "$kinds[1] -ne 'save_as'" in codigo
    assert "$planData.operations[0].target -ne 'task_pou_collection'" in codigo
    assert "task_name" in codigo and "program_name" in codigo


def test_o_alvo_declarado_do_add_tem_a_razao_escrita(fonte):
    """`add` colide com o metodo homonimo de `list`, e a colecao de POUs herda
    de `list`. O alvo declarado e o que impede que um plano autorize "um add
    qualquer"."""
    assert "colide com o metodo" in fonte
    assert "task_pou_collection" in fonte


# --- persistencia: a prova que fecha o marco -----------------------------------

def test_o_postsave_roda_sobre_a_saida_em_abertura_separada(codigo):
    assert "-ProjectPath $outputPath -ProbePath $probe42" in codigo
    assert "--mode=postsave" in codigo
    assert "--expect-task=" in codigo
    assert "--expect-pou=" in codigo
    assert "abertura separada sobre a saida" in codigo


def test_o_veredito_exige_o_vinculo_persistido(codigo):
    assert "$postsave.status -eq 'binding_verified'" in codigo
    assert "$postsave.binding_verified -eq $true" in codigo
    assert "program_call_persisted" in codigo
    assert "exit 3" in codigo


def test_recon_sem_medida_nao_sai_zero(codigo):
    assert "exit 4" in codigo
    assert "as tasks NAO foram medidas" in codigo


# --- o dialogo -----------------------------------------------------------------

def test_o_aviso_do_dialogo_vem_ANTES_do_lancamento(codigo):
    """Aviso que chega junto com o evento nao e aviso. A instrucao tem de estar
    impressa antes da copia e antes do Start-Process -- quando o dialogo
    aparecer, o operador ja precisa saber o que fazer."""
    posicao_aviso = codigo.find('CLIQUE "NAO".')
    posicao_copia = codigo.find("Copy-Item -LiteralPath $BaseProject")
    # O LANCAMENTO e a CHAMADA de Invoke-MasterTool, nao a linha `Start-Process`
    # dentro da definicao da funcao: a definicao aparece antes no texto e depois
    # na execucao, e comparar com ela mediria a ordem errada.
    posicao_lancamento = codigo.find("$obsRecon = Invoke-MasterTool")
    assert posicao_aviso > 0
    assert posicao_aviso < posicao_copia < posicao_lancamento


def test_o_host_nao_responde_o_dialogo_por_conta_propria(fonte, codigo):
    """Automatizar o clique num dialogo de salvamento daria ao host o poder de
    gravar. O host fecha a janela (CloseMainWindow) e para por ai."""
    assert "system.exit(0)" in fonte
    for envio in ("SendKeys", "AppActivate", "SendMessage", "PostMessage",
                  "SendWait"):
        assert envio not in codigo


def test_o_aviso_explica_o_que_o_SIM_destruiria(fonte):
    assert "Deseja salvar as alteracoes?" in fonte
    assert "COPIA DE ENTRADA" in fonte
    assert "CANCELAR" in fonte


# --- codificacao ---------------------------------------------------------------

def test_json_gravado_sem_bom(codigo):
    assert "System.Text.UTF8Encoding($false)" in codigo
    assert "[System.IO.File]::WriteAllText" in codigo
    assert "Out-File" not in codigo
