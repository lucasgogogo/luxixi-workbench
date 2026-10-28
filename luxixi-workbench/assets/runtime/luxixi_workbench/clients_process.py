"""Bounded stdout/stderr and cleanup of this invocation only (no name-based kills)."""
import ctypes
import os
import signal
import subprocess
import threading
import time

class WindowsJob:
    def __init__(self):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active_limit',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):_fields_=[(x,ctypes.c_ulonglong) for x in ['reads','writes','other','read_bytes','write_bytes','other_bytes']]
        class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        class Accounting(ctypes.Structure):_fields_=[(x,ctypes.c_longlong) for x in ['user','kernel','period_user','period_kernel']]+[(x,w.DWORD) for x in ['faults','total','active','terminated']]
        self.accounting=Accounting;self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        declarations={'CreateJobObjectW':([ctypes.c_void_p,w.LPCWSTR],w.HANDLE),'SetInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL),'QueryInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p],w.BOOL),'CloseHandle':([w.HANDLE],w.BOOL)}
        for name,(args,result) in declarations.items():getattr(self.api,name).argtypes=args;getattr(self.api,name).restype=result
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        info=Extended();info.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            self.close();raise ctypes.WinError(ctypes.get_last_error())
    def assign(self,child):
        if not self.api.AssignProcessToJobObject(self.handle,int(child._handle)):raise ctypes.WinError(ctypes.get_last_error())
    def resume(self,child):
        # Popen closes the primary thread handle. Find only this suspended PID's
        # thread, validate ownership, and resume after assignment to our job.
        from ctypes import wintypes as w
        class ThreadEntry(ctypes.Structure):
            _fields_=[('size',w.DWORD),('usage',w.DWORD),('tid',w.DWORD),('pid',w.DWORD),('base',w.LONG),('delta',w.LONG),('flags',w.DWORD)]
        declarations={'CreateToolhelp32Snapshot':([w.DWORD,w.DWORD],w.HANDLE),'Thread32First':([w.HANDLE,ctypes.POINTER(ThreadEntry)],w.BOOL),'Thread32Next':([w.HANDLE,ctypes.POINTER(ThreadEntry)],w.BOOL),'OpenThread':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'GetProcessIdOfThread':([w.HANDLE],w.DWORD),'ResumeThread':([w.HANDLE],w.DWORD)}
        for name,(args,result) in declarations.items():getattr(self.api,name).argtypes=args;getattr(self.api,name).restype=result
        snapshot=self.api.CreateToolhelp32Snapshot(4,0)
        if snapshot in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
        try:
            item=ThreadEntry();item.size=ctypes.sizeof(item);ok=self.api.Thread32First(snapshot,ctypes.byref(item))
            while ok:
                if item.pid==child.pid:
                    handle=self.api.OpenThread(0x0802,False,item.tid)
                    if not handle:raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.api.GetProcessIdOfThread(handle)!=child.pid:raise OSError('thread ownership changed')
                        if self.api.ResumeThread(handle)!=1:raise OSError('primary thread was not suspended exactly once')
                        return
                    finally:self.api.CloseHandle(handle)
                ok=self.api.Thread32Next(snapshot,ctypes.byref(item))
            raise OSError('suspended primary thread not found')
        finally:self.api.CloseHandle(snapshot)
    def stop(self):
        self.api.TerminateJobObject(self.handle,1)
        until=time.monotonic()+3
        while time.monotonic()<until:
            info=self.accounting()
            if self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None) and info.active==0:return True
            time.sleep(.02)
        return False
    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None

def execute(args,instruction,cwd,env,timeout,run_root,output_limit=8*1024*1024):
    if output_limit<1024:raise ValueError('输出上限无效')
    handles=[];child=None;job=None;assigned=False;threads=[];lock=threading.Lock();overflow=threading.Event();used=0;reader_failed=threading.Event()
    timed_out=False;tree_confirmed=False;cleanup_error=None;started=time.monotonic()
    def drain(pipe,file):
        nonlocal used
        try:
            while True:
                chunk=pipe.read(4096)
                if not chunk:break
                with lock:
                    take=max(0,min(len(chunk),output_limit-used));used+=take
                    if take<len(chunk):overflow.set()
                if take:file.write(chunk[:take]);file.flush()
        except (OSError,ValueError):reader_failed.set()
        finally:pipe.close()
    try:
        # Exclusive files are opened before the native process can write any output.
        for name in ['stdout.jsonl','stderr.txt']:handles.append((run_root/name).open('xb'))
        if os.name=='nt':job=WindowsJob()
        options={'creationflags':subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP|0x00000004} if os.name=='nt' else {'start_new_session':True}
        child=subprocess.Popen(args,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,**options)
        if job:job.assign(child);assigned=True;job.resume(child)
        for pipe,file in zip([child.stdout,child.stderr],handles):
            thread=threading.Thread(target=drain,args=(pipe,file),daemon=True);thread.start();threads.append(thread)
        def send_input():
            try:child.stdin.write(instruction.encode('utf-8'));child.stdin.close()
            except (BrokenPipeError,OSError,ValueError):pass
        sender=threading.Thread(target=send_input,daemon=True);sender.start();threads.append(sender)
        while child.poll() is None:
            if overflow.is_set() or reader_failed.is_set():break
            if time.monotonic()-started>=timeout:timed_out=True;break
            time.sleep(.03)
    finally:
        # Job handles identify our tree even after the leader exits; no process-name lookup.
        if job:
            try:tree_confirmed=job.stop() and assigned
            except Exception as error:cleanup_error=type(error).__name__
            finally:job.close()
        elif child and child.poll() is None:
            try:
                os.killpg(child.pid,signal.SIGTERM)
                time.sleep(.1)
                os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except OSError as error:cleanup_error=type(error).__name__
        if child:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill();child.wait(timeout=5)
            if child.stdin and not child.stdin.closed:child.stdin.close()
        for thread in threads:thread.join(timeout=3)
        for file in handles:
            if not file.closed:file.flush();os.fsync(file.fileno());file.close()
    return {'exit_code':child.returncode if child else None,'timed_out':timed_out,'output_limit_exceeded':overflow.is_set(),'output_bytes':used,'reader_failed':reader_failed.is_set(),'process_exited':child is not None and child.poll() is not None,'tree_cleanup_confirmed':tree_confirmed,'tree_cleanup_error':cleanup_error}
