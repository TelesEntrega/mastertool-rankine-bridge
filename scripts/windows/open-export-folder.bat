@echo off
if not exist "%~dp0..\..\workspace\exports" mkdir "%~dp0..\..\workspace\exports"
explorer "%~dp0..\..\workspace\exports"
