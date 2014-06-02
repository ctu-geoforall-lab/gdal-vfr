@echo off

set DB=vfr
set USER=postgres

set DATE=20140430
set PGM=pg
set CONN=--username %USER%
set OPT=--dbname %DB% --user %USER%

set PATH=C:\Program Files (x86)\PostgreSQL\9.3\bin;%PATH%
psql -d %DB% -f cleandb.sql %CONN% 2>nul

echo "Using vfr2%PGM%..."

REM first pass (empty DB)
echo "First pass (empty DB...)"
call vfr2%PGM% --file seznam.txt %OPT%

REM second pass (already exists)
echo "Second pass (already exists...)"
call vfr2%PGM% --file seznam.txt %OPT%

REM third pass (overwrite)
echo "Third pass (overwrite...)"
call vfr2%PGM% --file seznam.txt %OPT% --o

echo "Forth pass (append...)"
call vfr2%PGM% --type OB_554979_UKSH %OPT% --a

echo "Fifth pass (schema per file...)"
call vfr2%PGM% --file seznam.txt %OPT% -s
