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
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT

# second pass (already exists)
echo "Second pass (already exists...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT

# third pass (overwrite)
echo "Third pass (overwrite...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT --o

# fourth pass (append)
echo "Forth pass (append...)"
../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT --a

if [ "$PGM" = "pg" ] ; then
    echo "Fifth pass (schema per file...)"
    ../vfr2${PGM}.py --file OB_UKSH.xml.gz $OPT -s
fi

exit 0
