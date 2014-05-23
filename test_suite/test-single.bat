@echo off

set PGM=pg
set CONN=--username test -W
set OPT=--dbname vfr --user test --passwd test
set DB=vfr

set PATH=C:\Program Files (x86)\PostgreSQL\9.3\bin;%PATH%
dropdb %CONN% %DB%
createdb %CONN% %DB%
psql -d %DB% -c"create extension postgis" %CONN%

echo "Using vfr2%PGM%..."

REM first pass (empty DB)
echo "First pass (empty DB...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT%

REM second pass (already exists)
echo "Second pass (already exists...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT%

REM third pass (overwrite)
echo "Third pass (overwrite...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% --o

echo "Fourth pass (schema per file...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% -s
