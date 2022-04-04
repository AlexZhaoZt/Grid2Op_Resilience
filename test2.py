# %%
import sys
sys.path.insert(0, "/home/bugting/my_pandapower")
import networkx
import numpy as np
import grid2op
print('Running Grid2Op with version:')
print(grid2op.__version__)
from tqdm.notebook import tqdm  # for easy progress bar
display_tqdm = False  # this is set to False for ease with the unitt test, feel free to set it to True
from grid2op.PlotGrid import PlotMatplot
from grid2op.Agent import DoNothingAgent
from grid2op.Parameters import Parameters
# %%
# initialize
p = Parameters()
p.ENV_DC = True
# env = grid2op.make("rte_case14_realistic", action_class=grid2op.Action.CompleteAction, param=p)
env = grid2op.make("rte_case14_realistic", param=p)
# env = grid2op.make("rte_case5_example", test=True, param=p)
# env = grid2op.make("rte_case14_opponent", test=True, param=p)
# %%
# plot grid
line_ids = [int(i) for i in range(env.n_line)]
plot_helper = PlotMatplot(env.observation_space)
# plot_helper.plot_info(gen_values=env.gen_pmax)
plot_helper.plot_info(line_values=env.action_space().name_line)
# plot_helper.plot_info(load_values=[el for el in range(env.n_load)])
# plot_helper.plot_layout()
# %%
# plot_helper.plot_info(load_values=[el for el in range(env.n_load)])
plot_helper.plot_info(gen_values=env.gen_pmax)
my_agent = DoNothingAgent(env.action_space)
done = False
time_step = int(0)
cum_reward = 0.
obs = env.reset()
obs_arr = []

obs_arr.append(obs)
fig = plot_helper.plot_obs(obs_arr[-1])


def disconnect_bus_0():
    set_status = env.action_space.disconnect_powerline(line_name='0_1_0')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])

    set_status = env.action_space.disconnect_powerline(line_name='0_4_1')
    obs, _, _, _ = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])

def disconnect_bus_4():
    set_status = env.action_space.disconnect_powerline(line_name='4_5_17')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])

    set_status = env.action_space.disconnect_powerline(line_name='0_4_1')
    obs, _, _, _ = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])

    set_status = env.action_space.disconnect_powerline(line_name='3_4_6')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])

    set_status = env.action_space.disconnect_powerline(line_name='1_4_4')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])

def termination_test():
    set_status = env.action_space.disconnect_powerline(line_name='4_5_17')
    set_status = env.action_space.disconnect_powerline(line_name='0_4_1', previous_action=set_status)
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space.disconnect_powerline(line_name='0_4_1')
    obs, _, _, _ = env.step(set_status)
    obs_arr.append(obs) 
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
    set_status = env.action_space.disconnect_powerline(line_name='3_4_6')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
    set_status = env.action_space.disconnect_powerline(line_name='1_4_4')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
    set_status = env.action_space.disconnect_powerline(line_name='9_10_12')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
    set_status = env.action_space.disconnect_powerline(line_name='5_10_7')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
    set_status = env.action_space.disconnect_powerline(line_name='6_7_18')
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

def do_nothing_test():
    act = env.action_space()

    for _ in range(10):
        obs, _, _, info = env.step(act)
        print(info)
        obs_arr.append(obs)
        fig = plot_helper.plot_obs(obs_arr[-1])

def busbar_test():

    # print(env.backend.get_topo_vect().shape)
    # print(obs.topo_vect)
    print(env.backend._grid['_isolated_buses'])
    set_status = env.action_space()
    set_status.change_bus = 0
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    print(env.backend._grid['_isolated_buses'])

    set_status = env.action_space()
    set_status.change_bus = 1
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 1
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 0
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 1
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 2
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 3
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 4
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 5
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 0
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
    print('HERE')
    set_status = env.action_space()
    set_status.change_bus = 6
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

    set_status = env.action_space()
    set_status.change_bus = 7
    obs, _, _, info = env.step(set_status)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)

def off_line_test():
    act = env.action_space()
    act.set_line_status = ([(3, -1), (5, -1), (16, -1), (4, -1), (7, -1)])
    obs, _, _, info = env.step(act)
    obs_arr.append(obs)
    fig = plot_helper.plot_obs(obs_arr[-1])
    print(info)
# busbar_test()

termination_test()
# do_nothing_test()
# off_line_test()
# %%
