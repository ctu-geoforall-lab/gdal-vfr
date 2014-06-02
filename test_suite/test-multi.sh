#!/bin/sh

DB=vfr

# single file 
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
../vfr2${PGM}.py --file seznam.txt $OPT

# second pass (already exists)
echo "Second pass (already exists...)"
../vfr2${PGM}.py --file seznam.txt $OPT

# third pass (overwrite)
echo "Third pass (overwrite...)"
../vfr2${PGM}.py --file seznam.txt $OPT --o

# fourth pass (append)
echo "Forth pass (append...)"
../vfr2${PGM}.py --type OB_554979_UKSH $OPT --a

if [ "$PGM" = "pg" ] ; then
    echo "Fourth pass (schema per file...)"
    ../vfr2${PGM}.py --file seznam.txt $OPT -s --o
fi

if [ "$PGM" = "ogr" ] ; then
    rm ${DB}.db
fi

exit 0
