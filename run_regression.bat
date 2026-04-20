@echo off
setlocal

set PYTEST=.\Test\Scripts\pytest.exe
set REG_PATH=tests/regression/

if "%1"=="" goto help

set ENV_OPT=
if not "%2"=="" set ENV_OPT=--env %2

if /I "%1"=="frontdesk"    ( %PYTEST% %REG_PATH%test_front_desk_regression.py    -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="fd"           ( %PYTEST% %REG_PATH%test_front_desk_regression.py    -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="phlebotomist" ( %PYTEST% %REG_PATH%test_phlebotomist_regression.py  -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="phlebo"       ( %PYTEST% %REG_PATH%test_phlebotomist_regression.py  -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="accession"    ( %PYTEST% %REG_PATH%test_accession_regression.py     -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="labtech"      ( %PYTEST% %REG_PATH%test_labtech_regression.py       -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="lt"           ( %PYTEST% %REG_PATH%test_labtech_regression.py       -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="doctor"       ( %PYTEST% %REG_PATH%test_doctor_regression.py        -v --tb=short %ENV_OPT% & goto end )

:help
echo.
echo  Usage:  run_regression ^<role^> [env]
echo.
echo  Roles:
echo    frontdesk    (alias: fd)      Front Desk registration regression
echo    phlebotomist (alias: phlebo)  Phlebotomist sample toggle regression
echo    accession                     Accession sample verification regression
echo    labtech      (alias: lt)      Lab Technician report entry regression
echo    doctor                        Doctor report review regression
echo.
echo  Env (optional, default = dev):
echo    dev             https://frontenddevh1.specigo.com/
echo    staging         https://staging.specigo.com/
echo.
echo  Examples:
echo    run_regression fd
echo    run_regression doctor staging
echo    run_regression labtech dev
echo.

:end
endlocal
