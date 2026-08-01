@echo off
echo ============================================================
echo  DISCOVERY - executar DENTRO do MasterTool IEC XE 3.63
echo ============================================================
echo  Execute, nesta ordem, pelo menu de scripting do MasterTool:
echo    1. %~dp0..\mastertool\01_discover_environment.py
echo    2. %~dp0..\mastertool\02_dump_api_surface.py
echo    3. %~dp0..\mastertool\03_list_project_tree.py
echo  Saidas em: workspace\exports\^<timestamp^>\
echo ============================================================
explorer "%~dp0..\mastertool"
pause
