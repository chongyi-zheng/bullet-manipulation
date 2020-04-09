import time
import numpy as np
import pdb

import roboverse.bullet as bullet
import roboverse.devices as devices

# space_mouse = devices.SpaceMouse()
# space_mouse.start_control()

bullet.connect()
bullet.setup()

## load meshes
table = bullet.objects.table()
# spam = bullet.objects.spam()
# box = bullet.objects.box()
# hinge = bullet.objects.hinge()
w200 = bullet.objects.widowx_200()

while True:
    time.sleep(0.01)
    bullet.step()
