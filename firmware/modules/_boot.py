import esp
esp.osdebug(None)
esp.sleep_type(esp.SLEEP_MODEM)

import gc
gc.threshold((gc.mem_free() + gc.mem_alloc()) // 4)
import uos
from flashbdev import bdev

try:
    if bdev:
        uos.mount(bdev, '/')
except OSError:
    import inisetup
    inisetup.setup()

gc.collect()

import fcb
fc = fcb.FCB()
# fc.start()
