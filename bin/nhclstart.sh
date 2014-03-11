#!/bin/sh

if [ -e ~/.bashrc ];then
    source ~/.bashrc
fi

if [ -e ~/.profile ];then
    source ~/.profile
fi

nohup $1 2>&1 |./cronolog ../log/$2_%Y%m%d.log >> /dev/null 2>&1 &
#./$1
exit $?
