# -*- coding: utf-8 -*-
"""Guarda de seguranca dos scripts internos. Espelha config/safety-policy.yaml.

Base: SOMENTE LEITURA. `READ_ONLY_PHASE` continua True e as sete operacoes
legadas de WRITE_OPERATIONS seguem bloqueadas -- abrir uma fase de escrita
controlada NAO mexe nesse booleano.

Sobre essa base, `CONTROLLED_WRITE_PHASE` pode nomear UMA fase por vez, e a
allowlist dessa fase nomeia as operacoes uma a uma. Nome fora da allowlist,
fase desconhecida, fase ausente e operacao desconhecida sao todos bloqueados
aqui, independentemente de configuracao (fail closed).

QUAL FASE ESTA ABERTA E O QUE ELA AUTORIZA ESTAO NO COMENTARIO ACIMA DE
`CONTROLLED_WRITE_PHASE`, e so la. Esta docstring ja repetiu esse estado e
envelheceu tres vezes -- duas fontes para o mesmo fato divergem, e a que
ninguem edita e a que mente.
"""
from __future__ import print_function

READ_ONLY_PHASE = True

FORBIDDEN_OPERATIONS = [
    "modify_original_project",
    "download_to_plc",
    "go_online",
    "login_to_controller",
    "start_controller",
    "stop_controller",
    "reset_controller",
    "force_variables",
    "write_physical_outputs",
    "change_hardware_configuration",
    "install_libraries_without_authorization",
    "import_without_backup",
    "apply_ai_changes_to_official_project",
]

WRITE_OPERATIONS = [
    "save_project",
    "import_object",
    "create_object",
    "delete_object",
    "modify_object",
    "set_declaration",
    "set_implementation",
]

# --- escrita controlada no MasterTool X (docs/28, docs/29) -------------------
#
# ACHADO de 2026-07-31, ao preparar o gate de W1.1: `assert_operation_allowed`
# so conhecia os sete nomes de WRITE_OPERATIONS e devolvia True para qualquer
# outro. Ou seja, com READ_ONLY_PHASE = True, `create_gvl`, `save_as`,
# `create_program`, `replace`, `build` e `import_xml` TODOS passavam. O gate
# nunca cobriu a superficie do MasterTool X -- ele falhava ABERTO para todo
# nome que nao estivesse na lista legada.
#
# Registro LITERAL das operacoes mutaveis catalogadas em docs/27 secao 7.
# Nomes exatos, sem curinga e sem prefixo: `create_*` nao existe aqui de
# proposito. Uma API que nao esteja nesta lista tambem e recusada -- nome
# desconhecido falha FECHADO.
MASTERTOOL_MUTATING_OPERATIONS = frozenset([
    # criacao de objeto IEC
    "create_gvl", "create_pou", "create_program", "create_function",
    "create_function_block", "create_dut", "create_interface",
    "create_persistentvars", "create_folder", "create_task",
    "create_task_configuration", "create_boot_application",
    # conteudo textual
    "replace", "replace_line", "insert", "remove", "append",
    # persistencia
    "save", "save_as", "save_archive",
    # compilacao
    "build", "rebuild", "clean",
    # importacao
    "import_xml", "import_native", "import_device",
    "import_vendor_description", "import_io_mappings_from_csv",
    # estrutura
    "rename", "move", "add",
    # dispositivo e repositorio
    "unplug", "update", "set_gateway_and_ip_address", "remove_device",
    "remove_vendor_description", "save_device_cache",
    # configuracao de projeto e bibliotecas
    "set_compilerversion_to_newest", "download_missing_libraries",
    "remove_library", "add_library",
])

# Registro LITERAL das ESCRITAS DE PROPRIEDADE catalogadas.
#
# Classe de mutacao distinta da de cima, e nao um apendice dela: as de cima sao
# CHAMADAS (`objeto.metodo(...)`), estas sao ATRIBUICOES (`objeto.campo = x`).
# A diferenca importa porque a guarda de uma nao enxerga a outra -- ver
# `assert_controlled_property_write_allowed`.
#
# O prefixo `set:` nao e decoracao. Ele impede que um nome de propriedade se
# confunda com um nome de metodo dentro da MESMA allowlist de fase: `add`,
# `replace`, `insert` e `remove` sao metodos catalogados e seriam nomes
# plausiveis de campo.
#
# Cada nome vem do stub que o produto instala, com a linha citada -- nenhum foi
# inventado. `ScriptTaskConfigObject.pyi` (MT9000 4.1.0.11):
#
#     L92-95    kind_of_task.setter   (enum KindOfTask, L5-11)
#     L106-116  priority.setter       (str)
#     L119-131  interval.setter       (str; exige kind_of_task Cyclic ou
#                                      ExternalEvent, diz o proprio stub)
#     L135-146  interval_unit.setter  (str)
#
# FORA, e cada ausencia com motivo: `event`, `external_event`, `core_binding` e
# `parent_synchron_task` sao settable no stub e nao servem a nenhuma spec que
# este projeto saiba escrever; `watchdog.*` tem RECEPTOR proprio
# (`ScriptWatchdog`), e receptor novo e verificacao nova.
MASTERTOOL_PROPERTY_WRITES = frozenset([
    "set:kind_of_task", "set:interval", "set:interval_unit", "set:priority",
])

# Fase de escrita controlada ATUALMENTE autorizada, ou None.
#
# Isto NAO e um booleano de propósito: `READ_ONLY_PHASE = False` autorizaria de
# uma vez as sete operacoes de WRITE_OPERATIONS, que e exatamente a abertura
# generica que docs/28 secao 14 proibe. A fase nomeia o marco, e o marco nomeia
# as operacoes -- uma por uma.
#
# NENHUMA FASE ATIVA.
#
# W9 -- a primeira escrita de propriedade -- foi EXECUTADA e ENCERRADA
# (docs/49, run-037). As quatro escritas foram relidas do objeto e depois do
# projeto salvo e reaberto; a `MainTask` ficou intacta, que e o que prova que
# a escrita foi na task certa.
#
# O que segue e o registro do que a fase existiu para provar.
#
# Classe de mutacao nova, e a primeira fase a autorizar nomes com prefixo
# `set:`. Ate a run-036 este gate so sabia falar de chamada de metodo, e
# `task.interval = x` nao era recusado: era invisivel.
#
# O QUE ELA EXISTE PARA CORRIGIR, medido na run-036 (docs/48 secao 4):
#
#     MainTask (template)         Cyclic  100     ms  prioridade 13
#     TaskDiagnostico (criada)    Cyclic  t#20ms  ms  prioridade  1
#
# A task que a fabrica cria nasce mais RAPIDA e mais PRIORITARIA que a task
# principal do projeto. Nada disso veio da spec -- sao os defaults do produto.
# Uma fabrica que gera projeto com o tempo errado gera projeto errado.
#
# As QUATRO escritas de propriedade catalogadas estao aqui, e nenhuma a mais.
# `watchdog.*` fica de fora: receptor proprio (`ScriptWatchdog`), e receptor
# novo e verificacao nova.
#
# Os verbos de metodo que acompanham sao o minimo para que a prova aconteca num
# projeto que compila: nao da para medir o tempo de uma task que nao existe,
# vazia, num projeto que nao salva.
#
# W8 -- criar a task E dar-lhe o POU -- foi EXECUTADA e ENCERRADA (docs/48,
# run-036). O aviso da run-032 sumiu, e a saida reaberta foi medida com a task
# presente e `PRG_DIAG` na posicao 0 da lista dela. Com isso, as DOZE operacoes
# do vocabulario estao provadas em campo, e a lista de operacoes em prova do
# executor voltou a ficar VAZIA.
#
# O que segue e o registro do que a fase existiu para provar.
#
# `create_task` era a UNICA operacao do vocabulario sem prova, e o que faltava
# nao era a API: era o caminho para ENCHER a task. Ele existe, e o aviso do
# fabricante que W2 mediu e quem o indica, ao nomear `MainTask`:
#
#     "A tarefa MainTask deveria conter apenas a chamada do programa MainPrg.
#     Chamadas adicionais de outros programas devem ser realizadas a partir
#     das POUs correspondentes do Perfil de Projeto"
#
# O fabricante esta falando da task DO PERFIL. Uma task criada pela spec nao e
# ela, o perfil nao diz nada sobre ela, e `UserPrg` -- que roda pela cadeia da
# `MainTask` -- seria o caminho ERRADO. Para essa, a lista de POUs da propria
# task e o unico caminho, e e o mesmo verbo `add` que W2 exerceu: outro
# RECEPTOR, mesma API (`ScriptPouObjectCollection.add`, stub L288).
#
# A prova so vale inteira: task criada, POU dentro, salva, reaberta e compilada
# SEM aviso. A run-032 ja mostrou que a task vazia compila -- com o aviso "No
# POU is defined for task". E o aviso que esta fase existe para fazer sumir.
#
# W7 -- a fabrica com TUDO que esta provado -- foi EXECUTADA e ENCERRADA
# (docs/47, runs 034 e 035). Uma spec de maquina com 7 objetos de 5 familias,
# com dependencia real entre eles, virou projeto DUAS vezes sobre copias novas:
# 0 erros, 0 avisos, 7 de 7 objetos verificados, 49 nos, conteudo EQUIVALENTE
# entre as duas geracoes e nove `object_guid` distintos provando que as
# geracoes foram independentes.
#
# `W4_EXECUTE_PLAN` foi a fase da fabrica quando ela sabia criar GVL e
# PROGRAM. Desde entao FB, FUNCTION e DUT foram provados (docs/43, docs/46),
# e a allowlist de W4 ficou menor que o que a fabrica sabe fazer.
#
# W7 NAO ALARGA W4: ela e a UNIAO das allowlists de autoria das fases que ja
# provaram cada verbo, e ha teste afirmando essa igualdade. Nada aqui foi
# autorizado que um marco anterior nao tenha exercido contra o produto.
#
#     create_gvl              W1.1, W1.4
#     create_program          W1.2, W1.4
#     create_function_block   W5 (run-028)
#     create_function         W5 (run-028)
#     create_dut              W6 (run-033)
#     replace                 W1.3A, W1.3B, W3
#     save_as                 todas
#
# FORA: `build` (fase propria), `add` (recusado como padrao em docs/41) e
# `create_task` -- a UNICA operacao do vocabulario ainda sem prova, porque a
# task criada compila com aviso e nao ha caminho medido para lhe dar um POU.
#
# HISTORICO: W1 a W9 completos. TREZE de treze operacoes do vocabulario
# provadas, e as DUAS classes de mutacao -- chamada e atribuicao -- exercidas
# contra o produto.
#
# `create_dut` PROVADO na run-033 (docs/46): STRUCT e ENUM criados,
# persistidos e compilados, com um PROGRAM que declara uma variavel de
# cada -- 0 erros, 0 avisos, 3 de 3 objetos verificados.
#
# `create_task` EXERCIDO na run-032 e NAO PROVADO. A task foi criada e
# sobreviveu a `save_as`, e o build passou com 0 erros -- e com um AVISO:
# "No POU is defined for task". Enche-la exigiria vincular um PROGRAM a
# uma task que nao e a do perfil, e para isso nao ha caminho medido: a
# chamada idiomatica escreve em `UserPrg`, que roda pela cadeia da
# `MainTask` (docs/41). A API funciona; a OPERACAO nao serve a fabrica
# ainda, e marca-la como provada prometeria capacidade que nao existe.
#
# Historico da fase, que fica no mapa como registro:
#
# As DUAS ultimas operacoes do vocabulario sem prova em cadeia.
#
# `create_dut` esteve bloqueada desde docs/35 por uma afirmacao ERRADA
# minha -- "os valores do enum DutType nao estao catalogados". Estavam,
# no stub que o produto instala, e a run-031 (docs/45) mediu que o enum e
# injetado no escopo do script. Foi a QUARTA vez que confundi "meu
# catalogo nao tem" com "a API nao tem".
#
# `create_task` nunca entrou em fase alguma: todas as execucoes reusaram
# a `MainTask` do template.
#
# Mesmo mecanismo de W5: o planner recusa plano executavel com operacao
# nao provada, e quem desempata e esta allowlist -- escrever o verbo aqui,
# a mao, e a decisao humana de que a execucao existe para exerce-lo.
#
# HISTORICO: W1 a W5 completos.
#
# FB E FUNCTION FORAM PROVADOS (docs/43, run-028) numa cadeia completa --
# create, replace, save_as, reabrir, build. Ate ali as duas operacoes
# tinham API catalogada e nenhuma prova: W1.5 (docs/35) as criou apenas
# para LER o texto de nascimento e descartar a copia SEM salvar.
#
# A prova e conclusiva porque o PROGRAM gerado INSTANCIA o FB e CHAMA a
# FUNCTION: criar os dois e deixa-los soltos provaria que a API cria
# objeto, e nao que o objeto serve. Nascimento quebrado teria reprovado no
# `Typify code`.
#
# O OVO-E-GALINHA QUE W5 RESOLVEU: o planner e fail-closed em
# `field_proven` e nao emite plano executavel com operacao nao provada;
# sem executar, nao ha prova. A saida nao foi marcar `field_proven` antes
# de medir -- seria declarar em vez de medir, o fail-open fechado em
# docs/42 secao 4. A saida foi a ALLOWLIST: escrever o verbo a mao numa
# fase cujo proposito e exerce-lo. Depois da medicao, o contrato do planner
# ganhou `field_proven: True` com a run citada, e a lista de operacoes em
# prova do executor voltou a ficar VAZIA.
#
# A FABRICA JA FUNCIONA (docs/42, run-027). W4 foi a primeira fase que nao
# pertenceu a um marco de UMA operacao: ela autorizou o executor a rodar um
# PLANO, cujos objetos vem da spec. Medido:
#
#     spec.json      1 GVL, 2 PROGRAMs, 2 chamadas
#     plano          14 passos, emitido offline pelo planner
#     execucao       11 passos; 3 delegados (reopen, build, verify)
#     criados        GVL_FABRICA, PRG_BOMBA, PRG_PRESSAO
#     build          0 erros, 0 avisos do fabricante
#
# Os tres nomes vem da SPEC e nao aparecem em codigo nenhum -- e essa e a
# diferenca entre provar operacoes e ter fabrica.
#
# A ALLOWLIST DE W4 NAO FOI DERIVADA DO PLANO, e essa foi a decisao que
# importava. O plano declara `required_allowlist`, e seria comodo abrir a
# fase com o que ele pedir -- e ai a fase deixaria de autorizar coisa alguma,
# porque o proprio pedido definiria a permissao. A lista ficou LITERAL, e o
# executor recusa rodar se os passos exigirem alem dela.
#
# Foram os QUATRO verbos de autoria provados em campo, e nenhum a mais:
#
#     create_gvl      W1.1 (docs/33), W1.4 (runs 019-025)
#     create_program  W1.2 (docs/30), W1.4
#     replace         W1.3A, W1.3B, W1.4, W3 -- inclusive a chamada
#                     idiomatica, que E um `replace` na POU de perfil
#     save_as         todas as execucoes
#
# FORA, e cada ausencia com motivo: `build` tem fase propria (verificar nao e
# autoria); `add` e o caminho de W2, provado como CAPACIDADE e recusado como
# PADRAO (docs/41); `create_function_block`, `create_function`, `create_dut` e
# `create_task` tem API catalogada e NENHUMA foi exercida numa cadeia que
# persistiu e compilou. O planner ja marca `field_proven: False` e recusa
# emitir plano executavel com elas -- a allowlist e a segunda porta.
#
# HISTORICO. DEZOITO fases abertas e encerradas, cada uma com abertura e
# fechamento em commit proprio: W1.1, W1.2, W1.3A, W1.3B, W1.5, W1.4,
# W2_BIND_PROGRAM_CALL, W2_VERIFY_BUILD, W3_IDIOMATIC_CALL,
# W3_VERIFY_BUILD, W4_EXECUTE_PLAN, W4_VERIFY_BUILD,
# W5_PROVE_IEC_PACKAGE, W5_VERIFY_BUILD, W6_PROVE_DUT_AND_TASK,
# W6_VERIFY_BUILD, W7_FACTORY_FULL, W7_VERIFY_BUILD, W8_PROVE_TASK_WITH_POU
# W8_VERIFY_BUILD, W9_PROVE_TASK_TIMING e W9_VERIFY_BUILD.
#
# W1_4_INTEGRATED_BUILD foi REABERTA uma vez, com a MESMA allowlist, para medir
# DETERMINISMO (docs/40): cinco geracoes, dez pares, zero divergencias -- e
# cinco arquivos de bytes DISTINTOS. Reabrir saiu barato precisamente porque
# encerrar nunca apagou a allowlist; ela ficou no mapa como registro.
#
# W3 respondeu a pergunta que W2 deixou (docs/41): `add` na MainTask compila
# com 1 aviso do fabricante, e a chamada dentro de `UserPrg` com 0. Mesma
# cadeia, mesmo compilador. E por isso que a fabrica gera pela segunda forma.
#
# Encerrar esta fase e commit ISOLADO, com os testes estruturais junto,
# conforme docs/28 secao 14.
CONTROLLED_WRITE_PHASE = None

# Allowlist por fase. Nome exato, comparacao por igualdade, sem correspondencia
# parcial. Acrescentar operacao aqui e decisao humana em commit proprio.
#
# A entrada de W1_1_CREATE_GVL PERMANECE no mapa de proposito: ela e o registro
# historico de qual allowlist esteve ativa, e apagar o registro apagaria a
# evidencia de que a fase existiu. Estar no mapa NAO autoriza nada -- quem
# autoriza e CONTROLLED_WRITE_PHASE apontar para a entrada, e ele nao aponta
# para nenhuma.
PHASE_ALLOWED_OPERATIONS = {
    # ENCERRADA. Fica no mapa como registro historico; nao esta ativa.
    "W1_1_CREATE_GVL": frozenset(["create_gvl", "save_as"]),
    # ENCERRADA. `create_pou` nunca entrou: o preflight provou que
    # `create_program` bastava, e uma allowlist que cresce por precaucao deixa
    # de descrever o que esta em uso (docs/30).
    "W1_2_CREATE_PROGRAM": frozenset(["create_program", "save_as"]),
    # ENCERRADA. Edicao textual de GVL existente (docs/31, executada em
    # docs/33). Sem `create_gvl`: a entrada foi `W1-A1.project`, artefato
    # imutavel de W1.1, e a GVL nao foi recriada. `insert` e `append` tambem
    # nunca entraram -- o probe usa `replace` e so ele, e allowlist nao
    # antecipa operacao que ninguem chama.
    "W1_3A_EDIT_GVL": frozenset(["replace", "save_as"]),
    # ENCERRADA. Edicao textual de PROGRAM ST existente (docs/31, executada em
    # docs/34). Allowlist IDENTICA a de W1.3A, e de proposito: o verbo
    # autorizado e o mesmo, o que muda e quantos documentos o recebem -- dois
    # aqui, um la. A cardinalidade foi verificada pelo probe e pelo artefato,
    # nao pela allowlist.
    "W1_3B_EDIT_PROGRAM": frozenset(["replace", "save_as"]),
    # ENCERRADA. Medicao de texto de nascimento (docs/35), executada nas
    # runs 013 e 014 com resultado identico byte a byte. E a UNICA fase ate hoje
    # sem `save_as`: ela cria para LER e descarta a copia sem persistir. Sem
    # `create_dut` -- os valores de `DutType` nao estao catalogados, e allowlist
    # nao antecipa API que ninguem sabe chamar.
    "W1_5_MEASURE_IEC_BIRTH": frozenset(["create_function_block",
                                         "create_function"]),
    # ENCERRADA. Autoria integrada com build (docs/32), executada e
    # aprovada na run-019 com `integration_verified`. A allowlist mais larga ate
    # hoje, e mesmo assim NAO tem `save`: `save_as` escreve em arquivo novo e
    # preserva a entrada; `save` sobrescreveria a testemunha do estado inicial.
    "W1_4_INTEGRATED_BUILD": frozenset(["create_gvl", "create_program",
                                        "replace", "save_as", "build"]),
    # ENCERRADA. Program Call (docs/38), executada na run-021: pous de
    # ["MainPrg"] para ["MainPrg", "PRG_AI_TESTE"], vinculo confirmado em
    # reabertura independente.
    "W2_BIND_PROGRAM_CALL": frozenset(["add", "save_as"]),
    # ENCERRADA. Verificacao por compilacao da saida de W2 (run-021):
    # build_verified, 0 erros, 1 aviso de convencao do fabricante. Uma
    # operacao, e nenhuma escrita: verificar nao e autoria.
    "W2_VERIFY_BUILD": frozenset(["build"]),
    # ATIVA. A chamada IDIOMATICA (docs/41): a chamada do PROGRAM vai para
    # dentro de `UserPrg`, POU do Perfil de Projeto, e nao para a lista da
    # MainTask.
    #
    # Allowlist IDENTICA a de W1.3A e W1.3B, e isso e o ponto: o verbo e o
    # mesmo `replace` que W1.3B ja provou sobre um PROGRAM. O que muda nao e a
    # capacidade -- e ONDE a chamada mora, que e a diferenca entre "funciona" e
    # "esta certo". Uma allowlist mais larga aqui sugeriria uma capacidade nova
    # que este marco nao exerce.
    #
    # Sem `add`: acrescentar a lista da task e exatamente o que W2 fez e o que
    # o fabricante desaconselha. Sem `create_*`: o PROGRAM ja existe, vem da
    # saida de W1.4. Sem `build`: verificar tem fase propria.
    "W3_IDIOMATIC_CALL": frozenset(["replace", "save_as"]),
    # ATIVA. Verificacao por compilacao da saida de W3. UMA operacao, nenhuma
    # escrita -- mesma separacao que `W2_VERIFY_BUILD` estabeleceu: juntar
    # `build` na fase da mutacao alargaria a autoria para cobrir verificacao.
    "W3_VERIFY_BUILD": frozenset(["build"]),
    # ATIVA. A FABRICA (docs/42): o executor roda um plano emitido pelo
    # planner a partir de uma spec. Os CINCO verbos provados em campo, e
    # nenhum a mais.
    #
    # E a uniao de W1.4 com W3, e nao uma abertura nova: W1.4 autorizava
    # `create_gvl, create_program, replace, save_as, build` e W3
    # `replace, save_as`. Aqui `build` sai -- verificar tem fase propria --
    # e sobram os quatro de autoria.
    "W4_EXECUTE_PLAN": frozenset(["create_gvl", "create_program",
                                  "replace", "save_as"]),
    # ATIVA no momento do build. Mesma separacao de W2 e W3.
    "W4_VERIFY_BUILD": frozenset(["build"]),
    # ATIVA. Provar FB e FUNCTION numa cadeia que PERSISTE e COMPILA.
    #
    # E a allowlist de W4 mais os dois verbos em prova. `create_dut` fica
    # de fora: os valores do enum `DutType` nao estao catalogados
    # (docs/35 secao 1), e chamar sem o subtipo certo seria inventar a
    # API -- allowlist nao antecipa operacao que ninguem sabe chamar.
    "W5_PROVE_IEC_PACKAGE": frozenset(["create_gvl", "create_program",
                                       "create_function_block",
                                       "create_function", "replace",
                                       "save_as"]),
    # ATIVA no momento do build. Mesma separacao de W2, W3 e W4.
    "W5_VERIFY_BUILD": frozenset(["build"]),
    # ATIVA. Provar `create_dut` e `create_task` em cadeia que persiste e
    # compila. E a allowlist de W5 mais os dois verbos em prova.
    "W6_PROVE_DUT_AND_TASK": frozenset(["create_gvl", "create_program",
                                        "create_function_block",
                                        "create_function", "create_dut",
                                        "create_task", "replace",
                                        "save_as"]),
    # ATIVA no momento do build.
    "W6_VERIFY_BUILD": frozenset(["build"]),
    # ATIVA. A fabrica com TODAS as operacoes de autoria provadas. E a uniao
    # das allowlists de autoria de W1.4, W3, W5 e W6 -- sem `build`, sem `add`
    # e sem `create_task`.
    "W7_FACTORY_FULL": frozenset(["create_gvl", "create_program",
                                  "create_function_block", "create_function",
                                  "create_dut", "replace", "save_as"]),
    "W7_VERIFY_BUILD": frozenset(["build"]),
    # A cadeia que W6 nao teve: criar a task E dar-lhe o POU. ENCERRADA.
    #
    # `add` volta a uma allowlist depois de W2, e a razao pela qual ele saiu
    # nao vale aqui. O aviso do fabricante nomeia a `MainTask` -- ele fala da
    # task DO PERFIL, cuja convencao e chamar de dentro das POUs do perfil.
    # Uma task criada pela spec nao e ela, e para essa a lista de POUs da
    # propria task e o unico caminho que existe: `UserPrg` roda pela cadeia da
    # `MainTask`, e chegar por ali ligaria o programa ao ciclo errado.
    #
    # Os DOIS verbos em prova sao `create_task` e `add`, e a fabrica de W7
    # continua sem nenhum dos dois. Os outros cinco estao aqui porque a prova
    # precisa de um projeto que compile: uma task cheia de um PROGRAM que nao
    # existe nao mediria nada.
    "W8_PROVE_TASK_WITH_POU": frozenset(["create_gvl", "create_program",
                                         "create_dut", "create_task", "add",
                                         "replace", "save_as"]),
    "W8_VERIFY_BUILD": frozenset(["build"]),
    # ENCERRADA. A primeira fase a autorizar ESCRITA DE PROPRIEDADE -- os quatro
    # nomes com prefixo `set:` vem de `MASTERTOOL_PROPERTY_WRITES`, e a porta
    # que os confere e `assert_controlled_property_write_allowed`.
    "W9_PROVE_TASK_TIMING": frozenset(["create_gvl", "create_program",
                                       "create_task", "add", "replace",
                                       "save_as",
                                       "set:kind_of_task", "set:interval",
                                       "set:interval_unit", "set:priority"]),
    "W9_VERIFY_BUILD": frozenset(["build"]),
    # W10 -- ALTERACAO DE OBJETO PREEXISTENTE (fase R2).
    #
    # A allowlist e a MENOR possivel: `replace` e `save_as`. Nenhum `create_*`
    # entra, e a ausencia e o desenho -- W10 prova que o sistema ALTERA, e um
    # `create` na mesma allowlist deixaria a prova ambigua entre "alterou" e
    # "criou por cima".
    #
    # E a mesma allowlist de W1_3A/W1_3B, que alteraram texto de objeto que a
    # propria sessao havia criado. A diferenca de W10 nao esta nos verbos: esta
    # em o alvo ser PREEXISTENTE, e no executor conferir o hash anterior MEDIDO
    # antes de sobrescrever.
    "W10_EDIT_EXISTING": frozenset(["replace", "save_as"]),
    "W10_VERIFY_BUILD": frozenset(["build"]),
    # REVERSAO (fase R2, quarta palavra do gate). Fases PROPRIAS, e nao reuso
    # das de cima: desfazer nao e um detalhe da mesma sessao que fez. Uma
    # reversao autorizada pela fase da alteracao poderia rodar dentro dela, e
    # entao "alterou e desfez" e "alterou" seriam indistinguiveis no registro.
    #
    # A allowlist e IDENTICA a de W10_EDIT_EXISTING de proposito: a reversao
    # usa o MESMO mecanismo, com o MESMO rigor. Reverter por um caminho mais
    # curto seria provar reversibilidade de outra coisa.
    "W10_REVERT": frozenset(["replace", "save_as"]),
    "W10_REVERT_VERIFY_BUILD": frozenset(["build"]),
}

try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)         # Python 3 (testes)


class SafetyError(Exception):
    """Operacao bloqueada pela politica de seguranca."""
    pass


def assert_operation_allowed(operation):
    """Lanca SafetyError se a operacao for proibida na fase atual.

    Guarda das operacoes LEGADAS. Operacao mutavel do MasterTool X nunca e
    liberada por aqui: ela e desviada para `assert_controlled_write_allowed`,
    de modo que exista UMA unica porta para escrita controlada. Duas portas
    seriam duas politicas, e a segunda envelheceria em silencio.
    """
    if operation in FORBIDDEN_OPERATIONS:
        raise SafetyError(
            "Operacao '%s' e permanentemente proibida pela politica de "
            "seguranca (config/safety-policy.yaml)." % operation)
    if operation in MASTERTOOL_MUTATING_OPERATIONS:
        raise SafetyError(
            "Operacao mutavel do MasterTool X '%s' nao passa por "
            "assert_operation_allowed(). Escrita controlada tem porta unica: "
            "assert_controlled_write_allowed() (docs/28, docs/29)." % operation)
    if READ_ONLY_PHASE and operation in WRITE_OPERATIONS:
        raise SafetyError(
            "Operacao de escrita '%s' bloqueada: fase atual e somente "
            "leitura. Conclua e aprove as fases 0-3 antes." % operation)
    return True


def assert_controlled_write_allowed(operation):
    """Porta unica da escrita controlada. Fail-closed em todos os caminhos.

    So devolve True quando as tres coisas valem ao mesmo tempo:

        a fase autorizada esta declarada e e conhecida
        a operacao esta no registro literal de operacoes mutaveis
        a operacao esta na allowlist DESTA fase

    Qualquer outra situacao levanta -- inclusive operacao desconhecida, fase
    desconhecida, fase None, argumento vazio e argumento que nao seja texto.
    Nao ha curinga, prefixo, correspondencia parcial nem default permissivo.
    """
    if not isinstance(operation, _STRING_TYPES) or not operation:
        raise SafetyError(
            "Operacao invalida para escrita controlada: %r. Esperado o nome "
            "exato da API, como texto nao vazio." % (operation,))

    if operation in FORBIDDEN_OPERATIONS:
        raise SafetyError(
            "Operacao '%s' e permanentemente proibida pela politica de "
            "seguranca (config/safety-policy.yaml)." % operation)

    if operation not in MASTERTOOL_MUTATING_OPERATIONS:
        raise SafetyError(
            "Operacao '%s' nao esta no registro literal de operacoes mutaveis "
            "(MASTERTOOL_MUTATING_OPERATIONS). Nome desconhecido falha "
            "fechado: catalogar a API em docs/27 vem antes de usa-la."
            % operation)

    phase = CONTROLLED_WRITE_PHASE
    if not isinstance(phase, _STRING_TYPES) or not phase:
        raise SafetyError(
            "Nenhuma fase de escrita controlada autorizada "
            "(CONTROLLED_WRITE_PHASE = %r). Toda escrita esta bloqueada."
            % (phase,))

    allowed = PHASE_ALLOWED_OPERATIONS.get(phase)
    if not allowed:
        raise SafetyError(
            "Fase de escrita controlada desconhecida ou sem allowlist: %r. "
            "Configuracao incompleta falha fechado." % (phase,))

    if operation not in allowed:
        raise SafetyError(
            "Operacao '%s' nao autorizada na fase '%s'. Autorizadas: %s. "
            "Ampliar a allowlist e decisao humana em commit proprio "
            "(docs/28 secao 14)." % (operation, phase, ", ".join(sorted(allowed))))

    return True


def assert_controlled_property_write_allowed(property_write):
    """A OUTRA porta: atribuicao de propriedade.

    Ate a run-036 este gate so sabia falar de CHAMADA DE METODO, e por isso
    `task.interval = 't#100ms'` nao era recusado -- ele simplesmente nao era
    visto. Uma classe inteira de mutacao passava por baixo do vocabulario:
    nenhum `assert` era chamado, nenhuma allowlist consultada, e a escrita
    acontecia. `docs/48` secao 5 nomeou isso como limite; isto o fecha.

    Porta SEPARADA, e nao um nome a mais no registro de metodos, por duas
    razoes que a mesma funcao apagaria:

      * a verificacao ESTATICA e outra. Chamada guardada e `Call` com a guarda
        na linha imediatamente anterior; atribuicao guardada e `Assign` com
        alvo `Attribute`. Um teste que procura `Call` nunca veria a segunda.
      * o nome pode COLIDIR. `add`, `replace`, `insert` e `remove` sao metodos
        catalogados E nomes plausiveis de propriedade. O prefixo `set:` torna
        a colisao impossivel, e uma allowlist de fase diz sem ambiguidade se
        autorizou o metodo ou o campo.

    Fail-closed nos mesmos cinco caminhos da porta de metodos.
    """
    if not isinstance(property_write, _STRING_TYPES) or not property_write:
        raise SafetyError(
            "Escrita de propriedade invalida: %r. Esperado o nome exato no "
            "formato 'set:<propriedade>', como texto nao vazio."
            % (property_write,))

    if property_write not in MASTERTOOL_PROPERTY_WRITES:
        raise SafetyError(
            "Escrita de propriedade '%s' nao esta no registro literal "
            "(MASTERTOOL_PROPERTY_WRITES). Nome desconhecido falha fechado: "
            "catalogar a propriedade no stub oficial, com linha citada, vem "
            "antes de escreve-la." % (property_write,))

    phase = CONTROLLED_WRITE_PHASE
    if not isinstance(phase, _STRING_TYPES) or not phase:
        raise SafetyError(
            "Nenhuma fase de escrita controlada autorizada "
            "(CONTROLLED_WRITE_PHASE = %r). Toda escrita esta bloqueada."
            % (phase,))

    allowed = PHASE_ALLOWED_OPERATIONS.get(phase)
    if not allowed:
        raise SafetyError(
            "Fase de escrita controlada desconhecida ou sem allowlist: %r. "
            "Configuracao incompleta falha fechado." % (phase,))

    if property_write not in allowed:
        raise SafetyError(
            "Escrita de propriedade '%s' nao autorizada na fase '%s'. "
            "Autorizadas: %s. Ampliar a allowlist e decisao humana em commit "
            "proprio (docs/28 secao 14)."
            % (property_write, phase, ", ".join(sorted(allowed))))

    return True


def controlled_write_summary():
    """Fase e operacoes autorizadas, para manifesto e relatorio de execucao.

    Copia defensiva: quem le o resumo nao pode alterar a allowlist por
    referencia.
    """
    phase = CONTROLLED_WRITE_PHASE
    allowed = PHASE_ALLOWED_OPERATIONS.get(phase) or frozenset()
    return {
        "read_only_phase": READ_ONLY_PHASE,
        "controlled_write_phase": phase,
        "allowed_operations": sorted(allowed),
        "mutating_operations_known": len(MASTERTOOL_MUTATING_OPERATIONS),
        "property_writes_known": len(MASTERTOOL_PROPERTY_WRITES),
    }


def read_only_banner():
    return ("MODO SOMENTE LEITURA: este script nao modifica o projeto, nao "
            "compila, nao realiza download nem qualquer operacao online.")
