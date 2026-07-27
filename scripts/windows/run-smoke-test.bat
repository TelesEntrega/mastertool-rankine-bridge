@echo off
rem Os scripts IronPython rodam DENTRO do MasterTool, nao pelo cmd.
rem Este .bat apenas orienta e abre a pasta correta.
echo ============================================================
echo  SMOKE TEST - executar DENTRO do MasterTool IEC XE 3.63
echo ============================================================
echo  1. Abra o MasterTool com um projeto carregado.
echo  2. Menu de scripting (Ferramentas ^> Scripting ^> Executar script).
echo  3. Selecione: %~dp0..\mastertool\00_smoke_test.py
echo  4. Confira a saida no painel de mensagens e em workspace\logs\.
echo ============================================================
explorer "%~dp0..\mastertool"
pause
