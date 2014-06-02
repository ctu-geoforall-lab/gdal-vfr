@echo off

set DB=vfr
set USER=postgres
set CONN=--username %USER%

IF "%1"=="ogr" (
   set PGM=%1
   set OPT=--format PostgreSQL --dsn="PG:dbname=%DB% user=%USER%"
) ELSE (
   set PGM=pg
   set OPT=--dbname %DB% --user %USER%
)

set PATH=C:\Program Files (x86)\PostgreSQL\9.3\bin;%PATH%
psql -d %DB% -f cleandb.sql %CONN% 2>nul

echo "Using vfr2%PGM%..."

REM first pass (empty DB)
echo "First pass (empty DB...)"
call vfr2%PGM% --type OB_564729_UKSH %OPT%

REM second pass (already exists)
echo "Second pass (already exists...)"
call vfr2%PGM% --type OB_564729_UKSH %OPT%

REM third pass (overwrite)
echo "Third pass (overwrite...)"
call vfr2%PGM% --type OB_564729_UKSH %OPT% --o

REM fourth pass (append)
echo "Forth pass (append...)"
call vfr2%PGM% --type OB_554979_UKSH %OPT% --a

if %PGM%==pg (
   REM fifth pass (schema per file)
   echo "Fifth pass (schema per file...)"
   call vfr2%PGM% --type OB_564729_UKSH %OPT% -s
)