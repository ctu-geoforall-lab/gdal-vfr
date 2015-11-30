#!/bin/sh

SCRIPT=`realpath $0` # realpath is a separate package and doesn't need
                     # to be installed
if [ -z $SCRIPT ] ; then
    SCRIPTPATH='.'
else
    SCRIPTPATH=`dirname $SCRIPT`
fi

export DB=ruian
export DIR=fulldb
export FILE=../db_uksh.txt
export LOG=log.txt
export LOG_ERR=log_err.txt

mkdir -p $DIR
cd $DIR

nohup $SCRIPTPATH/../vfr2pg.py --file $FILE --dbname $DB --o >$LOG 2>$LOG_ERR &
