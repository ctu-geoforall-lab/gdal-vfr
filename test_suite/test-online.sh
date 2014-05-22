#!/bin/sh

DATE="20140430"

# single file 
dropdb vfr; createdb vfr && psql vfr -c"create extension postgis"

# first pass (empty DB)
../vfr2pg.py --date $DATE --type OB_564729_UKSH --dbname vfr

# second pass (already exists)
../vfr2pg.py --date $DATE --type OB_564729_UKSH --dbname vfr

# third pass (overwrite)
../vfr2pg.py --date $DATE --type OB_564729_UKSH --dbname vfr --o

exit 0
