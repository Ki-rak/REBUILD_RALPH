"""Native process ownership proof for the real-browser verifier, no network/keys."""
import ctypes
import os
import shutil
import subprocess
import pytest
from ops.demo_browser_verify import stop_browser_process


@pytest.mark.skipif(os.name!='nt',reason='Windows native process tree contract')
def test_owned_node_and_browser_helper_descendant_are_reaped():
    node=shutil.which('node');assert node
    script="const c=require('child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{windowsHide:true,stdio:'ignore'});console.log(c.pid);setInterval(()=>{},1000);"
    process=subprocess.Popen([node,'-e',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=None
    try:
        descendant=int(process.stdout.readline().strip())
        handle=kernel.OpenProcess(0x00100000,False,descendant);assert handle
        stop_browser_process(process)
        assert process.poll() is not None
        assert kernel.WaitForSingleObject(handle,5000)==0,'Owned descendant must have exited'
    finally:
        if process.poll() is None:stop_browser_process(process)
        if handle:kernel.CloseHandle(handle)
