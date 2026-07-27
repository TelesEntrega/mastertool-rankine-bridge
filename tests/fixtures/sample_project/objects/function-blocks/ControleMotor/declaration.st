FUNCTION_BLOCK ControleMotor
VAR_INPUT
    xLiga       : BOOL;             // comando de partida
    xDesliga    : BOOL;
    rSetpoint   : REAL := 10.0;
END_VAR
VAR_OUTPUT
    xMotor      : BOOL;
    xFalha      : BOOL;
END_VAR
VAR
    tonPartida  : TON;
    iEstado     : INT;
END_VAR
