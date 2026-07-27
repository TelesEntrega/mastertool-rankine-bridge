rResultado := (rValorA + rValorB) / 2;

IF rResultado > 100.0 THEN
    rResultado := 100.0;
ELSIF rResultado < 0.0 THEN
    rResultado := 0.0;
ELSE
    FbLimitador.Ajustar(
        IN_VALOR := rResultado,
        OUT_VALOR => rResultado
    );
END_IF;

FunCalcularMedia := rResultado;
