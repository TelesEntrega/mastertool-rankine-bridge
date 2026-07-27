FUNCTION_BLOCK FB_Valvula EXTENDS FB_EquipamentoBase
VAR_INPUT
    xAbrir      : BOOL;
    tTimeout    : TIME := T#5S;
END_VAR
VAR_OUTPUT
    xAberta     : BOOL;
    xErro       : BOOL;
END_VAR
VAR_IN_OUT
    stComando   : ST_ComandoValvula;
END_VAR
VAR PERSISTENT
    iPastaAtuadoresExemplo : UDINT;
END_VAR
