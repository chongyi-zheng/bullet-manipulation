import roboverse.bullet as bullet
import numpy as np
import roboverse.utils as utils
from roboverse.envs.sawyer_base import SawyerBaseEnv
from roboverse.envs.widowx200_grasp import WidowX200GraspEnv
import gym
from roboverse.bullet.misc import load_obj
import os.path as osp
import pickle

REWARD_NEGATIVE = -1.0
REWARD_POSITIVE = 10.0
SHAPENET_ASSET_PATH = osp.join(
    osp.dirname(osp.abspath(__file__)), 'assets/ShapeNetCore')


def load_shapenet_object(object_path, scaling, object_position, scale_local=0.5):
    path = object_path.split('/')
    dir_name = path[-2]
    object_name = path[-1]
    obj = load_obj(
        SHAPENET_ASSET_PATH + '/ShapeNetCore_vhacd/{0}/{1}/model.obj'.format(
            dir_name, object_name),
        SHAPENET_ASSET_PATH + '/ShapeNetCore.v2/{0}/{1}/models/model_normalized.obj'.format(
            dir_name, object_name),
        object_position,
        [1, -1, 0, 0], # this rotates objects 90 degrees. Originally: [0, 0, 1, 0]
        scale=scale_local*scaling[
            '{0}/{1}'.format(dir_name, object_name)])
    return obj


class Widow200GraspV2Env(WidowX200GraspEnv):
    def __init__(self,
                 *args,
                 observation_mode='state',
                 transpose_image=False,
                 reward_type=False,  # Not actually used
                 randomize=True,  # Not actually used
                 **kwargs):


        self._object_position_high = (.82, .075, -.20)
        self._object_position_low = (.78, -.125, -.20)
        self._num_objects = 1
        self.object_ids = [[0, 1, 25, 30, 50, 215, 255, 265, 300, 310][1]]
        shapenet_data = pickle.load(
            open(osp.join(SHAPENET_ASSET_PATH, 'metadata.pkl'), 'rb'))
        self.object_list = shapenet_data['object_list']
        self.scaling = shapenet_data['scaling']
        self._scaling_local = [0.5]*10
        self._observation_mode = observation_mode
        self._transpose_image = transpose_image

        super().__init__(*args, **kwargs)

        self._env_name = 'Widow200GraspV2Env'
        self._height_threshold = -0.31
        self._reward_height_thresh = -0.3
        self._max_force = 10000
        
    def _load_meshes(self):
        super()._load_meshes()
        self._tray = bullet.objects.widow200_tray()

        self._objects = {}
        self._sensors = {}
        self._workspace = bullet.Sensor(self._robot_id,
            xyz_min=self._pos_low, xyz_max=self._pos_high,
            visualize=False, rgba=[0,1,0,.1])

        import scipy.spatial
        min_distance_threshold = 0.12
        object_positions = np.random.uniform(
            low=self._object_position_low, high=self._object_position_high)
        object_positions = np.reshape(object_positions, (1,3))
        while object_positions.shape[0] < self._num_objects:
            object_position_candidate = np.random.uniform(
                low=self._object_position_low, high=self._object_position_high)
            object_position_candidate = np.reshape(
                object_position_candidate, (1,3))
            min_distance = scipy.spatial.distance.cdist(
                object_position_candidate, object_positions)
            if (min_distance > min_distance_threshold).any():
                object_positions = np.concatenate(
                    (object_positions, object_position_candidate), axis=0)

        assert len(self.object_ids) >= self._num_objects
        import random
        indexes = list(range(self._num_objects))
        random.shuffle(indexes)
        for idx in indexes:
            key_idx = self.object_ids.index(self.object_ids[idx])
            self._objects[key_idx] = load_shapenet_object(
                self.object_list[self.object_ids[idx]], self.scaling,
                object_positions[idx], scale_local=self._scaling_local[idx])
            for _ in range(10):
                bullet.step()

    def step(self, *action):
        delta_pos, gripper = self._format_action(*action)
        pos = bullet.get_link_state(self._robot_id, self._end_effector, 'pos')
        pos += delta_pos[:3] * self._action_scale
        pos = np.clip(pos, self._pos_low, self._pos_high)
        # theta = bullet.quat_to_deg(self.theta)
        joints, current = bullet.get_joint_positions(self._robot_id)
        wrist_theta = current[4]
        wrist_theta_step_multiplier = 1

        # print("delta_pos", delta_pos)
        # print("gripper", gripper)
        # print("action", action)
        # print("self.theta", self.theta)
        if len(delta_pos) > 3:
            delta_wrist_theta = delta_pos[3]
            # print("delta_theta", delta_theta)
            # target_theta = theta + np.asarray([0., 0., 20*delta_theta])
            # target_theta = np.clip(target_theta, [180, 0., 0.], [180, 0., 180.])
            # target_theta = bullet.deg_to_quat(target_theta)
            # print("target_theta", target_theta)
        else:
            delta_wrist_theta = 0
            # target_theta = self.theta

        print("wrist_theta before", wrist_theta)
        wrist_theta = wrist_theta + wrist_theta_step_multiplier * delta_wrist_theta
        wrist_theta = np.clip(wrist_theta, -np.pi, np.pi)
        print("wrist_theta after", wrist_theta)

        gripper = -0.8

        self._simulate(pos, self.theta, gripper, wrist_theta)
        # if self._visualize: self.visualize_targets(pos)

        pos = bullet.get_link_state(self._robot_id, self._end_effector, 'pos')
        if pos[2] < self._height_threshold:
            gripper = 0.8
            for i in range(10):
                self._simulate(pos, target_theta, gripper)
            for i in range(50):
                pos = bullet.get_link_state(self._robot_id, self._end_effector, 'pos')
                pos = list(pos)
                pos = np.clip(pos, self._pos_low, self._pos_high)
                pos[2] += 0.05
                self._simulate(pos, target_theta, gripper)
            done = True
            reward = self.get_reward({})
            if reward > 0:
                info = {'grasp_success': 1.0}
            else:
                info = {'grasp_success': 0.0}
        else:
            done = False
            reward = REWARD_NEGATIVE
            info = {'grasp_success': 0.0}

        observation = self.get_observation()
        self._prev_pos = bullet.get_link_state(self._robot_id, self._end_effector, 'pos')
        return observation, reward, done, info

    def _simulate(self, pos, theta, gripper, wrist_theta, discrete_gripper=True):
        for _ in range(self._action_repeat):
            bullet.sawyer_position_theta_ik(	
                self._robot_id, self._end_effector,
                pos, self.theta,
                gripper, wrist_theta,
                gripper_name=self._gripper_joint_name, gripper_bounds=self._gripper_bounds,
                discrete_gripper=discrete_gripper, max_force=self._max_force
            )
            bullet.step_ik(self._gripper_range)

    def get_observation(self):
        left_tip_pos = bullet.get_link_state(
            self._robot_id, self._gripper_joint_name[0], keys='pos')
        right_tip_pos = bullet.get_link_state(
            self._robot_id, self._gripper_joint_name[1], keys='pos')
        left_tip_pos = np.asarray(left_tip_pos)
        right_tip_pos = np.asarray(right_tip_pos)

        gripper_tips_distance = [np.linalg.norm(
            left_tip_pos - right_tip_pos)]
        end_effector_pos = self.get_end_effector_pos()
        end_effector_theta = bullet.get_link_state(
            self._robot_id, self._end_effector, 'theta', quat_to_deg=False)

        if self._observation_mode == 'state':
            observation = np.concatenate(
                (end_effector_pos, end_effector_theta, gripper_tips_distance))
            # object_list = self._objects.keys()
            for object_name in range(self._num_objects):
                object_info = bullet.get_body_info(self._objects[object_name],
                                                   quat_to_deg=False)
                object_pos = object_info['pos']
                object_theta = object_info['theta']
                observation = np.concatenate(
                    (observation, object_pos, object_theta))
        elif self._observation_mode == 'pixels':
            image_observation = self.render_obs()
            image_observation = np.float32(image_observation.flatten())/255.0
            # image_observation = np.zeros((48, 48, 3), dtype=np.uint8)
            observation = {
                'state': np.concatenate(
                    (end_effector_pos, gripper_tips_distance)),
                'image': image_observation
            }
        elif self._observation_mode == 'pixels_debug':
            # This mode passes in all the true state information + images
            image_observation = self.render_obs()
            image_observation = np.float32(image_observation.flatten())/255.0
            state_observation = np.concatenate(
                (end_effector_pos, end_effector_theta, gripper_tips_distance))

            for object_name in range(self._num_objects):
                object_info = bullet.get_body_info(self._objects[object_name],
                                                   quat_to_deg=False)
                object_pos = object_info['pos']
                object_theta = object_info['theta']
                state_observation = np.concatenate(
                    (state_observation, object_pos, object_theta))
            observation = {
                'state': state_observation,
                'image': image_observation,
            }
        else:
            raise NotImplementedError

        return observation

    def get_info(self):
        info = {'end_effector_pos': self.get_end_effector_pos()}
        for object_name in range(self._num_objects):
             object_info = bullet.get_body_info(self._objects[object_name],
                                                    quat_to_deg=False)
             object_pos = object_info['pos']
             info["object" + str(object_name)] = object_pos

        return info 

    def get_reward(self, info):
        object_list = self._objects.keys()
        reward = REWARD_NEGATIVE
        for object_name in object_list:
            object_info = bullet.get_body_info(self._objects[object_name],
                                               quat_to_deg=False)
            object_pos = np.asarray(object_info['pos'])
            object_height = object_pos[2]
            if object_height > self._reward_height_thresh:
                end_effector_pos = np.asarray(self.get_end_effector_pos())
                object_gripper_distance = np.linalg.norm(
                    object_pos - end_effector_pos)
                if object_gripper_distance < 0.1:
                    reward = REWARD_POSITIVE
        return reward


if __name__ == "__main__":
    import roboverse
    import time

    save_video = True
    images = []

    num_objects = 1
    # env = roboverse.make("SawyerGraspOneV2-v0",
    #                      gui=True,
    #                      observation_mode='state',)
    #                      # num_objects=num_objects)
    env = roboverse.make("Widow200GraspV2-v0", gui=True)
    obs = env.reset()
    # object_ind = np.random.randint(0, env._num_objects)
    object_ind = num_objects - 1
    i = 0
    xy_dist_thresh = 0.02
    action = env.action_space.sample()
    for _ in range(200):
        time.sleep(0.1)
        object_pos = obs[8: 8 + 3]
        # print("obs", obs)
        # print("object_pos", object_pos)
        ee_pos = obs[:3]

        xyz_delta = object_pos - ee_pos
        xy_diff = np.linalg.norm(xyz_delta[:2])
        action = xyz_delta
        if xy_diff > xy_dist_thresh:
            action[2] = 0 # prevent downward motion if too far.
        action = action*4.0
        action += np.random.normal(scale=0.1, size=(3,))

        action = np.array([0,0,0])

        theta_action = 0.1
        # theta_action = 0
        gripper = -1

        action = np.concatenate((action, np.asarray([theta_action, gripper])))
        # print('action', action)
        obs, rew, done, info = env.step(action)

        img = env.render()
        if save_video:
            images.append(img)

        # print("info", env.get_info())
        i+=1
        if done or i > 50:
            # object_ind = np.random.randint(0, env._num_objects)
            object_ind = num_objects - 1
            obs = env.reset()
            i = 0
            print('Reward: {}'.format(rew))
        # print(obs)

    if save_video:
        utils.save_video('data/autograsp.avi', images)

