#!/bin/sh


process_list=('fileTunnel.py'\
               )

function stop_all_tunnel()
{
    num=0
    process_name=$1
    pid_list=`ps -ef | grep $process_name | grep -v grep | grep -v "vi $process_name" | awk '{print $2}'`
    for pid in $pid_list
    do
        kill $pid;
        if [ $? -eq "0" ];then
            num=$((num+1))
        fi
    done
    return $num
}

function stop_one_tunnel()
{
    num=0
    process_name=$1
    tunnel_name_=$2
    pid_list=`ps -ef | grep "$process_name" | grep "$tunnel_name_" | grep -v grep | grep -v "vi $process_name" | awk '{print $2}'`
    for pid in $pid_list
    do
        kill $pid
        if [ $? -eq "0" ];then
            num=$((num+1))
        fi
    done
    return $num
}


function usage()
{
    echo "Usage: $0 [option] [tunnel_name, default is all tunnels.]" >&2
    exit    1
}

function main()
{
    kill_all_tunnel=true
    tunnel_name=
    while getopts :t:h opt 
    do
        case $opt in
            h)
                usage $@
                ;;
            t)
                tunnel_name=$OPTARG
                kill_all_tunnel=false
                ;; 
            '?')
                usage $@
                ;;
        esac
    done
    shift $((OPTIND - 1))

    if [ $# -eq "1" ];then
        kill_all_tunnel=false
        tunnel_name=$1
    fi
    if $kill_all_tunnel;then
        for process in ${process_list[@]}
        do
            cur_time=`date '+%Y-%m-%d %H:%M:%S'`
            stop_all_tunnel $process
            printf "Time(%s): %s processes named %s be killed\n\n" "$cur_time" $? "$process"
        done
    else
        for process in ${process_list[@]}
        do
            cur_time=`date '+%Y-%m-%d %H:%M:%S'`
            stop_one_tunnel $process $tunnel_name
            printf "Time(%s): %s tunnel named %s be killed\n\n" "$cur_time" $? $tunnel_name
        done
    fi

}

main $@
