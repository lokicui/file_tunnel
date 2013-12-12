#!/bin/sh

if [ -e ~/.bashrc ];then
    source ~/.bashrc
fi

if [ -e ~/.profile ];then
    source ~/.profile
fi


TM=`date '+%Y-%m-%d %H:%M:%S'`
yesterday=`date -d '-1 days' '+%Y%m%d'`
if [ $# -eq 1 ];then
    yesterday=$1
fi

srcdir_pattern=/dataN/logdata
backupdir_pattern=/dataN/logdata/logdata.bak
backupdir=`echo $backupdir_pattern | sed 's/dataN/data1/'`

begindisknum4bak=1
enddisknum4bak=11

function gen_backupdir()
{
    local i=$1
    local diskno=$((i+1))
    if [ $i -eq $enddisknum4bak ];then
        diskno=$begindisknum4bak
    fi
    local bakdir=`echo $backupdir_pattern | sed "s/dataN/data$diskno/"`
    local bakpath=$bakdir/disk"$i"
    if [ ! -d $bakpath ];then
        mkdir -p $bakpath
        if [ ! -d $backupdir ];then
            mkdir -p $backupdir
        fi
        ln -s $bakpath $backupdir
    fi
}

for((i=$begindisknum4bak;i<=$enddisknum4bak;i++))
do
    srcdir=`echo $srcdir_pattern | sed "s/dataN/data$i/"`
    if ! [ -d $srcdir ];then
        continue
    fi
    bakdir=$backupdir/disk"$i"
    if ! [ -d $bakdir ];then
        gen_backupdir $i
    fi
    bakfname=$bakdir/$yesterday.tgz
    srcflist=`find $srcdir -maxdepth 2 -type d -iname $yesterday | xargs`
    if [ -n "$srcflist" ];then
        tar zcvf $bakfname $srcflist &
    fi
done

wait
printf "TM(%s) disk backup inc success!\n" "$TM"
