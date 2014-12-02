@echo off

set DB=ruian
set DIR=c:\vfr_files
set FILE=%osgeo4w_root%\bin\test_suite\db_uksh.txt
set USER=postgres
set LOG=log.txt
set LOG_ERR=log_err.txt

if not exist "%DIR%" mkdir %DIR%
cd %DIR%
vfr2pg --file %FILE% --dbname %DB% --user %USER% --o >%LOG% 2>%LOG_ERR%
