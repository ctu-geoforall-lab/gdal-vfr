#!/bin/sh

SCRIPT=`realpath $0` # realpath is a separate package and doesn't need
                     # to be installed
if [ -z $SCRIPT ] ; then
    SCRIPTPATH='.'
else
    SCRIPTPATH=`dirname $SCRIPT`
fi

DB=ruian_test

if test -z "$1" ; then
    PGM=pg
    OPT="--dbname $DB"

    psql -d $DB -f $SCRIPTPATH/cleandb.sql 2>/dev/null
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
$SCRIPTPATH/../vfr2${PGM}.py --type $SCRIPTPATH/OB_564729_UKSH $OPT

echo "2d PASS (already exists...)"
$SCRIPTPATH/../vfr2${PGM}.py --type $SCRIPTPATH/OB_564729_UKSH $OPT

echo "3d PASS (overwrite...)"
$SCRIPTPATH/../vfr2${PGM}.py --type $SCRIPTPATH/OB_564729_UKSH $OPT --o

echo "4th PASS (append...)"
$SCRIPTPATH/../vfr2${PGM}.py --type $SCRIPTPATH/OB_554979_UKSH $OPT --a

echo "5th PASS (geom_name...)"
$SCRIPTPATH/../vfr2${PGM}.py --type $SCRIPTPATH/OB_564729_UKSH $OPT --o --geom OriginalniHranice

if [ "$PGM" = "pg" ] ; then
    echo "6th PASS (schema per file...)"
    $SCRIPTPATH/../vfr2${PGM}.py --type $SCRIPTPATH/OB_564729_UKSH $OPT --schema vfr_xxxxxxx_ob_564729_uksh
fi

exit 0
