#!/bin/sh

export DB=ruian
export DIR=fulldb
export FILE=../db_uksh.txt
export LOG=log.txt
export LOG_ERR=log_err.txt

mkdir -p $DIR
cd $DIR
nohup ../../vfr2pg.py --file $FILE --dbname $DB --o >$LOG 2>$LOG_ERR &
