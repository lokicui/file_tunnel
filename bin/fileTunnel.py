#!/usr/bin/python
#encoding=GBK

import os
import sys
import fcntl
import getopt
import re
import time
import pdb
import random
from datetime import datetime, date, timedelta
sys.path.append('../common')

from ssh_session import SSHSession

DEBUG = 1
INFO = 2
WARNING = 3
ERROR = 4
FATAL = 5

MODE_UNKNOWN = 0
MODE_PUSH = 1
MODE_PULL = 2
MODE_RSYNC = 4
MODE_OR = 8
MODE_AND = 16

g_alarm_script = 'alarm.sh'

class TunnelConfItem(object):
    '''
    configuration for every tunnel
    '''

    def __init__(self):
        self.name = ''
        self.filter = '*'
        self.extral_options = ['-auz']
        self.appname = os.uname()[1]
        self.timeout = 600.0
        self.flush_interval = 1.0
        self.start_time = None
        self.backup_pattern = '%Y-%m-%d/%H'
        self.bak_days = 30

        self.mode = MODE_UNKNOWN
        self.src_nodes = []
        self.dest_nodes = []

#class BaseTunnel(multiprocessing.Process):
class BaseTunnel(object):
    '''
    '''
    class Node(object):
        '''
        '''

        def __init__(self, string, passwd):
            self._ssh = SSHSession(cout=sys.stderr)
            self._host = ''
            self._dir = ''
            self._islocal = False
            self._user = ''
            self._port = None
            self._passwd = passwd
            self._string = string
            self.init()

        def __str__(self):
            return self._string

        def init(self):
            if self._string.find('@') == -1:
                self._islocal = True
                self._dir = self._string
            else:
                m = re.search(r'(.*)@(\d+.\d+.\d+.\d+)(#\d+)?:(.*)', self._string)
                if m:
                    self._user = m.group(1)
                    self._host = m.group(2)
                    port_str = m.group(3)
                    if port_str and port_str.strip('#').isdigit():
                        self._port = int(port_str.strip('#'))
                    self._dir = m.group(4).rstrip(r'/')
                assert self._passwd

        def is_alive(self):
            if not self._islocal:
                dir = self._dir
                assert dir.startswith('/')
                #root_dir = dir[:dir.find('/', 1)]
                dir = time.strftime(self._dir, time.localtime())
                self.ssh_cmd('mkdir -p %s' % dir)
                return self.ssh_cmd('[ -r %s ]' % dir)
            return True

        def ssh_cmd(self, cmd):
            return self._ssh.ssh_cmd(self.uhost(), cmd, self.passwd(), timeout=5)
        
        def get_bak_basedir(self, tm=None):
            if not tm:
                tm = time.localtime()
            return os.path.join(self.dir(tm), '.bak/')

        def fmtbackupdir(self, backupdir_pattern, tm=None):
            if not tm:
                tm = time.localtime()
            return time.strftime('%s/%s' % (self.get_bak_basedir(tm), backupdir_pattern), tm)

        def dir(self, tm=None, create_dir=True):
            if not tm:
                tm = time.localtime()
            if self._islocal:
                dir = time.strftime(self._dir, tm)
                if not os.path.isdir(dir) and create_dir:
                    os.makedirs(os.path.split(dir)[0])
            else:
                dir = time.strftime(self._string, tm)
            return dir

        def passwd(self):
            return self._passwd

        def host(self):
            return self._host

        def uhost(self):
            if self._port:
                return '%s@%s#%d' % (self._user, self._host, self._port)
            else:
                return '%s@%s' % (self._user, self._host)

        def dest(self):
            return str(self)

        def __str__(self):
            return self._string

    def __init__(self):
        self._lockfd = open('.lock', 'w')

    def makedirs(self, path):
        ret = True
        fcntl.flock(self._lockfd, fcntl.LOCK_EX)
        try:
            os.makedirs(path)
        except:
            ret = False
        fcntl.flock(self._lockfd, fcntl.LOCK_UN)
        return ret

    def run(self):
        raise NotImplementedError(reflect.qual(self.__class__) + " did not implement run")


class PushTunnel(BaseTunnel):
    '''
      push tunnel, you can push local files to multi-remote-machines in master-backup mode
      Note:
            Only support master-backup mode, no master-master mode
            That means only one machine can receive data at a time. In master-backup mode, we will try
            sending data to backup machine if we found master is down.

            local->remote means push
            remote->local means pull
    '''
    def __init__(self, conf):
        super(self.__class__, self).__init__()
        self._name = conf.name
        self._appname = conf.appname
        self._src_nodes = conf.src_nodes
        self._dest_nodes = conf.dest_nodes
        self._backup_pattern = conf.backup_pattern
        self._filter = conf.filter
        self._timeout = conf.timeout
        self._mode = conf.mode
        self._extral_options = conf.extral_options
        self._flush_interval = conf.flush_interval
        self._bak_days = conf.bak_days

        assert len(self._src_nodes) == 1
        assert len(self._dest_nodes) >= 1

        self._remote_alive_nodes = self._dest_nodes
        self._step_value = 500
        self._stop = False
        self._ssh = SSHSession(cout=sys.stderr)


    def find_alive_nodes(self):
        '''
        iterating destination nodes and find one which still alive
        '''
        alive_nodes = []
        for node in self._dest_nodes:
            if node.is_alive():
                alive_nodes.append(node)
            else:
                log(ERROR, 'host(%s) dead!' % node.uhost())
        assert alive_nodes
        return alive_nodes

    def alive_valid_nodes(self):
        self._remote_alive_nodes = self.find_alive_nodes()
        for node in self._remote_alive_nodes:
            yield node
            if self._mode & MODE_OR:
                break

    def get_backupdir(self):
        return self._src_nodes[0].fmtbackupdir(self._backup_pattern)

    def src_dir(self):
        return str(self._src_nodes[0].dir())

    def appname(self):
        return str(self._appname)

    def name(self):
        return self._name

    def step_value(self):
        return self._step_value

    def options(self):
        return ' '.join(self._extral_options + ['--delay-updates'])

    def filter(self):
        return self._filter

    def ssh(self):
        return self._ssh

    def stop(self):
        self._stop = True

    def sending_dir(self):
        '''
        return current sending direction && create it if dones't exist
        '''
        local_sending_dir = os.path.join(self.src_dir(), '.' + str(self.name()))
        if not os.path.isdir(local_sending_dir):
            self.makedirs(local_sending_dir)
        return local_sending_dir
    
    def _rotate_backup(self):
        dir = self._src_nodes[0].get_bak_basedir()
        if dir and os.path.isdir(dir):
            cmd = 'find %s -ctime +%s -delete' % (dir, self._bak_days)
            log(INFO, 'CMD[%s] execute success!' % cmd)
            return os.system(cmd)
        return False


    def _init_local_sending_dir(self):
        '''
        select almost step_value files && move all those file to sending_dir
        return true if any file needs to be send
        '''
        selected = len(os.listdir(self.sending_dir()))
        if selected:
            return selected

        total = len(os.listdir(self.src_dir()))
        if total:
            cmd = 'find %s -maxdepth 1 ! -name ".?*" -iname "%s" -type f | xargs -r ls -rt | tail -n "%s" | xargs -r mv -t %s'\
             % (self.src_dir(), self.filter(), self.step_value(), self.sending_dir())
            if os.system(cmd):
                log(ERROR, 'CMD[%s] execute failed!' % cmd)
                self.stop()
            else:
                log(INFO, 'CMD[%s] execute success!' % cmd)
                for file in os.listdir(self.sending_dir()):
                    basename = os.path.split(file)[1]
                    fname = os.path.join(self.sending_dir(), basename)
                    if not os.path.isfile(fname):
                        continue
                    if self.appname():
                        nname = os.path.join(self.sending_dir(), '%s.%s' % (basename, self.appname()))
                    else:
                        nname = os.path.join(self.sending_dir(), basename)
                    os.rename(fname, nname)

        return len(os.listdir(self.sending_dir()))

    def _push(self, node, option):
        '''
        push local files to remote machine
        if success:
            mv local file to backupdir
        return success or not
        '''
        return self.ssh().rsync(self.sending_dir() + '/', node.dir(), node.passwd(), self._timeout, option)

    def _backup(self):
        backupdir = self.get_backupdir()
        if not os.path.isdir(backupdir):
            self.makedirs(backupdir)
        return self.ssh().rsync(self.sending_dir() + '/', backupdir, None, self._timeout, '-az --remove-sent-files --remove-source-files --inplace')

    def _can_trigger(self):
        return not self._stop

    def run(self):
        '''
        subprocess entry
        '''
        while self._can_trigger():
            if self._init_local_sending_dir():
                for node in self.alive_valid_nodes():
                    if not self._push(node, self.options()):
                        log(ERROR, 'push to node[%s] failed' % node)
                        break
                else:
                    log(INFO, 'push to node[%s] success' % node)
                    assert self._backup()
                    self._rotate_backup()
                    log(INFO, 'sleep %ds...' % self._flush_interval)
                    time.sleep(self._flush_interval)
            else:
                time.sleep(1)


class RsyncPullTunnel(BaseTunnel):
    '''
    '''

    def __init__(self, conf):
        super(self.__class__, self).__init__()
        self._name = conf.name
        self._appname = conf.appname
        self._src_nodes = conf.src_nodes
        self._dest_nodes = conf.dest_nodes
        self._backup_pattern = conf.backup_pattern
        self._filter = conf.filter
        self._timeout = conf.timeout
        self._mode = conf.mode
        self._extral_options = conf.extral_options
        self._flush_interval = conf.flush_interval
        self._start_time = conf.start_time
        self._bak_days = conf.bak_days

        assert len(self._src_nodes) >= 1
        assert len(self._dest_nodes) == 1

        self._remote_alive_nodes = self._src_nodes
        self._stop = False
        self._ssh = SSHSession(cout=sys.stderr)
        self._rsync_days = 1


    def find_alive_nodes(self):
        '''
        iterating destination nodes and find one which still alive
        '''
        alive_nodes = []
        for node in self._src_nodes:
            if node.is_alive():
                alive_nodes.append(node)
            else:
                log(ERROR, 'host(%s) dead!' % node.uhost())
        assert alive_nodes
        return alive_nodes

    def alive_valid_nodes(self):
        self._remote_alive_nodes = self.find_alive_nodes()
        for node in self._remote_alive_nodes:
            yield node
            if self._mode & MODE_OR:
                break

    def select_one_disk(self, blacklist=[r'/data']):
        blacklist.append(self.view_disk())
        pattern = re.compile(r'/data\d+', re.I)
        disk_avail_ratio = {}
        default_selected_disk = '/data2'
        highest_ratio = 0
        for dataN in os.listdir('/'):
            dataN = os.path.join('/', dataN)
            if dataN in blacklist or not pattern.match(dataN):
                continue
            vfs = os.statvfs(dataN)
            avail_ratio = vfs.f_bavail * 1.0 / vfs.f_blocks
            if avail_ratio > highest_ratio:
                highest_ratio = avail_ratio
            if avail_ratio > 0.15:
                disk_avail_ratio[dataN] = avail_ratio

        if highest_ratio < 0.2:
            warn_msg = 'same disks has full, highest_available_ration=%.2f%%' % highest_ratio * 100
            log(WARN, warn_msg)
            global g_alarm_script
            if os.path.isfile(g_alarm_script):
                os.system('./%s "%s"' (g_alarm_script, warn_msg))

        if not disk_avail_ratio:
            log(ERROR, 'all disk has full, highest_available_ration=%.2f%%' % highest_ratio * 100)
            self._stop = True
            return default_selected_disk
        #asc order
        disk_avail_items = sorted(disk_avail_ratio.items(), key=lambda item:item[1], reverse=True)
        selected_disk_item = random.sample(disk_avail_items[:len(disk_avail_items)/2 + 1], 1)[0]
        return selected_disk_item[0]

    def view_disk(self):
        return r'/data1'

    def dest_dir(self, node, tm=None):
        if not tm:
            tm = time.localtime()
        dir = self._dest_nodes[0].dir(tm, False).replace(r'$SRCIP', node.host())
        view_dir = dir.replace(r'/$dataN', self.view_disk())
        #Return True if path is an existing directory.
        #This follows symbolic links, so both islink() and isdir() can be true for the same path.
        if os.path.isdir(view_dir):
            return view_dir
        #symlink,but broken, unlink it
        elif os.path.islink(view_dir):
            os.unlink(view_dir)
        #we need a dir,but is a regular file, remove it!
        elif os.path.isfile(view_dir):
            os.remove(view_dir)

        #create view parent dir
        view_parent_dir = os.path.split(view_dir)[0]
        if not os.path.isdir(view_parent_dir):
            self.makedirs(view_parent_dir)
        assert os.path.isdir(view_parent_dir) , view_parent_dir
        dest_dir = dir.replace(r'/$dataN', self.select_one_disk())
        if not os.path.isdir(dest_dir):
            #remove broken symlink
            if os.path.islink(dest_dir):
                os.unlink(dest_dir)
            self.makedirs(dest_dir)
        assert os.path.isdir(dest_dir)
        if not os.path.isfile(view_dir):
            os.symlink(dest_dir, view_dir)
        log(INFO, 'symlink(%s, %s)' % (dest_dir, view_dir))
        assert os.path.islink(view_dir)
        return view_dir

    def sending_path(self, node, tm=None):
        '''
        if sending_path didn't exist, there is no need to create it
        return current sending dir
        '''
        if not tm:
            tm = time.localtime()
        return node.dir(tm)

    def appname(self):
        return str(self._appname)

    def name(self):
        return self._name

    def step_value(self):
        return self._step_value

    def options(self):
        return ' '.join(self._extral_options)

    def filter(self):
        return self._filter

    def ssh(self):
        return self._ssh

    def stop(self):
        self._stop = True

    def task_time(self):
        return time.time() - self._timeout


    def _pull(self, node, option, tm):
        '''
        push local files to remote machine
        if success:
            mv local file to backupdir
        return success or not
        '''
        return self.ssh().rsync(self.sending_path(node, tm), self.dest_dir(node, tm), node.passwd(), self._timeout, option)

    def _can_trigger(self):
        if self._start_time is not None and not self._stop:
            #waiting until can trigger
            try:
                #python2.6
                dm = datetime.strptime('%s %s' % (date.today(), self._start_time), '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                if dm > now:
                    interval = (dm - now).seconds
                else:
                    interval = (dm + timedelta(days=1) - now).seconds
            except:
                #python2.4
                dm = time.mktime(time.strptime('%s %s' % (date.today(), self._start_time), '%Y-%m-%d %H:%M:%S'))
                now = time.time()
                if dm > now:
                    interval = dm - now
                else:
                    interval = dm + 86400 - now
            log(INFO, 'waiting for trigger, sleep %ds...' % interval)
            time.sleep(interval)
            log(INFO, 'sync start...')
        return not self._stop

    def run(self):
        '''
        subprocess entry
        '''
        while self._can_trigger():
            tm_now = time.time() - self._timeout
            for i in range(self._rsync_days):
                tm = tm_now - 86400 * i
                for node in self.alive_valid_nodes():
                    if not self._pull(node, self.options(), time.localtime(tm)):
                        break
            else:
                log(INFO, 'sync completed,sleep %ds...' % self._flush_interval)
                time.sleep(self._flush_interval)


class RsyncPushTunnel(BaseTunnel):
    '''
    implements in next version
    '''

    def __init__(self, conf):
        super(self.__class__, self).__init__()
        raise NotImplementedError(reflect.qual(self.__class__) + " did not implement")

class PullTunnel(BaseTunnel):
    '''
    implements in next version
    '''

    def __init__(self, conf):
        super(self.__class__, self).__init__()
        raise NotImplementedError(reflect.qual(self.__class__) + " did not implement")

def log(level, msg):
    now = str(datetime.now())
    if level == FATAL:
        raise RuntimeError('%s %s' % (now, msg))
    elif level == ERROR:
        print >> sys.stderr, '[ERROR]', now, msg
    elif level == WARNING:
        print >> sys.stderr, '[WARNING]', now, msg
    elif level == INFO:
        print >> sys.stderr, '[INFO]', now, msg
    elif level == DEBUG:
        print >> sys.stderr, '[DEBUG]', now, msg


def usage(pname):
    usage_str = '''\
NAME
       faster, flexible replacement for rcp

SYNOPSIS
       [LSRC means local src,RDEST means remote dest]
       [COMMON MODE]
           %s [options]... LSRC->RDEST                    RDEST_PASSWD
           %s [options]... RSRC->LDEST                    RSRC_PASSWD
       [MULTI-MASTER MODE]
           %s [options]... LSRC->RDEST1&RDEST2            RDEST1_PASSWD|RDEST2_PASSWD
           %s [options]... LSRC->RDEST1&RDEST2&RDEST3...  RDEST1_PASSWD|RDEST2_PASSWD|RDEST3_PASSWD...
           %s [options]... RSRC1&RSRC2->LDEST             RSRC1_PASSWD|RSRC2_PASSWD
           %s [options]... RSRC1&RSRC2&RSRC3...->LDEST    RSRC1_PASSWD|RSRC2_PASSWD|RSRC3_PASSWD...
       [MASTER-BACKUP MODE]
           %s [options]... LSRC->RDEST1|RDEST2            RDEST1_PASSWD|RDEST2_PASSWD
           %s [options]... LSRC->RDEST1|RDEST2|RDEST3...  RDEST1_PASSWD|RDEST2_PASSWD|RDEST3_PASSWD...
           %s [options]... RSRC1|RSRC2->LDEST             RSRC1_PASSWD|RSRC2_PASSWD
           %s [options]... RSRC1|RSRC2|RSRC3...->LDEST    RSRC1_PASSWD|RSRC2_PASSWD|RSRC3_PASSWD...

DESCRIPTION
      -a             Append suffix to filename.                  (default value=os.uname()[1])
      -b             Set backup rotate days. default is 30.      (bak files older then setting will be deleted)
      -i             Set rsync/push/pull interval,default is 1.  (There is no need to change the default value)
      -n             Specify Tunnel Name                         (No default value, must be unique)
      --option       Set extral option, default is "az".         (default value='az',changing it with caution)
      --bakpattern   Set backupdir pattern, default is 'sending_dir/.bak/bakpattern(%Y-%m-%d/%H)'
      -r             Specify Filter pattern, default is '*'
      -t             Spawn time out in seconds, 0 indicates no time out.
                     [If single file size is larger than 32M, you need to specify a larger time out. default is 600]
      ''' % ((pname,)*10)
    print usage_str
    sys.exit(1)

def load_config(tinfo, passwd):
    tpasswd = passwd.strip().split('|')
    conf = TunnelConfItem()
    src = tinfo.strip().split('->')[0]
    if src.find('@') != -1:
        conf.mode = MODE_PULL
        if src.find('|') != -1:
            srcs = src.split('|')
            conf.mode |= MODE_OR
        elif src.find('&') != -1:
            srcs = src.split('&')
            conf.mode |= MODE_AND
        else:
            srcs = [src]
        for i in range(0, len(srcs)):
            conf.src_nodes.append(BaseTunnel.Node(srcs[i], tpasswd[i]))
    else:
        conf.src_nodes.append(BaseTunnel.Node(src, None))

    dest = tinfo.strip().split('->')[1]
    if dest.find('@') != -1:
        conf.mode = MODE_PUSH
        if dest.find('|') != -1:
            dests = dest.split('|')
            conf.mode |= MODE_OR
        elif dest.find('&') != -1:
            dests = dest.split('&')
            conf.mode |= MODE_AND
        else:
            dests = [dest]
        assert len(dests) == len(tpasswd)
        for i in range(0, len(dests)):
            conf.dest_nodes.append(BaseTunnel.Node(dests[i], tpasswd[i]))
    else:
        conf.dest_nodes.append(BaseTunnel.Node(dest, None))
    return conf

def test():
    conf = TunnelConfItem()
    conf.src_nodes.append(None)
    conf.dest_nodes.append(None)
    tunnel = RsyncPullTunnel(conf)
    print tunnel.select_one_disk()

if __name__ == '__main__':
    try:
        lstOpt, lstArg = getopt.gnu_getopt(sys.argv[1:], "s:n:r:t:i:a:b:", ['bakpattern=', 'option=', 'rsync'])
    except getopt.GetoptError, err:
        print str(err) # will print something like "option -a not recognized"
        usage(sys.argv[0])

    if len(lstArg) < 2:
        usage(sys.argv[0])
    conf = load_config(lstArg[0], lstArg[1])
    for (option, value) in lstOpt:
        value = value.strip()
        if option == '-r':
            conf.filter = value.strip("'").strip('"')
        elif option == '-a':
            conf.appname = value.strip("'").strip('"')
        elif option == '-b':
            bak_days = value.strip("'").strip('"')
            if bak_days.isdigit():
                conf.bak_days = int(bak_days)
        elif option == '-s':
            conf.start_time = value.strip("'").strip('"')
        elif option == '-t':
            conf.timeout = int(value)
        elif option == '-n':
            conf.name = value
        elif option == '-i':
            conf.flush_interval = float(value)
        elif option == '--option':
            conf.extral_options.append(value.strip("'").strip('"'))
        elif option == '--bakpattern':
            conf.backup_pattern = '.bak/' + value.strip("'").strip('"')
        elif option == '--rsync':
            conf.mode |= MODE_RSYNC

    if conf.mode & MODE_RSYNC and conf.mode & MODE_PULL:
        tunnel = RsyncPullTunnel(conf)
    elif conf.mode & MODE_RSYNC and conf.mode & MODE_PUSH:
        tunnel = RsyncPushTunnel(conf)
    elif conf.mode & MODE_PUSH:
        tunnel = PushTunnel(conf)
    elif conf.mode & MODE_PULL:
        tunnel = PullTunnel(conf)
    else:
        log(FATAL, 'mode=%d does not inplements!' % conf.mode)
    tunnel.run()
