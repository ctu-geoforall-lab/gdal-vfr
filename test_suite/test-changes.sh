#!/bin/sh

SCRIPT=`realpath $0` # realpath is a separate package and doesn't need
                     # to be installed
if [ -z $SCRIPT ] ; then
    SCRIPTPATH='.'
else
    SCRIPTPATH=`dirname $SCRIPT`
fi

DB=ruian_test

# single file 
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
$SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/ST_ZKSH.xml.gz $OPT

echo "2nd PASS (apply changes...)"
$SCRIPTPATH/../vfr2${PGM}.py --file $SCRIPTPATH/ST_ZKSH.xml.gz $OPT

exit 0
