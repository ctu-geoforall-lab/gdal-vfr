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
$SCRIPTPATH/../vfr2${PGM}.py --type OB_564729_UKSH $OPT

echo "2d PASS (already exists...)"
$SCRIPTPATH/../vfr2${PGM}.py --type OB_564729_UKSH $OPT

echo "3d PASS (overwrite...)"
$SCRIPTPATH/../vfr2${PGM}.py --type OB_564729_UKSH $OPT --o

echo "4th PASS (append...)"
$SCRIPTPATH/../vfr2${PGM}.py --type OB_554979_UKSH $OPT --a

echo "5th PASS (geom_name...)"
$SCRIPTPATH/../vfr2${PGM}.py --type OB_564729_UKSH $OPT --o --geom OriginalniHranice

#echo "6th PASS (date...)"
#$SCRIPTPATH/../vfr2${PGM}.py --type OB_564729_UKSH $OPT --o --date 20151031

if [ "$PGM" = "pg" ] ; then
    echo "6th PASS (schema per file...)"
    $SCRIPTPATH/../vfr2${PGM}.py --type OB_564729_UKSH $OPT --schema vfr_xxxxxxx_ob_564729_uksh
fi

exit 0
