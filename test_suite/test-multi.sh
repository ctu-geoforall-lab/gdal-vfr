#!/bin/sh
set -e

SCRIPT=`realpath $0` # realpath is a separate package and doesn't need
                     # to be installed
if [ -z $SCRIPT ] ; then
    SCRIPTPATH='.'
else
    SCRIPTPATH=`dirname $SCRIPT`
fi

DB=ruian_test
export DATA_DIR=$SCRIPTPATH
export LOG_FILE=${SCRIPT}.log
rm -f $LOG

# single file 
if test -z "$1" ; then
    PGM=pg
    OPT="--dbname $DB"

    psql -d $DB -f $SCRIPTPATH/cleandb.sql
else
    PGM=ogr
    OPT="--format SQLite --dsn ${DB}.db"

    rm -f ${DB}.db
fi

echo "Using vfr2${PGM}..."

echo "1st PASS (empty DB...)"
$SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/seznam.txt $OPT

echo "2nd PASS (already exists...)"
$SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/seznam.txt $OPT

echo "3rd PASS (overwrite...)"
$SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/seznam.txt $OPT --o

echo "4th PASS (append...)"
$SCRIPTPATH/../vfr2${PGM}.py --type OB_554979_UKSH $OPT --a

echo "5th PASS (geom_name...)"
$SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/seznam.txt $OPT --o --geom OriginalniHranice

if [ "$PGM" = "pg" ] ; then
    echo "6th PASS (schema per file...)"
    $SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/seznam.txt $OPT -s --o
fi

exit 0
