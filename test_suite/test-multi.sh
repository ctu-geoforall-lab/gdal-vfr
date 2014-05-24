#!/bin/sh

DB=vfr

# single file 
if test -z "$1" ; then
    PGM="pg"
    OPT="--dbname $DB"
else
    if [ "$1" = "ogr" ] ; then
        PGM="ogr"
        OPT="--format PostgreSQL --dsn PG:dbname=$DB"
    else
        PGM="oci"
        OPT="--user test --passwd test"
    fi
fi

if [ "PGM" != "oci" ] ; then
    psql -d $DB -f cleandb.sql 2>/dev/null
fi

echo "Using vfr2${PGM}..."

# first pass (empty DB)
echo "First pass (empty DB...)"
../vfr2${PGM}.py --file seznam.txt $OPT

# second pass (already exists)
echo "Second pass (already exists...)"
../vfr2${PGM}.py --file seznam.txt $OPT

# third pass (overwrite)
echo "Third pass (overwrite...)"
../vfr2${PGM}.py --file seznam.txt $OPT --o

if [ "$PGM" = "pg" ] ; then
    echo "Fourth pass (schema per file...)"
    ../vfr2${PGM}.py --file seznam.txt $OPT -s
fi

exit 0
