#!/bin/sh

SCRIPT=`realpath $0` # realpath is a separate package and doesn't need
                     # to be installed
if [ -z $SCRIPT ] ; then
    SCRIPTPATH='.'
else
    SCRIPTPATH=`dirname $SCRIPT`
fi

if test -z $1 ; then
    echo "usage: $0 dbname"
    exit 1
else
    DB=$1
fi
FILE=db_uksh.txt

export DATA_DIR=data_$DB

nohup $SCRIPTPATH/../vfr2pg.py --file $SCRIPTPATH/$FILE --dbname $DB -o "$2" &
