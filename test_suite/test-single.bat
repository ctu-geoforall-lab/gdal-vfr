@echo off

set DB=ruian_test
set PATH=C:\Program Files (x86)\PostgreSQL\9.3\bin;%PATH%

IF "%1"=="ogr" (
   set PGM=%1
   set OPT=--format SQLite --dsn=%DB%.db

   del "%DB%.db"
) ELSE (
   set PGM=pg
   set OPT=--dbname %DB% --user %USER%
   set USER=postgres
   set CONN=--username %USER%
   
   psql -d %DB% -f cleandb.sql %CONN% 2>nul
)

echo "Using vfr2%PGM%..."

echo "1st PASS (empty DB...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT%

echo "2nd PASS (already exists...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT%

echo "3rd PASS (overwrite...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% --o

echo "4th PASS (append...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% --a

echo "5th PASS (geom_name...)"
call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% --o --geom OriginalniHranice

if %PGM%==pg (
   echo "6th PASS (schema per file...)"
   call vfr2%PGM% --file OB_UKSH.xml.gz %OPT% -s
)
