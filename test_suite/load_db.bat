@echo off

set DB=ruian
set FILE=db_uksh.txt
set USER=postgres
set LOG=log.txt
set LOG_ERR=log_err.txt

vfr2pg --file %FILE% --dbname %DB% --user %USER% --o >%LOG% 2>%LOG_ERR%
