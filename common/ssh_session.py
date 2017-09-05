import sys
import time
import re
import pdb
from pexpect import *

class SSHSession:

    "Session with extra state including the password to be used."

    def __init__(self, cout=None, verbose=False):
        self._user = None
        self._host = None
        self._port = None
        self._password = None
        self._cout = cout
        self._verbose = verbose
        self._SSH_OPTS = "-o 'RSAAuthentication=no' -o 'PubkeyAuthentication=no'"
        self._re = re.compile(r'(.{1,256})@(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})#*(\d*)')

    def __exec(self, cmd, timeout):
        if not timeout or timeout <= 0:
            timeout = -1

        child_result, exitstatus, is_timeout = run(cmd, timeout=timeout, withexitstatus=1, logfile=self._cout,\
                events={'(?i)(?:password)|(?:passphrase for key)': '%s\r\n' % self._password,
                '(yes/no).*':'yes\r\n'})
        if is_timeout:
            return False
        #print 'child_result=', child_result, exitstatus
        return (exitstatus == 0)

    def __exec_old(self, cmd, timeout):
        import pexpect
        if not timeout or timeout <= 0:
            end_time = sys.maxint
        else:
            end_time = time.time() + timeout
        child = pexpect.spawn(cmd, timeout=(end_time - time.time()))
        #child.delaybeforesend = 0
        #child.delayafterclose = 0
        #child.delayafterterminate = 0
        #child.logfile = self._cout
        child.logfile_read = self._cout
        try_count = 5
        while try_count:
            try:
                try_count -= 1
                #backword compatible with python 2.4
                if end_time - time.time() < 0:
                    timeout_piece = 0
                else:
                    timeout_piece = end_time - time.time()

                #timeout_piece = 0 if end_time - time.time() < 0 else end_time - time.time()
                i = child.expect(['(?i)(?:password)|(?:passphrase for key)', 'Authentication.*', '(yes/no).*', '200%.*',\
                        'Host key not found.*', 'error.*',\
                        pexpect.EOF,\
                        pexpect.TIMEOUT],timeout=timeout_piece)
                if i == 0:
                    if self._verbose:
                        print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    child.sendline(self._password)
                    continue
                elif i in (1,3):
                    if self._verbose:
                        print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    continue
                elif i == 2:
                    if self._verbose:
                        print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    child.sendline("yes")
                    continue
                elif i == 4:
                    if self._verbose:
                        print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    trace_prefix = 'strace -o ".strace.out" '
                    if cmd.find(trace_prefix) != -1:
                        cmd = trace_prefix + cmd
                        continue
                    return None
                elif i == 5 or i == 6:
                    #EOF
                    if self._verbose:
                        print >> sys.stderr, 'Connection exit'
                        print >> sys.stderr, 'Here is what SSH said:'
                        print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                        print >> sys.stderr, child.before, child.after
                    child.close()
                    break
                elif i == 7:
                    #timeout
                    if self._verbose:
                        print >> sys.stderr, 'Connection timeout'
                        print >> sys.stderr, 'SSH could not login. Here is what SSH said:'
                        print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    child.close()
                    return None
            except Exception,e:
                if self._verbose:
                    print >> sys.stderr, "Connection close",e
                    print >> sys.stderr, 'SSH could not login. Here is what SSH said:'
                    print >> sys.stderr, 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    return None

        return  not child.exitstatus

    def __parse_cmd(self, cmd):
        #tshopping@172.24.32.248#36000:/data1/tshp1/xxx
        success = False
        pattern = '(.{1,256})@(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})#*(\d*)'
        for seg in cmd.strip().split():
            seg = seg.strip()
            if not seg:
                continue
            m = self._re.search(seg)
            if m:
                self._user = m.group(1)
                self._host = m.group(2)
                assert self._user
                assert self._host
                success = True
                if m.group(3):
                    self._port = m.group(3)
                break
        return success


    def __ssh_command (self, remote_cmd, dest_info, passwd, timeout):
        '''
        This runs a command on the remote host. This could also be done with the
        pxssh class, but this demonstrates what that class does at a simpler level.
        This returns a pexpect.spawn object. This handles the case when you try to
        connect to a new host and ssh asks you if you want to accept the public key
        fingerprint and continue connecting.
        '''
        assert self.set_passwd(passwd)
        assert self.__parse_cmd(dest_info)
        if self._port:
            cmd = 'ssh -q %s -p%s -l "%s" "%s" "%s"' % (self._SSH_OPTS, self._port, self._user, self._host, remote_cmd)
        else:
            cmd = 'ssh -q %s -l "%s" "%s" "%s"' % (self._SSH_OPTS, self._user, self._host, remote_cmd)
        #print cmd
        return self.__exec(cmd, timeout)

    def __scp(self, src_path, dst_path, passwd, timeout):
        assert self.set_passwd(passwd)
        assert self.__parse_cmd('%s\t%s' % (src_path, dst_path))
        if self._port:
            cmd = 'scp -q %s -P %s %s %s' % (self._SSH_OPTS, self._port, src_path, dst_path)
        else:
            cmd = 'scp -q %s %s %s' % (self._SSH_OPTS, src_path, dst_path)
        return self.__exec(cmd, timeout)

    def __rsync(self, src_path, dst_path, passwd, timeout, option):
        if not timeout or timeout <= 0:
            timeout = sys.maxint
        cmd = 'rsync -P --timeout=%d %s %s %s' % (timeout, option, src_path, dst_path)
        #print cmd
        if passwd:
            assert self.set_passwd(passwd)
            #print cmd
            assert self.__parse_cmd(cmd)
        return self.__exec(cmd, timeout)

    def set_passwd(self, passwd):
        if passwd:
            self._password = passwd
            return True
        return False

    def ssh_cmd(self, dest_info, command, passwd, timeout=600):
        '''timeout set to None means timeout is invalid '''
        assert isinstance(command, str)
        assert isinstance(dest_info, str)
        assert isinstance(passwd, str)
        return self.__ssh_command(command, dest_info, passwd, timeout)

    def scp(self, src, dst, passwd, timeout=600):
        assert src
        assert dst
        '''timeout set to None means timeout is invalid'''
        return self.__scp(src, dst, passwd, timeout)

    def rsync(self, src_path, dst_path, passwd, timeout=600, option="-az"):
        assert src_path
        assert dst_path
        return self.__rsync(src_path, dst_path, passwd, timeout, option)


if __name__ == "__main__":
    #scp(src_file_list, dst_user, dst_ip, dst_path, dst_passwd)
    #file_list = "scp_upload.py gen_snap_new"
    #scp(file_list, "tshopping", "172.24.29.204", "/data1", "T5hopping")
    #ssh = SSHSession("tshopping", "172.26.0.55", "T5hopping")

    ssh = SSHSession(cout=sys.stdout)
    #ret = ssh.rsync('tdiscuz@10.151.130.150#36000:/data1/msg_bus_data/httpsqs.db', '.', 'T0iscuz', 3)
    #ret = ssh.scp('tdiscuz@10.151.130.150#36000:/data1/msg_bus_data/httpsqs.db', '.', 'T0iscuz',3)
    ret = ssh.ssh_cmd('tdiscuz@10.151.130.150#36000', 'ls -l /data', 'T0iscuz', 3)
    sys.exit(ret)
