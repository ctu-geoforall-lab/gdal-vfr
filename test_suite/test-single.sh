#!/bin/sh

# single file 
if test -z "$1" ; then
    PGM="pg"
    OPT="--dbname vfr"
else
    if [ "$1" = "ogr" ] ; then
        PGM="ogr"
        OPT="--format PostgreSQL --dsn PG:dbname=vfr"
    else
        PGM="oci"
        OPT="--user test --passwd test"
    fi
fi

if [ "PGM" != "oci" ] ; then
    dropdb vfr; createdb vfr && psql vfr -c"create extension postgis"
fi

echo "Using vfr2${PGM}..."

# first pass (empty DB)
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT

# second pass (already exists)
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT

# third pass (overwrite)
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT --o

exit 0
