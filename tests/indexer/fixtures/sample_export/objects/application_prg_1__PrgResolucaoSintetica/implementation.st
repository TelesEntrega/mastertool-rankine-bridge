MT01 := TRUE;

GvlDiagnosticoSintetico.DG_Contador := 1;

IF GA_ValorSintetico > 0 THEN
    xPulso := TRUE;
END_IF;

IF DG_Contador > 0 THEN
    xPulso := TRUE;
END_IF;

fbTimer(
    xStart := xPulso,
    tPreset := tTempoAjustado,
    xDone => xPulso
);

fbTimer.Reset();
