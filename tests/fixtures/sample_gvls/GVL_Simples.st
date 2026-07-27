(* GVL sintetica para testes de parser *)
VAR_GLOBAL CONSTANT
    MAX_EIXOS : INT := 4;
END_VAR
VAR_GLOBAL
    xEmergencia : BOOL;
    arEixos     : ARRAY[1..MAX_EIXOS] OF REAL;
END_VAR
