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


class GenDiffMetric(BaseReward):

    def __init__(self):
        BaseReward.__init__(self)
        
    def initialize(self, env):
        pass

    def __call__(self, action, env, has_error, is_done, is_illegal, is_ambiguous):
        if is_illegal or is_done:
            return 0
            
        gen_p, *_ = env.backend.generators_info()
        gen_diff_p = env._p_difference()
        gen_diff_p = gen_diff_p / np.sum(gen_p)

        return gen_diff_p
