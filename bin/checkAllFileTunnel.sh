#!/bin/sh

if [ -e ~/.bashrc ];then
    source ~/.bashrc
fi

if [ -e ~/.profile ];then
    source ~/.profile
fi

conf_file="allFileTunnel.conf"
myExec=fileTunnel


long_bit=`getconf LONG_BIT`
if ! [ -r $conf_file ];then
    echo $conf_file "isn't readable!"
    exit 1
fi

if [ $long_bit -gt 32 ];then
    ln -f -s ../common/cronolog_64 cronolog
else
    ln -f -s ../common/cronolog_32 cronolog
fi

ln -sf "$myExec.py" $myExec

TM=`date '+%Y-%m-%d %H:%M:%S'`
total_num=0
already_started_num=0
starting_num=0
success_start_num=0
while read line
do
    echo $line | grep '^#' 1>&2>/dev/null
    [ $? -eq 0 ] && continue
    name=`echo $line | awk -F" " '{print $1}' `
    args=`echo $line | grep -o ' .*'`
    if ([ -z "$name" ]  || [ -z "$args" ]);then
        continue
    fi
    if ! pgrep -f "(^|/)$myExec($| ).*$name" > /dev/null; then
    #if [ -z "`ps -ef |grep "$name" | grep "$myExec" | grep -v grep`" ] ; then
        ./nhclstart.sh "./$myExec -n $name $args" "$name"
        ret=$?
        echo "`date +'%Y-%m-%d %T'` ${name} restarted, status($ret)" >>../log/restart.log
        starting_num=$((starting_num+1))
        #if ! [ -z "`ps -ef |grep "$name" | grep "$myExec" | grep -v grep`" ] ; then
        if pgrep -f "(^|/)$myExec($| ).*$name" > /dev/null; then
            success_start_num=$((success_start_num+1))
        fi
    else
        already_started_num=$((already_started_num+1))
    fi
    total_num=$((total_num+1))
done < $conf_file

echo "[$TM -- FileTunnel Status]
    total tunnels:$total_num
    already started tunnels:$already_started_num
    starting tunnels:$starting_num
    success start tunnels:$success_start_num
"
exit 0
