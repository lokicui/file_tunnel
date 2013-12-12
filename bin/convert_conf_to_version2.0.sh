#!/bin/sh

cat allFileTunnel.conf.template
conf_file="allFileTunnel.conf"
while read line
do
    echo $line | grep '^#' 1>&2>/dev/null
    [ $? -eq 0 ] && continue
    [ -z "$line" ] && continue
    name=`echo $line | awk -F" " '{print $1}' `
    dest_path=`echo $line | awk -F" " '{print $(NF)}' `
    src_path=`echo $line | awk -F" " '{print $(NF-1)}' `
    passwd=`echo $line | awk -F" " '{print $(NF-2)}' `
    user=`echo $line | awk -F" " '{print $(NF-3)}' `
    ip=`echo $line | awk -F" " '{print $(NF-4)}'`
    appname=`echo $line | grep '\-a' | grep -o '\-s.*' | awk -F ' ' '{print $2}'`
    if [ -z "$appname" ];then
        printf '%s %s->%s@%s#36000:%s %s\n' $name $src_path $user ${ip} $dest_path $passwd
    else
        printf '%s -a %s %s->%s@%s#36000:%s %s\n' $name $appname $src_path $user ${ip} $dest_path $passwd
    fi
done < $1
exit 0
