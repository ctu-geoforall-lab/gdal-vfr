#!/bin/sh

DATE="20140430"

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
../vfr2${PGM}.py --date $DATE --type OB_564729_UKSH $OPT

# second pass (already exists)
../vfr2${PGM}.py --date $DATE --type OB_564729_UKSH $OPT

# third pass (overwrite)
../vfr2${PGM}.py --date $DATE --type OB_564729_UKSH $OPT

exit 0
