"""Windows Unicode ShellLink/known-folder calls using documented COM interfaces."""
import ctypes as C
from pathlib import Path
from uuid import UUID

PTR=C.c_void_p
WSTR=C.c_wchar_p
DWORD=C.c_ulong
HRESULT=C.c_long

def guid(value):return (C.c_ubyte*16).from_buffer_copy(UUID(value).bytes_le)

def checked(result):
    if result<0:raise OSError('Windows Shell接口失败 HRESULT 0x%08x'%(result & 0xffffffff))

def call(pointer,index,types,*args):
    table=C.cast(pointer,C.POINTER(C.POINTER(PTR))).contents
    checked(C.WINFUNCTYPE(HRESULT,PTR,*types)(table[index])(pointer,*args))

def release(pointer):
    if pointer:
        table=C.cast(pointer,C.POINTER(C.POINTER(PTR))).contents
        C.WINFUNCTYPE(DWORD,PTR)(table[2])(pointer)

def shortcut(path,write=False,target=None,arguments=None,cwd=None):
    ole=C.OleDLL('ole32')
    ole.CoInitializeEx.argtypes=[PTR,DWORD];ole.CoInitializeEx.restype=HRESULT
    checked(ole.CoInitializeEx(None,2))
    link=PTR();persist=PTR()
    try:
        cls=guid('00021401-0000-0000-c000-000000000046')
        iid=guid('000214f9-0000-0000-c000-000000000046')
        ole.CoCreateInstance.argtypes=[PTR,PTR,DWORD,PTR,C.POINTER(PTR)];ole.CoCreateInstance.restype=HRESULT
        checked(ole.CoCreateInstance(C.byref(cls),None,1,C.byref(iid),C.byref(link)))
        iid_file=guid('0000010b-0000-0000-c000-000000000046')
        call(link,0,[PTR,C.POINTER(PTR)],C.byref(iid_file),C.byref(persist))
        if write:
            for index,value in [(20,target),(11,arguments),(9,cwd),(7,'Luxixi local page service')]:call(link,index,[WSTR],value)
            call(link,15,[C.c_int],7)
            call(persist,6,[WSTR,C.c_int],str(path),1)
        else:
            call(persist,5,[WSTR,DWORD],str(path),0)
        result={}
        for name,index in [('target',3),('arguments',10),('cwd',8)]:
            buffer=C.create_unicode_buffer(32768)
            if name=='target':call(link,index,[WSTR,C.c_int,PTR,DWORD],buffer,len(buffer),None,4)
            else:call(link,index,[WSTR,C.c_int],buffer,len(buffer))
            result[name]=buffer.value
        return result
    finally:
        release(persist);release(link);ole.CoUninitialize()

def startup_directory():
    folder=guid('b97d20bb-f46a-4c97-ba10-5e3608430854');value=PTR()
    shell=C.WinDLL('shell32');ole=C.OleDLL('ole32')
    shell.SHGetKnownFolderPath.argtypes=[PTR,DWORD,PTR,C.POINTER(PTR)];shell.SHGetKnownFolderPath.restype=HRESULT
    checked(shell.SHGetKnownFolderPath(C.byref(folder),0,None,C.byref(value)))
    try:return Path(C.wstring_at(value))
    finally:
        ole.CoTaskMemFree.argtypes=[PTR];ole.CoTaskMemFree(value)
