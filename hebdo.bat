@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Routine du vendredi : optimiseur puis semaine ===
echo.
set /p D=Date de l'export (AAAAMMJJ, ex. 20261204) : 
set COURS=data_brute\cours_quotidiens_%D%.csv
set DIVS=data_brute\dividendes_%D%.csv
set POIDS=data_brute\poids_cibles_%D%.csv
set INDICE=data_brute\indice_secteurs_20261031.csv
if not exist "%COURS%" (
  echo Fichier introuvable : %COURS%
  pause
  exit /b 1
)
echo.
echo --- 1. Optimiseur ---
py -3.13 scripts\optimiseur.py %INDICE% %COURS% data_brute\scores.csv %POIDS%
if errorlevel 1 (
  echo L'optimiseur a echoue : rien n'a ete modifie.
  pause
  exit /b 1
)
echo.
echo Verifie : ecart de suivi proche de 3,5 %%, 30 a 35 lignes, "depassements": [] vide.
set /p OK=On reequilibre le portefeuille avec ces poids ? (O/N) : 
if /i not "%OK%"=="O" (
  echo Arret. Les poids sont dans %POIDS%, le portefeuille n'a pas bouge.
  pause
  exit /b 0
)
echo.
echo --- 2. Semaine ---
if exist "%DIVS%" (
  py -3.13 scripts\run_hebdo.py semaine %COURS% %INDICE% dividendes=%DIVS% poids=%POIDS%
) else (
  echo Pas de fichier %DIVS% : semaine sans dividendes.
  py -3.13 scripts\run_hebdo.py semaine %COURS% %INDICE% poids=%POIDS%
)
if errorlevel 1 (
  echo La mise a jour de la semaine a echoue.
  pause
  exit /b 1
)
echo.
echo --- 3. Apercu du site : http://localhost:8000 (Ctrl+C pour arreter) ---
echo Ensuite : GitHub Desktop, Commit puis Push.
py -3.13 -m http.server -d docs 8000
