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

def test_readiness_bound_is_finite_and_explicit():
    from ops.demo_live_verify import OwnedServer
    assert OwnedServer('test-run',8793).readiness_timeout == 60
    assert OwnedServer('test-run',8793,readiness_timeout=240).readiness_timeout == 240
    for invalid in (0,241,float('inf'),True):
        with pytest.raises(ValueError,match='INVALID_SERVER_READINESS_BOUND'):
            OwnedServer('test-run',8793,readiness_timeout=invalid)

@pytest.mark.skipif(os.name!='nt',reason='Windows server wrapper process tree contract')
def test_owned_server_stop_reaps_interpreter_descendant():
    from ops.demo_live_verify import OwnedServer
    node=shutil.which('node');assert node
    script="const c=require('child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{windowsHide:true,stdio:'ignore'});console.log(c.pid);setInterval(()=>{},1000);"
    process=subprocess.Popen([node,'-e',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=None;descendant=None
    try:
        descendant=int(process.stdout.readline().strip())
        handle=kernel.OpenProcess(0x00100000,False,descendant);assert handle
        server=OwnedServer('test-run',8793);server.process=process
        server.stop()
        assert process.poll() is not None
        assert kernel.WaitForSingleObject(handle,3000)==0,'Owned interpreter descendant must have exited'
    finally:
        if process.poll() is None:stop_browser_process(process)
        if handle and kernel.WaitForSingleObject(handle,0)!=0:
            subprocess.run(['taskkill','/PID',str(descendant),'/T','/F'],capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        if handle:kernel.CloseHandle(handle)

def test_owned_server_rejects_existing_listener_without_starting_process():
    import socket
    from ops.demo import DemoError
    from ops.demo_live_verify import OwnedServer
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen(1)
        server=OwnedServer('test-run',listener.getsockname()[1])
        with pytest.raises(DemoError,match='OWNED_SERVER_PORT_IN_USE'):
            server.start()
        assert server.process is None
