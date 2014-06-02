@echo off

set DB=vfr

IF "%1"=="ogr" (
   set PGM=%1
   set OPT=--format SQLite --dsn=%DB%.db
) ELSE (
   set PGM=pg
   set OPT=--dbname %DB% --user %USER%
   set USER=postgres
   set CONN=--username %USER%

   set PATH=C:\Program Files (x86)\PostgreSQL\9.3\bin;%PATH%
   psql -d %DB% -f cleandb.sql %CONN% 2>nul
)

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

REM fourth pass (append)
echo "Forth pass (append...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% --a

if %PGM%==pg (
   REM fifth pass (schema per file)
   echo "Fifth pass (schema per file...)"
   call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% -s
)

if %PGM%==ogr (
   del "%DB%.db"
)
