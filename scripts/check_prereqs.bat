@echo off
setlocal EnableExtensions

set "STATUS=0"

call :require jcmd
call :require jmap
call :require jstat
call :require jfr

set "MAT_OK=0"
if defined MAT_BIN (
  if exist "%MAT_BIN%" (
    set "MAT_OK=1"
  )
)

if "%MAT_OK%"=="0" (
  where ParseHeapDump.bat >nul 2>nul && set "MAT_OK=1"
)
if "%MAT_OK%"=="0" (
  where mat >nul 2>nul && set "MAT_OK=1"
)
if "%MAT_OK%"=="0" (
  where ParseHeapDump.sh >nul 2>nul && set "MAT_OK=1"
)

if "%MAT_OK%"=="1" (
  echo OK: MAT CLI
) else (
  echo MISSING: Eclipse MAT CLI ^(ParseHeapDump.sh, ParseHeapDump.bat, or mat^)
  set "STATUS=1"
)

set "ASYNC_OK=0"
if defined ASYNC_PROFILER_BIN (
  if exist "%ASYNC_PROFILER_BIN%" (
    set "ASYNC_OK=1"
  )
)
if "%ASYNC_OK%"=="0" (
  where async-profiler >nul 2>nul && set "ASYNC_OK=1"
)
if "%ASYNC_OK%"=="0" (
  where profiler.sh >nul 2>nul && set "ASYNC_OK=1"
)
if "%ASYNC_OK%"=="0" (
  where asprof >nul 2>nul && set "ASYNC_OK=1"
)

if "%ASYNC_OK%"=="1" (
  echo OK: async-profiler
) else (
  echo WARN: async-profiler missing ^(optional; deep mode falls back to JFR + MAT^)
)

exit /b %STATUS%

:require
where %~1 >nul 2>nul
if errorlevel 1 (
  echo MISSING: %~1
  set "STATUS=1"
) else (
  for /f "delims=" %%P in ('where %~1 2^>nul') do (
    echo OK: %~1 -^> %%P
    goto :eof
  )
)

goto :eof
