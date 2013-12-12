#!/bin/sh


TM=`date '+%Y-%m-%d %H:%M:%S'`
yesterday=`date -d '-1 days' '+%Y%m%d'`
if [ $# -eq 1 ];then
    yesterday=$1
fi
IP=10.185.22.37
disk=`df -P | grep -v 'data1' | grep -v 'data2' | awk  '{if(match($6, "data[0-9]+"))disk_avail[$6]=$4/$2;} END{for(k in disk_avail) print k,disk_avail[k]}' | sort -rnk 2 | head -n 1 | cut -d ' ' -f 1`

clicklog_path=$disk/logdata/clicklog/$yesterday/$IP
ln_dir=/data1/logdata/clicklog/$yesterday
ln_path=$ln_dir/$IP

if [ ! -d $ln_dir ];then
    mkdir -p $ln_path
    if [ ! -d $clicklog_path ];then
        mkdir -p $clicklog_path
    fi
    if [ ! -f $ln_path ];then
        ln -s $clicklog_path $ln_dir
    fi
else
    if [ ! -d $ln_path ];then
        if [ -f $ln_path ];then
            rm $ln_path
        fi
        if [ ! -d $clicklog_path ];then
            mkdir -p $clicklog_path
        fi
        if [ ! -f $ln_path ];then
            ln -s $clicklog_path $ln_dir
        fi
    fi
fi

echo $ln_path
#rsync etl@$IP::dbout/tdwout/qqlive/search_click/$yesterday/attempt*  $ln_path
$HADOOP_HOME/bin/hadoop fs -Dfs.default.name=hdfs://tl-if-nn-tdw.tencent-distribute.com:54310 -Dhadoop.job.ugi=u_isd:u_isd,supergroup  -get /stage/dbout/tdwout/qqlive/search_click/$yesterday/attemp* $ln_path
if [ $? -eq '0' ];then
    printf "TM(%s) pull clicklog success!\n" "$TM"
else
    printf "TM(%s) pull clicklog failed!\n" "$TM"
fi
