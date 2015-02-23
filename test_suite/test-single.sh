#!/bin/sh

DB=ruian_test

# single file 
if test -z "$1" ; then
    PGM=pg
    OPT="--dbname $DB"

    psql -d $DB -f cleandb.sql 2>/dev/null
else
    if [ "$1" = "ogr" ] ; then
        PGM=ogr
        OPT="--format SQLite --dsn ${DB}.db"

        rm -f ${DB}.db
    else
        PGM=oci
        OPT="--user test --passwd test"
    fi
fi

echo "Using vfr2${PGM}..."

echo "1st PASS (empty DB...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT

echo "2nd PASS (already exists...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT

echo "3rd PASS (overwrite...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT --o

echo "4th PASS (append...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT --a

echo "5th PASS (geom_name...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT --o --geom OriginalniHranice

if [ "$PGM" = "pg" ] ; then
    echo "6th PASS (schema per file...)"
    ../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT -s
fi

exit 0
