#!/bin/sh

DB=vfr

if test -z "$1" ; then
    PGM=pg
    OPT="--dbname $DB"

    psql -d $DB -f cleandb.sql 2>/dev/null
else
    if [ "$1" = "ogr" ] ; then
        PGM=ogr
        OPT="--format SQLite --dsn ${DB}.db"
    else
        PGM=oci
        OPT="--user test --passwd test"
    fi
fi

echo "Using vfr2${PGM}..."

# first pass (empty DB)
echo "First pass (empty DB...)"
../vfr2${PGM}.py --type OB_564729_UKSH $OPT

# second pass (already exists)
echo "Second pass (already exists...)"
../vfr2${PGM}.py --type OB_564729_UKSH $OPT

# third pass (overwrite)
echo "Third pass (overwrite...)"
../vfr2${PGM}.py --type OB_564729_UKSH $OPT --o

# fourth path (append)
echo "Forth pass (append...)"
../vfr2${PGM}.py --type OB_554979_UKSH $OPT --a

if [ "$PGM" = "pg" ] ; then
    echo "Fourth pass (schema per file...)"
    ../vfr2${PGM}.py --type OB_564729_UKSH $OPT --schema vfr_xxxxxxx_ob_564729_uksh
fi

if [ "$PGM" = "ogr" ] ; then
    rm ${DB}.db
fi

exit 0
