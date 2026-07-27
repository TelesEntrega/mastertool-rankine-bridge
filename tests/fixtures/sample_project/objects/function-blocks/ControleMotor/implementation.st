(* Maquina de estados simples de partida do motor *)
CASE iEstado OF
    0: (* parado *)
        IF xLiga AND NOT xDesliga THEN
            iEstado := 1;
        END_IF
    1: (* temporizacao de partida *)
        tonPartida(IN := TRUE, PT := T#2S);
        IF tonPartida.Q THEN
            xMotor := TRUE;
            iEstado := 2;
        END_IF
    2: (* rodando *)
        IF xDesliga THEN
            xMotor := FALSE;
            tonPartida(IN := FALSE);
            iEstado := 0;
        END_IF
END_CASE
