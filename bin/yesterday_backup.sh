#!/bin/sh

if [ -e ~/.bashrc ];then
    source ~/.bashrc
fi

if [ -e ~/.profile ];then
    source ~/.profile
fi

srcdir=/data2/logdata
backupdir="\/data1/logdata.daily.bak"

yesterday=`date -d '-1 days' '+%Y%m%d'`

if [ $# -eq 1 ];then
    yesterday=$1
fi

find $srcdir -type d  -iname $yesterday | while read fpath
do
    backuppath=`dirname $fpath | sed "s/\/data2/${backupdir}/"`
    if ! [ -d $backuppath ];then
        mkdir -p $backuppath
    fi
    finputname=`basename $fpath`
    foutputname=`basename $fpath`
    inputdir=`dirname $fpath`
    link_output_bak=$backuppath/$foutputname.link.tgz
    data_output_bak=$backuppath/$foutputname.tgz
    cd $inputdir
    tar zcvf  $link_output_bak $finputname/ &
    tar zhcvf $data_output_bak $finputname/ &
    cd -
done

wait
