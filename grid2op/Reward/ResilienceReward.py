# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Grid2Op, Grid2Op a testbed platform to model sequential decision making in power systems.

from multiprocessing.sharedctypes import RawArray
import numpy as np
from grid2op.Reward.BaseReward import BaseReward
from grid2op.dtypes import dt_float
import networkx as nx


class ResilienceReward(BaseReward):
    """
    This reward aims to reflect the degree of resilience of the network.

    The margin is defined, for each powerline as:
    `margin of a powerline = (thermal limit - flow in amps) / thermal limit`
    (if flow in amps <= thermal limit) else `margin of a powerline  = 0.`

    This rewards is then: `sum (margin of this powerline) ^ 2`, for each powerline.


    Examples
    ---------
    You can use this reward in any environment with:

    .. code-block:

        import grid2op
        from grid2op.Reward import L2RPNReward

        # then you create your environment with it:
        NAME_OF_THE_ENVIRONMENT = "rte_case14_realistic"
        env = grid2op.make(NAME_OF_THE_ENVIRONMENT,reward_class=L2RPNReward)
        # and do a step with a "do nothing" action
        obs = env.reset()
        obs, reward, done, info = env.step(env.action_space())
        # the reward is computed with the L2RPNReward class

    """
    def __init__(self):
        BaseReward.__init__(self)
        self._lambda = 1e3
        self.eps = 1e3

        self.min_pen_lte = dt_float(0)
        self.max_pen_gte = dt_float(10)

    def initialize(self, env):
        self.isolated_penalty_multiplier = 1
        self.reward_min = 0.0
        self.reward_illegal = -1.0
        self.reward_max = dt_float(env.backend.n_line)

    def __call__(self, action, env, has_error, is_done, is_illegal, is_ambiguous):
        if has_error:
           if is_illegal or is_ambiguous:
               return self.reward_illegal
           elif is_done:
               return self.reward_min
        
        # Get info from env
        obs = env.current_obs
        n_line = obs.n_line
        
        n_sub = obs.n_sub
        topo = obs.topo_vect
        or_topo = obs.line_or_pos_topo_vect
        ex_topo = obs.line_ex_pos_topo_vect
        or_sub = obs.line_or_to_subid
        ex_sub = obs.line_ex_to_subid
        
        conn_line = 0

        # # Create a graph of vertices
        # # Use one vertex per substation per bus
        # G = nx.Graph()
        
        # # Set lines edges for current bus
        for line_idx in range(n_line):
            # Skip if line is disconnected
            if obs.line_status[line_idx] == False:
                continue
            # Get substation index for current line
            conn_line += 1
            # lor_sub = or_sub[line_idx]
            # lex_sub = ex_sub[line_idx]
            # # Get the buses for current line
            # lor_bus = topo[or_topo[line_idx]]
            # lex_bus = topo[ex_topo[line_idx]]

            # if lor_bus <= 0 or lex_bus <= 0:
            #     continue

            # # Compute edge vertices indices for current graph
            # left_v =  lor_sub + (lor_bus - 1) * n_sub
            # right_v = lex_sub + (lex_bus - 1) * n_sub

            # # Register edge in graph
            # G.add_edge(left_v, right_v)
            
        # # Find the bridges
        # n_bridges = dt_float(len(list(nx.bridges(G))))

        # # Clip to min penalty
        # n_bridges = max(n_bridges, self.min_pen_lte)
        # # Clip to max penalty
        # n_bridges = min(n_bridges, self.max_pen_gte)
        
        # bridge_penalty = self.c_B * np.interp(n_bridges,
        #               [self.min_pen_lte, self.max_pen_gte],
        #               [1, 0])
        # gen_p, *_ = env.backend.generators_info()
        # load_p, *_ = env.backend.loads_info()
        # power_sat_reward = self.c_P * (load_p.sum() / gen_p.sum() * 10. - 9.) * 0.1 # avg ~ 0.01
        # assert(gen_p.sum() > 0)
        # reward = bridge_penalty + power_sat_reward

        # reward *= (conn_line / n_line)   # powerline integrity of the network
        # assert(n_line > 0)
        # # topological integrity of the network
        # reward /= env.backend.get_num_islands()
        # assert(env.backend.get_num_islands() > 0)

        # TESTING ZHIYAO'S REWARD FUNCTION
        LC = (conn_line / n_line)
        actual_load = env.current_obs.load_p

        # load_diff_p = env._load_difference()
        if env._new_load is None:
            LS = 0
        else:
            scheduled_load = env._new_load
            LS = np.sum(actual_load) / np.sum(scheduled_load)
        OC = np.sum(env.gen_cost_per_MW * env._p_difference())
        reward = self._lambda * LS + self.eps * LC
        # reward -= self.isolated_penalty_multiplier * env.backend.get_num_isolated()

        # print(f"\t env.backend.get_line_flow(): {env.backend.get_line_flow()}")
        return reward

    @staticmethod
    def __get_lines_capacity_usage(env):
        ampere_flows = np.abs(env.backend.get_line_flow(), dtype=dt_float)
        thermal_limits = np.abs(env.get_thermal_limit(), dtype=dt_float)
        thermal_limits += 1e-1  # for numerical stability
        relative_flow = np.divide(ampere_flows, thermal_limits, dtype=dt_float)

        x = np.minimum(relative_flow, dt_float(1.0))
        lines_capacity_usage_score = np.maximum(dt_float(1.0) - x ** 2, np.zeros(x.shape, dtype=dt_float))
        return lines_capacity_usage_score
