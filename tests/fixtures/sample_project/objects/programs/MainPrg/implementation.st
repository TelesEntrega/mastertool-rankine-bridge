// Programa principal (fixture sintetica de teste)
fbMotor(xLiga := xLigaMotor, xDesliga := FALSE);
xMotorLigado := fbMotor.xMotor;

IF xMotorLigado THEN
    rVelocidade := rVelocidade + 1.0;
END_IF

FOR i := 0 TO aiPressoes[0] DO
    aiPressoes[i] := 0;
END_FOR

%QX0.1 := xMotorLigado;
