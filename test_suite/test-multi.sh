#!/bin/sh

# single file 
dropdb vfr; createdb vfr && psql vfr -c"create extension postgis"

# first pass (empty DB)
../vfr2pg.py --file seznam.txt --dbname vfr

# second pass (already exists)
../vfr2pg.py --file seznam.txt --dbname vfr

# third pass (overwrite)
../vfr2pg.py --file seznam.txt --dbname vfr --o

exit 0
