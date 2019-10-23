import roboverse
import numpy as np
import time
import roboverse.utils as utils

env = roboverse.make('SawyerGraspOne-v0', render=False)

num_grasps = 0
save_video = False

for j in range(100):
    env.reset()
    target_pos = env.get_object_midpoint('duck')
    target_pos += np.random.uniform(low=-0.05, high=0.05, size=(3,))
    images = []

    for i in range(100):

        ee_pos = env.get_end_effector_pos()

        if i < 50:
            action = target_pos - ee_pos
            action[2] = 0.
            action *= 3.0
            grip=0.
        elif i < 70:
            action = target_pos - ee_pos
            action *= 3.0
            action[2] *= 2.0
            grip=0.
        elif i < 85:
            action = np.zeros((3,))
            grip=1.
        else:
            action = np.zeros((3,))
            action[2] = 1.0
            grip=1.

        if save_video:
            img = env.render()
            images.append(img)

        env.step(action, grip)

    object_pos = env.get_object_midpoint('duck')
    if object_pos[2] > -0.1:
        num_grasps += 1

    if save_video:
        utils.save_video('dump/grasp_duck_randomized/{}.avi'.format(j), images)

    print('\nNum attempts: {}'.format(j))
    print('Num grasps: {}'.format(num_grasps))

