#!/usr/bin/python
#encoding=GBK

import os
import getopt
import sys,re,time,random,string
from ssh_session import *
from datetime import date

def createRsyncTunnel(strIP, user, passwd, src_path, dst_path, interval, pattern, rsopt, timeout):
    ssh = ssh_session(user, strIP, passwd)
    cmd = "mkdir -p " + dst_path
    ssh.ssh_cmd(cmd, 60, True)
   
 
    while True:
        start_time = time.time()
        if ssh.rsync(src_path, dst_path, pattern, rsopt, timeout):
            print "Info:", date.today().strftime("%Y-%m-%d"), time.strftime("%H:%M:%S", time.localtime()), \
                "sync src_path and dst_path success, spend\t", time.time() - start_time, "\tsecs"
        else:
            print "Error:", date.today().strftime("%Y-%m-%d"), time.strftime("%H:%M:%S", time.localtime()), \
                "sync src_path and dst_path failed, spend\t", time.time() - start_time, "\tsecs"
            
        if time.time() - start_time > interval:
            continue
        else:
            time.sleep(interval - time.time() + start_time)
        
    
def createCommTunnel(strIP, user, passwd, src_path, dst_path, senderID='', pattern='*', appendID=False, timeout=600, send_step=50):
    loopInterval = 10

    if not src_path.endswith('/'):
        src_path += '/'
    if not dst_path.endswith('/'):
        dst_path += '/'
    src_tmp_path = src_path + ".tmp/"
    src_backup_path = src_path + ".bak/"
    dst_tmp_path = dst_path + ".tmp/" + senderID + '/'

    if not os.path.isdir(src_tmp_path):
        os.makedirs(src_tmp_path)
    if not os.path.isdir(src_backup_path):
        os.makedirs(src_backup_path)

    ssh = ssh_session(user, strIP, passwd)
    cmd = "mkdir -p " + dst_path
    ssh.ssh_cmd(cmd, 60, True)
    cmd = "mkdir -p " + dst_tmp_path
    ssh.ssh_cmd(cmd)
    
    index = 0
    while True:
        #step1 : move src files to src_temp_path
        cmd = r'cd %s; [ `ls | wc -l` -lt "2000" ] && find "%s" -maxdepth "1" -iname "%s" -type f|grep -v "/\." | head -n "2000"|xargs mv -t "%s"' % \
                (src_tmp_path, src_path, pattern, src_tmp_path)
                
        #cmd =  'cd %s; find -maxdepth 1 -iname "%s" | head -n 2000 |xargs mv -t  %s' % (src_path, pattern, src_tmp_path) 
        cur_time = time.time()
        if not os.system(cmd):
            print "Info:", date.today().strftime("%Y-%m-%d"), time.strftime("%H:%M:%S", time.localtime()), \
                "mv src file to tmp success, spend\t", time.time() - cur_time, "\tsecs"
        else:
            print "Info:", "src file copy completed, sleep %d secs" % loopInterval
            time.sleep(loopInterval)

        #step2 : send src_temp_path files to dst_tmp_path
        index += 1

        time.sleep(1)
        try:
            flist = []
            for fname in os.listdir(src_tmp_path) + ['']:
                if fname != '' and len(flist) < send_step:
                    flist.append(src_tmp_path + fname)
                    continue

                if len(flist) == 0:
                    continue

                str_file_list = string.join(flist, ' ')
                flist = []
                
                cur_date = date.today().strftime("%Y-%m-%d")
                src_tmp_backup_path = src_backup_path + cur_date + "/" + str(random.randint(0,100)) + "/"
                if not os.path.isdir(src_tmp_backup_path):
                    os.makedirs(src_tmp_backup_path)

                cur_date = date.today().strftime("%Y-%m-%d")    
                cur_time = time.time()
                if not ssh.scp(str_file_list, dst_tmp_path, timeout):
                    print "Error:", cur_date ,time.strftime("%H:%M:%S",time.localtime()), "scp src to dst failed"
                else:
                    print "Info:", cur_date, time.strftime("%H:%M:%S", time.localtime()), \
                            "scp src to dst success, spend\t",time.time() - cur_time, "\tsecs"

                    command = "mv -f  " + str_file_list + " " + src_tmp_backup_path
                    cur_time = time.time()
                    if not os.system(command):
                        print "Info:", cur_date, time.strftime("%H:%M:%S", time.localtime()), \
                            "backup src file suc, spend\t", time.time() - cur_time, "\tsecs"
                    else:
                        print "Error:", cur_date, time.strftime("%H:%M:%S", time.localtime()), \
                            "backup src file failed, spend\t", time.time() - cur_time, "\tsecs"

                    if not appendID:
                        command = 'cd %s; ls | xargs mv -t %s' % (dst_tmp_path, dst_path)
                    else:
                        command = 'cd %s; for file in $(ls %s); do mv %s/$file ${file}_%s; done' % \
                                (dst_path, dst_tmp_path, dst_tmp_path, senderID)
                    cur_time = time.time()
                    ssh.ssh_cmd(command, timeout)
                    print "Info:", cur_date, time.strftime("%H:%M:%S", time.localtime()), "mv dst file success, spend\t",\
                        time.time() - cur_time, "\tsecs"
        except Exception,e:
            cur_date = date.today().strftime("%Y%m%d")
            cur_time = time.strftime("%H:%M:%S", time.localtime())
            print "Error:", cur_date, cur_time, "exception\t",e


def usage(pname):
    usage_str = '''\
usage: %s [options] IP User Passwd SrcPath DstPath 
  [opt]:
      -a             Append Sender ID to filename               (invalid in rsync mode)
      -A/--rsopt     set rsync option, default is "auz".        (invalid in common mode)
      -i/--interval  set rsync interval, default is 300.        (invalid in common mode)
      -n             Specify Tunnel Name                        (invalid in rsync mode)
      -r             Specify Filter pattern
      -R/--rsync     use rsync module
      -s             Specify Sender ID                          (invalid in rsync mode)
      -t             spawn time out in seconds, 0 indicates no time out. default is 600 .\
      ''' % pname
    print usage_str
    sys.exit(1)


def main():
    try:
        lstOpt, lstArg = getopt.getopt(sys.argv[1:], "s:n:r:t:A:i:aR", ['rsync', 'rsopt', 'interval'])
    except getopt.GetoptError, err:
        print str(err) # will print something like "option -a not recognized"
        usage(sys.argv[0])
    if len(lstArg) < 5:
        usage(sys.argv[0])
    senderID = None
    tunnelName = None
    filterRegex = None
    appendID = False
    timeout = 600
    rsopt = "-auz"; 
    useRsync = False
    interval = 300
    for (option, value) in lstOpt:
        if option == '-s':
            senderID = value
        elif option == '-r':
            filterRegex = value
        elif option == '-a':
            appendID = True
        elif option == '-t':
            timeout = int(value)
        elif option in ('-R', '--rsync'):
            useRsync = True
        elif option in ('-A', '--rsopt'):
            rsopt = value.strip('"').strip("'")
        elif option in ('-i', '--interval'):
            interval = int(value)

    if timeout == 0:
        timeout = -1

    if useRsync:
        #backword compatible with python 2.4
        #createRsyncTunnel( *lstArg[:5], interval=interval, pattern=filterRegex, rsopt=rsopt, timeout=timeout)
        createRsyncTunnel(lstArg[0], lstArg[1], lstArg[2], lstArg[3], lstArg[4], interval, filterRegex, rsopt, timeout)
    else:
        #createCommTunnel( * lstArg[:5] , senderID = senderID, pattern=filterRegex, appendID = appendID, timeout=timeout)
        createCommTunnel(lstArg[0],lstArg[1], lstArg[2], lstArg[3], lstArg[4], senderID, filterRegex, appendID, timeout)

if __name__ == "__main__":
    main()
