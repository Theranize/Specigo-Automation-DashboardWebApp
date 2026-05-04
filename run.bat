@echo off
setlocal enabledelayedexpansion

set PYTEST=.\Test\Scripts\pytest.exe
set E2E_PATH=tests/e2e/
set REG_PATH=tests/regression/
set ALL_PATH=tests/
set SUPER_PATH=tests/e2e/super_user/test_super_user_e2e.py

if "%1"=="" goto help

set ENV_OPT=
if not "%2"=="" set ENV_OPT=--env %2

rem Optional 3rd positional: parallel worker count (number) or "auto".
rem When set, runs with --dist loadgroup so tests sharing a backend
rem patient mobile (tagged via xdist_group in conftest.py) land on the
rem same worker and serialise — preventing data races on the dev server.
rem Tests with no mobile mapping (regression, smoke) fall back to default
rem load distribution.
set PAR_OPT=
if not "%3"=="" set PAR_OPT=-n %3 --dist loadgroup

if /I "%1"=="e2e"           ( %PYTEST% %E2E_PATH%  -m "e2e"                   -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )
if /I "%1"=="acceptance"    ( %PYTEST% %E2E_PATH%  -m "e2e and acceptance"    -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )
if /I "%1"=="rejection"     ( %PYTEST% %E2E_PATH%  -m "e2e and rejection"     -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )
if /I "%1"=="rectification" ( %PYTEST% %E2E_PATH%  -m "e2e and rectification" -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )
if /I "%1"=="regression"    ( %PYTEST% %REG_PATH%  -m "regression"            -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )
if /I "%1"=="smoke"         ( %PYTEST% %ALL_PATH%  -m "smoke"                 -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )
if /I "%1"=="all"           ( %PYTEST% %ALL_PATH%                              -v --tb=short %ENV_OPT% %PAR_OPT% & goto end )

if /I "%1"=="patient" goto do_patient

if /I "%1"=="admin"   ( set SUPER_AS=admin   & shift & goto do_super )
if /I "%1"=="manager" ( set SUPER_AS=manager & shift & goto do_super )

rem --- pass a specific file or extra args directly ---
%PYTEST% %* -v --tb=short
goto end

:help
echo.
echo  Usage:  run ^<suite^> [env] [N^|auto]
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
echo    admin ^<...^>    Super-user admin run (see Super-User section below)
echo    manager ^<...^>  Super-user manager run (see Super-User section below)
echo.
echo  Env (optional, default = dev):
echo    dev             https://frontenddevh1.specigo.com/
echo    staging         https://staging.specigo.com/
echo.
echo  Parallel (optional, requires env first for suite mode):
echo    N               Run with N parallel workers (e.g. 3, max 14 unique patients)
echo    auto            One worker per logical CPU core
echo    Adds: -n ^<N^> --dist loadgroup
echo.
echo  Super-User (admin/manager) — single-session run across multiple roles:
echo    run ^<admin^|manager^> ^<target^> [scope] [reassign-mode] [env] [N^|auto]
echo.
echo    target        := P1..P14 (one or more) ^| e2e ^| acceptance ^| rejection ^| rectification
echo    scope         := (omitted = super-user owns everything)
echo                  ^| till ^<stage^>
echo                  ^| till ^<stage^> continue
echo                  ^| till ^<stage^> continue till ^<stage^>
echo    reassign-mode := +reassign-admin ^| +reassign-users
echo    stage         := fd ^| phlebo ^| acc ^| labt ^| doc
echo.
echo  Examples:
echo    run acceptance                  -^> sequential, dev (default)
echo    run acceptance staging          -^> sequential, staging
echo    run acceptance dev 3            -^> 3 workers, dev
echo    run acceptance staging auto     -^> auto workers, staging
echo    run e2e dev 4                   -^> 4 workers, all e2e on dev
echo    run patient P1                  -^> sequential, P1 on dev
echo    run patient P1 P3 P5            -^> sequential, P1/P3/P5 on dev
echo    run patient P1 P3 P5 3          -^> 3 workers, those patients on dev
echo    run patient P1 P3 P5 3 staging  -^> 3 workers, those patients on staging
echo    run patient P1 P3 staging       -^> sequential, P1/P3 on staging
echo    run admin P1                    -^> admin owns all P1 phases (single login)
echo    run admin P1 till acc continue  -^> admin runs FD/Phlebo/Acc, per-role finish
echo    run admin P2 till acc continue till doc            -^> admin to acc, per-role to doc
echo    run admin P2 till acc continue till doc +reassign-admin
echo    run admin P2 +reassign-users    -^> admin owns all except reassign/recollect
echo    run admin e2e staging 3         -^> all 14 patients, super-user-everything, staging, 3 workers
echo    run manager P5 P8 till doc continue staging 2
echo    run tests/e2e/acceptance/test_e2e_p5_relative_acceptance.py --env staging
echo.
goto end

:do_patient
rem Patients now live in two parametrized files (acceptance + rejection).
rem Build a -k filter from accumulated patient IDs (e.g. "P1 or P3 or P5") and
rem always pass both files; pytest deselects parametrize ids that don't match.
shift
set PIDS=
set ENV_OPT=
set PAR_OPT=

:patient_loop
if "%1"=="" goto run_patients

rem env tokens terminate parsing (preserve existing convention)
if /I "%1"=="dev"     ( set ENV_OPT=--env dev     & shift & goto run_patients )
if /I "%1"=="staging" ( set ENV_OPT=--env staging & shift & goto run_patients )

rem parallel: "auto" or any all-digit token
if /I "%1"=="auto" ( set PAR_OPT=-n auto --dist loadgroup & shift & goto patient_loop )
set _TOK=%1
set _NONDIGIT=
for /f "delims=0123456789" %%c in ("!_TOK!") do set _NONDIGIT=%%c
if "!_NONDIGIT!"=="" if not "!_TOK!"=="" ( set PAR_OPT=-n !_TOK! --dist loadgroup & shift & goto patient_loop )

if /I "%1"=="P1"  set PIDS=!PIDS! P1
if /I "%1"=="P2"  set PIDS=!PIDS! P2
if /I "%1"=="P3"  set PIDS=!PIDS! P3
if /I "%1"=="P4"  set PIDS=!PIDS! P4
if /I "%1"=="P5"  set PIDS=!PIDS! P5
if /I "%1"=="P6"  set PIDS=!PIDS! P6
if /I "%1"=="P7"  set PIDS=!PIDS! P7
if /I "%1"=="P8"  set PIDS=!PIDS! P8
if /I "%1"=="P9"  set PIDS=!PIDS! P9
if /I "%1"=="P10" set PIDS=!PIDS! P10
if /I "%1"=="P11" set PIDS=!PIDS! P11
if /I "%1"=="P12" set PIDS=!PIDS! P12
if /I "%1"=="P13" set PIDS=!PIDS! P13
if /I "%1"=="P14" set PIDS=!PIDS! P14

shift
goto patient_loop

:run_patients
if "!PIDS!"=="" (
    echo No valid patient IDs provided.
    echo Valid IDs: P1 P2 P3 P4 P5 P6 P7 P8 P9 P10 P11 P12 P13 P14
    goto end
)
rem Build "[P1] or [P3] or [P5]" — bracketed so "P1" doesn't substring-match P11/P12/P14.
set K_FILTER=
for %%p in (!PIDS!) do (
    if "!K_FILTER!"=="" ( set K_FILTER=[%%p] ) else ( set K_FILTER=!K_FILTER! or [%%p] )
)
%PYTEST% tests/e2e/acceptance/test_e2e_acceptance.py tests/e2e/rejection/test_e2e_rejection.py -k "!K_FILTER!" -v --tb=short %ENV_OPT% %PAR_OPT%
goto end

rem ─── Super-user (admin/manager) parser ─────────────────────────────────────
rem Token grammar (consumed in any order until exhausted):
rem   P1..P14                                — accumulate into TARGETS
rem   e2e | acceptance | rejection | rectification — expand to canonical P-list
rem   till <stage>                           — first occurrence => SUPER_UNTIL
rem                                            second occurrence => SUPER_CONT_TILL (and SUPER_CONT)
rem   continue                               — sets SUPER_CONT
rem   +reassign-admin | +reassign-users      — sets SUPER_REASSIGN
rem   dev | staging                          — sets ENV_OPT
rem   auto | <digits>                        — sets PAR_OPT
:do_super
set TARGETS=
set ENV_OPT=
set PAR_OPT=
set SUPER_UNTIL=
set SUPER_CONT=
set SUPER_CONT_TILL=
set SUPER_REASSIGN=
set _TILL_SEEN=

:super_loop
if "%1"=="" goto run_super

if /I "%1"=="dev"     ( set ENV_OPT=--env dev     & shift & goto super_loop )
if /I "%1"=="staging" ( set ENV_OPT=--env staging & shift & goto super_loop )

if /I "%1"=="auto" ( set PAR_OPT=-n auto --dist loadgroup & shift & goto super_loop )
set _TOK=%1
set _NONDIGIT=
for /f "delims=0123456789" %%c in ("!_TOK!") do set _NONDIGIT=%%c
if "!_NONDIGIT!"=="" if not "!_TOK!"=="" ( set PAR_OPT=-n !_TOK! --dist loadgroup & shift & goto super_loop )

if /I "%1"=="till" (
    if "!_TILL_SEEN!"=="" (
        set SUPER_UNTIL=%2
        set _TILL_SEEN=1
    ) else (
        set SUPER_CONT_TILL=%2
        set SUPER_CONT=1
    )
    shift & shift & goto super_loop
)
if /I "%1"=="continue"          ( set SUPER_CONT=1                 & shift & goto super_loop )
if /I "%1"=="+reassign-admin"   ( set SUPER_REASSIGN=super         & shift & goto super_loop )
if /I "%1"=="+reassign-users"   ( set SUPER_REASSIGN=users         & shift & goto super_loop )

if /I "%1"=="e2e"           ( set TARGETS=!TARGETS!,P1,P2,P3,P4,P5,P6,P7,P8,P9,P10,P11,P12,P13,P14 & shift & goto super_loop )
if /I "%1"=="acceptance"    ( set TARGETS=!TARGETS!,P1,P3,P4,P5,P7,P8,P11,P12,P14                  & shift & goto super_loop )
if /I "%1"=="rejection"     ( set TARGETS=!TARGETS!,P2,P6,P9,P10,P13                                & shift & goto super_loop )
if /I "%1"=="rectification" ( set TARGETS=!TARGETS!,P4,P10,P12                                      & shift & goto super_loop )

if /I "%1"=="P1"  ( set TARGETS=!TARGETS!,P1  & shift & goto super_loop )
if /I "%1"=="P2"  ( set TARGETS=!TARGETS!,P2  & shift & goto super_loop )
if /I "%1"=="P3"  ( set TARGETS=!TARGETS!,P3  & shift & goto super_loop )
if /I "%1"=="P4"  ( set TARGETS=!TARGETS!,P4  & shift & goto super_loop )
if /I "%1"=="P5"  ( set TARGETS=!TARGETS!,P5  & shift & goto super_loop )
if /I "%1"=="P6"  ( set TARGETS=!TARGETS!,P6  & shift & goto super_loop )
if /I "%1"=="P7"  ( set TARGETS=!TARGETS!,P7  & shift & goto super_loop )
if /I "%1"=="P8"  ( set TARGETS=!TARGETS!,P8  & shift & goto super_loop )
if /I "%1"=="P9"  ( set TARGETS=!TARGETS!,P9  & shift & goto super_loop )
if /I "%1"=="P10" ( set TARGETS=!TARGETS!,P10 & shift & goto super_loop )
if /I "%1"=="P11" ( set TARGETS=!TARGETS!,P11 & shift & goto super_loop )
if /I "%1"=="P12" ( set TARGETS=!TARGETS!,P12 & shift & goto super_loop )
if /I "%1"=="P13" ( set TARGETS=!TARGETS!,P13 & shift & goto super_loop )
if /I "%1"=="P14" ( set TARGETS=!TARGETS!,P14 & shift & goto super_loop )

echo Unrecognized super-user token: %1
shift
goto super_loop

:run_super
if "!TARGETS!"=="" (
    echo No super-user targets provided.
    echo Valid: P1..P14, or suite tokens e2e^|acceptance^|rejection^|rectification.
    goto end
)
rem strip leading comma
set TARGETS=!TARGETS:~1!

set SUPER_OPTS=--super-as %SUPER_AS% --super-targets !TARGETS!
if not "!SUPER_UNTIL!"==""      set SUPER_OPTS=!SUPER_OPTS! --super-until !SUPER_UNTIL!
if "!SUPER_CONT!"=="1"          set SUPER_OPTS=!SUPER_OPTS! --super-continue
if not "!SUPER_CONT_TILL!"==""  set SUPER_OPTS=!SUPER_OPTS! --super-continue-till !SUPER_CONT_TILL!
if not "!SUPER_REASSIGN!"==""   set SUPER_OPTS=!SUPER_OPTS! --super-reassign !SUPER_REASSIGN!

%PYTEST% %SUPER_PATH% -v --tb=short %ENV_OPT% %PAR_OPT% !SUPER_OPTS!

:end
endlocal
