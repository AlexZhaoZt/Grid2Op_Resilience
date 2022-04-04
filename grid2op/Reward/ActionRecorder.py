# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Grid2Op, Grid2Op a testbed platform to model sequential decision making in power systems.

import numpy as np

from grid2op.Exceptions import Grid2OpException
from grid2op.Reward.BaseReward import BaseReward
from grid2op.dtypes import dt_float


class ActionRecorder(BaseReward):
    """
    Not a real reward just a hack to record actions in {other_rewards}
    """
    def __init__(self):
        BaseReward.__init__(self)

    def initialize(self, env):
        if not env.redispatching_unit_commitment_availble:
            raise Grid2OpException("Impossible to use the ActionRecorder reward with an environment without generators"
                                   "cost. Please make sure env.redispatching_unit_commitment_availble is available.")
    def __call__(self, action, env, has_error, is_done, is_illegal, is_ambiguous):
        return {"set_bus": action.set_bus, "set_line": action.set_line_status}
