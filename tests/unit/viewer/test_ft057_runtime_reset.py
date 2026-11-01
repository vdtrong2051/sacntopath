"""FT-05.7 VTK bridge reset discards prior RGB without blocking Qt."""
from concurrent.futures import Future
import time
from scantopath.modules.viewer3d.application.live_3d_runtime import Live3DRenderWorker


def until(test,limit=3):
    end=time.monotonic()+limit
    while time.monotonic()<end:
        if test():return True
        time.sleep(.005)
    return False

class Session:
    def __init__(self):self.stopped=False
    def start(self):
        f=Future();f.set_result(True);return f
    def begin_live_cloud(self,**kwargs):
        f=Future();f.set_result(True);return f
    def next_frame(self,*,timeout):
        time.sleep(.004)
        raise TimeoutError('no frame')
    def stop(self,*,timeout):self.stopped=True


def test_ft057_scope_epoch_recreates_session_and_cleanup():
    sessions=[]
    def factory():
        obj=Session();sessions.append(obj);return obj
    w=Live3DRenderWorker(session_factory=factory)
    w.start()
    try:
        w.change_generation(1)
        assert until(lambda: w.statistics()['session_starts']>=1)
        first=sessions[-1]
        w.invalidate_scene()
        assert until(lambda: w.statistics()['session_starts']>=2)
        assert first.stopped
        assert w.statistics()['pending_rgb']==0
        assert w.statistics()['desired_generation']==1
    finally:
        w.request_stop()
        assert until(lambda: w.stopped)
    assert all(s.stopped for s in sessions)
