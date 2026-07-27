VAR_GLOBAL
    xLigaMotor      : BOOL;
    xMotorLigado    : BOOL;
    rVelocidade     : REAL := 0.0;
    aiPressoes      : ARRAY[0..9] OF INT;
    xValvulaSaida AT %QX0.0 : BOOL;
END_VAR
VAR_GLOBAL RETAIN
    iContadorCiclos : DINT;
END_VAR
