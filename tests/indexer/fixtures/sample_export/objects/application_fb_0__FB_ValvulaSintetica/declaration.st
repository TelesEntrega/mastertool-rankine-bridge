FUNCTION_BLOCK FB_ValvulaSintetica
VAR_INPUT
    xComandoAbrir   : BOOL;
    tTempoLimite    : TIME := T#2S;
END_VAR
VAR_OUTPUT
    xValvulaAberta  : BOOL;
    xFalhaValvula   : BOOL;
END_VAR
VAR
    tonMonitorAbre  : TON;
END_VAR
VAR CONSTANT
    iMaxTentativas  : INT := 3;
END_VAR
