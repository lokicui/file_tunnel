#!/bin/sh

source ~/.bashrc
source ~/.profile

conf_file="allFileTunnel.conf"
myExec=fileTunnel.py


long_bit=`getconf LONG_BIT`
if ! [ -r $conf_file ];then
    echo $conf_file "isn't readable!"
    exit 1
fi

if [ $long_bit -gt 32 ];then
    ln -f -s cronolog_64 cronolog
else
    ln -f -s cronolog_32 cronolog
fi



while read line
do
    echo $line | grep '^#' 1>&2>/dev/null
    [ $? -eq 0 ] && continue
    name=`echo $line | awk -F" " '{print $1}' `
    args=`echo $line | grep -o ' .*'`
    if ([ -z "$name" ]  || [ -z "$args" ]);then
        continue
    fi
    if [ -z "`ps -ef |grep "$name" | grep "$myExec" | grep -v grep`" ] ; then
        ./nhclstart.sh "./$myExec -n $name $args" "$name"
        ret=$?
        echo "`date +'%Y-%m-%d %T'` ${name} restarted, status($ret)" >>../log/restart.log
    fi
done < $conf_file
exit 0
