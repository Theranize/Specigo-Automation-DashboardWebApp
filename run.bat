@echo off
setlocal

set PYTEST=.\Test\Scripts\pytest.exe
set E2E_PATH=tests/e2e/
set REG_PATH=tests/regression/
set ALL_PATH=tests/

if "%1"=="" goto help

set ENV_OPT=
if not "%2"=="" set ENV_OPT=--env %2

if /I "%1"=="e2e"           ( %PYTEST% %E2E_PATH%  -m "e2e"                   -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="acceptance"    ( %PYTEST% %E2E_PATH%  -m "e2e and acceptance"    -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="rejection"     ( %PYTEST% %E2E_PATH%  -m "e2e and rejection"     -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="rectification" ( %PYTEST% %E2E_PATH%  -m "e2e and rectification" -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="regression"    ( %PYTEST% %REG_PATH%  -m "regression"            -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="smoke"         ( %PYTEST% %ALL_PATH%  -m "smoke"                 -v --tb=short %ENV_OPT% & goto end )
if /I "%1"=="all"           ( %PYTEST% %ALL_PATH%                              -v --tb=short %ENV_OPT% & goto end )

if /I "%1"=="patient" goto do_patient

rem --- pass a specific file or extra args directly ---
%PYTEST% %* -v --tb=short
goto end

:help
echo.
echo  Usage:  run ^<suite^> [env]
echo.
echo  Suites:
echo    e2e             All E2E tests
echo    acceptance      E2E acceptance (happy path)
echo    rejection       E2E rejection / recollection
echo    rectification   E2E rectification flows
echo    regression      All regression tests
echo    smoke           Smoke tests
echo    all             Entire test suite
echo    patient P^<n^>   Run one or more specific patients (P1-P14)
echo.
echo  Env (optional, default = dev):
echo    dev             https://frontenddevh1.specigo.com/
echo    staging         https://staging.specigo.com/
echo.
echo  Examples:
echo    run acceptance              -^> dev (default)
echo    run acceptance staging      -^> staging
echo    run smoke dev               -^> dev (explicit)
echo    run patient P1              -^> P1 on dev
echo    run patient P1 P3 P5        -^> P1, P3, P5 on dev
echo    run patient P1 P3 staging   -^> P1, P3 on staging
echo    run tests/e2e/acceptance/test_e2e_p5_relative_acceptance.py --env staging
echo.

:do_patient
shift
set FILE_LIST=
set ENV_OPT=

:patient_loop
if "%1"=="" goto run_patients
if /I "%1"=="dev"     ( set ENV_OPT=--env dev     & shift & goto run_patients )
if /I "%1"=="staging" ( set ENV_OPT=--env staging & shift & goto run_patients )

if /I "%1"=="P1"  set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_acceptance.py
if /I "%1"=="P2"  set FILE_LIST=%FILE_LIST% tests/e2e/rejection/test_e2e_p2_rejection.py
if /I "%1"=="P3"  set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p3_partial_approve.py
if /I "%1"=="P4"  set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p4_rectification.py
if /I "%1"=="P5"  set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p5_relative_acceptance.py
if /I "%1"=="P6"  set FILE_LIST=%FILE_LIST% tests/e2e/rejection/test_e2e_p6_rejection.py
if /I "%1"=="P7"  set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p7_limit_error.py
if /I "%1"=="P8"  set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p8_new_patient_acceptance.py
if /I "%1"=="P9"  set FILE_LIST=%FILE_LIST% tests/e2e/rejection/test_e2e_p9_new_patient_rejection.py
if /I "%1"=="P10" set FILE_LIST=%FILE_LIST% tests/e2e/rejection/test_e2e_p10_new_patient_partial.py
if /I "%1"=="P11" set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p10_duplicate_mobile_error.py
if /I "%1"=="P12" set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p12_relative_acceptance.py
if /I "%1"=="P13" set FILE_LIST=%FILE_LIST% tests/e2e/rejection/test_e2e_p13_partial_rejection.py
if /I "%1"=="P14" set FILE_LIST=%FILE_LIST% tests/e2e/acceptance/test_e2e_p14_partial_approve.py

shift
goto patient_loop

:run_patients
if "%FILE_LIST%"=="" (
    echo No valid patient IDs provided.
    echo Valid IDs: P1 P2 P3 P4 P5 P6 P7 P8 P9 P10 P11 P12 P13 P14
    goto end
)
%PYTEST% %FILE_LIST% -v --tb=short %ENV_OPT%

:end
endlocal
