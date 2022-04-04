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


class ResponseQualityMetric(BaseReward):
    def __init__(self):
        BaseReward.__init__(self)

    def __call__(self, action, env, has_error,
                 is_done, is_illegal, is_ambiguous):
        if has_error or is_illegal or is_ambiguous:
            return -1

        # Get obs from env
        obs = env.get_obs()

        # All lines ids
        lines_id = np.arange(env.n_line)
        lines_id = lines_id[obs.time_before_cooldown_line == 0]

        n_lines = dt_float(0.0)
        for line_id in lines_id:
            # Line could be reconnected but isn't
            if obs.line_status[line_id] == False:
                n_lines += dt_float(1.0)

        return n_lines