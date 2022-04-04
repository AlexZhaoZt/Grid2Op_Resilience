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


class GridIntegrityMetric(BaseReward):
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

    def initialize(self, env):
        pass

    def __call__(self, action, env, has_error, is_done, is_illegal, is_ambiguous):
        if has_error:
           if is_illegal or is_done:
               return -1

        num_islands = env.backend.get_num_islands()
        
        return num_islands
