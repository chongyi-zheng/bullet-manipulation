import numpy as np
import pdb

import pybullet as p
import roboverse.bullet as bullet
from roboverse.envs.sawyer_base import SawyerBaseEnv

class SawyerLiftMultiEnv(SawyerBaseEnv):

    def __init__(self, goal_pos=None, *args, goal_mult=4, bonus=0, min_reward=-3.,
                 num_obj=2, **kwargs):
        self.record_args(locals())
        self._goal_pos = goal_pos
        self._goal_mult = goal_mult
        self._bonus = bonus
        self._min_reward = min_reward
        self._id = 'SawyerLiftMultiEnv'
        self.num_obj = num_obj
        super().__init__(*args, **kwargs)

    def get_params(self):
        params = super().get_params()
        return params

    def _load_meshes(self):
        super()._load_meshes()
        self._objects.update({
            'bowl':  bullet.objects.bowl(),
            # 'lid': bullet.objects.lid(),
        })
        colors = [
            [1, 0, 0, 1],
            [0, 1, 0, 1],
            [0, 0, 1, 1],
            [1, 1, 0, 1],
            [1, 1, 1, 1],
            [0, 0, 0, 1],
        ]
        for obj_id in range(self.num_obj):
            obj_name = self.get_obj_name(obj_id)
            # obj = bullet.objects.spam()
            obj = bullet.objects.spam_objs[obj_id]()

            numJoints = p.getNumJoints(obj)
            p.changeVisualShape(obj, numJoints-1, rgbaColor=colors[obj_id])
            p.setJointMotorControl2(obj, numJoints-1, p.VELOCITY_CONTROL, force=0)

            self._objects[obj_name] = obj

    def get_object_positions(self):
        bodies = sorted([v for k, v in self._objects.items() if not bullet.has_fixed_root(v)])
        obj_pos = []
        for body in bodies:
            link = bullet.get_index_by_attribute(body, 'link_name', 'spam')
            self._format_state_query()
            state = bullet.get_link_state(body, link, ['pos', 'theta'])
            obj_pos.append(state['pos'])
        return obj_pos

    def get_reward(self, observation):
        """Dummy reward for sawyer lift multi env
        """
        reward = 1
        return reward


    def get_obj_name(self, cube_id):
        return 'cube_{cube_id}'.format(cube_id=cube_id)
