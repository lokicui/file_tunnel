#!/usr/bin/python
#encoding=GBK
import sys
import time
sys.path.append('./util/pexpect')
import pexpect

class ssh_session:

    "Session with extra state including the password to be used."

    def __init__(self, user, host, password, port=36000, verbose=None):
        self._user = user
        self._host = host
        self._port = port
        self._password = password
        self._verbose = verbose
    
    def __exec(self, cmd, max_timeout):
        if not max_timeout or max_timeout <= 0:
            end_time = sys.maxint
        else:
            end_time = time.time() + max_timeout
        child = pexpect.spawn(cmd, timeout=(end_time - time.time()))
        child.logfile = sys.stdout
        while True:
            try:
                #backword compatible with python 2.4
                if end_time - time.time() < 0:
                    timeout_piece = 0
                else:
                    timeout_piece = end_time - time.time()

                #timeout_piece = 0 if end_time - time.time() < 0 else end_time - time.time()
                i = child.expect(['password:.*', 'Authentication.*', '(yes/no).*', '100%.*',\
                        'Host key not found.*',\
                        pexpect.EOF,\
                        pexpect.TIMEOUT],timeout=timeout_piece)
                if i == 0:
                    if self._verbose:
                        print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    child.sendline(self._password)
                    continue
                elif i in (1,3):
                    if self._verbose:
                        print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    continue
                elif i == 2:
                    if self._verbose:
                        print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    child.sendline("yes")
                    continue
                elif i == 4:
                    if self._verbose:
                        print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    trace_prefix = 'strace -o ".strace.out" '
                    if cmd.find(trace_prefix) != -1:
                        cmd = trace_prefix + cmd
                        continue
                    return None
                elif i == 5:
                    #EOF
                    if self._verbose:
                        print 'Connection exit'
                        print 'Here is what SSH said:'
                        print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                        print child.before, child.after
                    child.close()
                    break
                elif i == 6:
                    #timeout
                    if self._verbose:
                        print 'Connection timeout'
                        print 'SSH could not login. Here is what SSH said:'
                        print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    child.close()
                    return None
            except Exception,e:
                if self._verbose:
                    print "Connection close",e
                    print 'SSH could not login. Here is what SSH said:'
                    print 'i(%s),child.before(%s), child.after(%s)' % (i, child.before, child.after)
                    return None

        return  child

    def __scp(self, src_file_list, dst_path, max_timeout):
        cmd = 'scp -q %s %s@%s#%s:%s' % (src_file_list, self._user, self._host, self._port, dst_path)
        return self.__exec(cmd, max_timeout)
    
    def __ssh_command (self, remote_cmd, max_timeout, doStrace):
    
        """This runs a command on the remote host. This could also be done with the
        pxssh class, but this demonstrates what that class does at a simpler level.
        This returns a pexpect.spawn object. This handles the case when you try to
        connect to a new host and ssh asks you if you want to accept the public key
        fingerprint and continue connecting. """

        if doStrace:
            cmd = 'strace -o \'.strace.out\' ssh -p%s -l "%s" "%s" "%s"' % (self._port, self._user, self._host, remote_cmd)
        else:
            cmd = 'ssh -q -p%s -l "%s" "%s" "%s"' % (self._port, self._user, self._host, remote_cmd)
           
        return self.__exec(cmd, max_timeout)

    def __rsync(self, pattern, option, src_path, dst_path, max_timeout, doStrace):
        if not max_timeout or max_timeout <= 0:
            max_timeout = sys.maxint
        if pattern and len(pattern) > 0:
            cmd = 'rsync --progress --include=%s -f "- *" %s --timeout %s %s %s@%s#%s:%s' % \
                    (pattern, option, max_timeout, src_path, self._user, self._host, self._port, dst_path)
        else:
            cmd = 'rsync --progress  %s --timeout %s %s %s@%s#%s:%s' % \
                    (option, max_timeout, src_path, self._user, self._host, self._port,dst_path)
        return self.__exec(cmd, max_timeout)
        

    def scp(self, src, dst, max_timeout=600):
        """max_timeout set to None means timeout is invalid"""
        return self.__scp(src, dst, max_timeout)

    def ssh_cmd(self, command, max_timeout=600, doStrace=False):
        """max_timeout set to None means timeout is invalid"""
        return self.__ssh_command(command, max_timeout, doStrace)

    def rsync(self, src_path, dst_path, pattern=None, option="-auz", max_timeout=600, doStrace=False):
        return self.__rsync(pattern, option, src_path, dst_path, max_timeout, doStrace)
