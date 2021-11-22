# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Grid2Op, Grid2Op a testbed platform to model sequential decision making in power systems.
import os
import copy
import warnings
import numpy as np
import re

import grid2op
from grid2op.dtypes import dt_float, dt_bool, dt_int
from grid2op.Action import ActionSpace, BaseAction, TopologyAction, DontAct, CompleteAction
from grid2op.Exceptions import *
from grid2op.Observation import CompleteObservation, ObservationSpace, BaseObservation
from grid2op.Reward import FlatReward, RewardHelper, BaseReward
from grid2op.Rules import RulesChecker, AlwaysLegal, BaseRules
from grid2op.Backend import Backend
from grid2op.Chronics import ChronicsHandler
from grid2op.VoltageControler import ControlVoltageFromFile, BaseVoltageController
from grid2op.Environment.BaseEnv import BaseEnv
from grid2op.Opponent import BaseOpponent, NeverAttackBudget
from grid2op.operator_attention import LinearAttentionBudget

from grid2op.Backend import PandaPowerBackend


class Environment(BaseEnv):
    """
    This class is the grid2op implementation of the "Environment" entity in the RL framework.

    Attributes
    ----------

    name: ``str``
        The name of the environment

    action_space: :class:`grid2op.Action.ActionSpace`
        Another name for :attr:`Environment.helper_action_player` for gym compatibility.

    observation_space:  :class:`grid2op.Observation.ObservationSpace`
        Another name for :attr:`Environment.helper_observation` for gym compatibility.

    reward_range: ``(float, float)``
        The range of the reward function

    metadata: ``dict``
        For gym compatibility, do not use

    spec: ``None``
        For Gym compatibility, do not use

    viewer: ``object``
        Used to display the powergrid. Currently not supported.

    """

    REGEX_SPLIT = r"^[a-zA-Z0-9]*$"

    def __init__(self,
                 init_grid_path: str,
                 chronics_handler,
                 backend,
                 parameters,
                 name="unknown",
                 names_chronics_to_backend=None,
                 actionClass=TopologyAction,
                 observationClass=CompleteObservation,
                 rewardClass=FlatReward,
                 legalActClass=AlwaysLegal,
                 voltagecontrolerClass=ControlVoltageFromFile,
                 other_rewards={},
                 thermal_limit_a=None,
                 with_forecast=True,
                 epsilon_poly=1e-4,  # precision of the redispatching algorithm we don't recommend to go above 1e-4
                 tol_poly=1e-2,  # i need to compute a redispatching if the actual values are "more than tol_poly" the values they should be
                 opponent_action_class=DontAct,
                 opponent_class=BaseOpponent,
                 opponent_init_budget=0.,
                 opponent_budget_per_ts=0.,
                 opponent_budget_class=NeverAttackBudget,
                 opponent_attack_duration=0,
                 opponent_attack_cooldown=99999,
                 kwargs_opponent={},
                 attention_budget_cls=LinearAttentionBudget,
                 kwargs_attention_budget={},
                 has_attention_budget=False,
                 _raw_backend_class=None,
                 _compat_glop_version=None,
                 _read_from_local_dir=True,  # TODO runner and all here !
                 ):
        BaseEnv.__init__(self,
                         init_grid_path=init_grid_path,
                         parameters=parameters,
                         thermal_limit_a=thermal_limit_a,
                         epsilon_poly=epsilon_poly,
                         tol_poly=tol_poly,
                         other_rewards=other_rewards,
                         with_forecast=with_forecast,
                         voltagecontrolerClass=voltagecontrolerClass,
                         opponent_action_class=opponent_action_class,
                         opponent_class=opponent_class,
                         opponent_budget_class=opponent_budget_class,
                         opponent_init_budget=opponent_init_budget,
                         opponent_budget_per_ts=opponent_budget_per_ts,
                         opponent_attack_duration=opponent_attack_duration,
                         opponent_attack_cooldown=opponent_attack_cooldown,
                         kwargs_opponent=kwargs_opponent,
                         has_attention_budget=has_attention_budget,
                         attention_budget_cls=attention_budget_cls,
                         kwargs_attention_budget=kwargs_attention_budget,
                         )
        if name == "unknown":
            warnings.warn("It is NOT recommended to create an environment without \"make\" and EVEN LESS "
                          "to use an environment without a name...")
        self.name = name
        self._read_from_local_dir = _read_from_local_dir

        # for gym compatibility (initialized below)
        # self.action_space = None
        # self.observation_space = None
        self.reward_range = None
        self.viewer = None
        self.metadata = None
        self.spec = None

        if _raw_backend_class is None:
            self._raw_backend_class = type(backend)
        else:
            self._raw_backend_class = _raw_backend_class

        self._compat_glop_version = _compat_glop_version

        # for plotting
        self._init_backend(chronics_handler, backend,
                           names_chronics_to_backend, actionClass, observationClass,
                           rewardClass, legalActClass)
        self._actionClass_orig = actionClass
        self._observationClass_orig = observationClass

    def _init_backend(self, chronics_handler, backend,
                      names_chronics_to_backend, actionClass, observationClass,
                      rewardClass, legalActClass):
        """
        INTERNAL

        .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

        Create a proper and valid environment.
        """

        if not isinstance(rewardClass, type):
            raise Grid2OpException("Parameter \"rewardClass\" used to build the Environment should be a type (a class) "
                                   "and not an object (an instance of a class). "
                                   "It is currently \"{}\"".format(type(rewardClass)))
        if not issubclass(rewardClass, BaseReward):
            raise Grid2OpException("Parameter \"rewardClass\" used to build the Environment should derived form "
                                   "the grid2op.BaseReward class, type provided is \"{}\"".format(type(rewardClass)))

        # backend
        if not isinstance(backend, Backend):
            raise Grid2OpException("Parameter \"backend\" used to build the Environment should derived form the "
                                   "grid2op.Backend class, type provided is \"{}\"".format(type(backend)))
        self.backend = backend
        if self.backend.is_loaded:
            raise EnvError("Impossible to use the same backend twice. Please create your environment with a "
                           "new backend instance.")

        if self._read_from_local_dir:
            # test to support pickle conveniently
            self.backend._PATH_ENV = self.get_path_env()

        # all the above should be done in this exact order, otherwise some weird behaviour might occur
        # this is due to the class attribute
        self.backend.set_env_name(self.name)
        self.backend.load_grid(self._init_grid_path)  # the real powergrid of the environment
        self.backend.load_redispacthing_data(self.get_path_env())
        self.backend.load_storage_data(self.get_path_env())
        exc_ = self.backend.load_grid_layout(self.get_path_env())
        if exc_ is not None:
            warnings.warn(f"No layout have been found for you grid (or the layout provided was corrupted). You will "
                          f"not be able to use the renderer, plot the grid etc. The error was \"{exc_}\"")
        self.backend.is_loaded = True

        # alarm set up
        self.load_alarm_data()

        # to force the initialization of the backend to the proper type
        self.backend.assert_grid_correct()
        self._handle_compat_glop_version()

        self._has_been_initialized()  # really important to include this piece of code! and just here after the
        # backend has loaded everything
        self._line_status = np.ones(shape=self.n_line, dtype=dt_bool)
        self._disc_lines = np.zeros(shape=self.n_line, dtype=dt_int) - 1

        if self._thermal_limit_a is None:
            self._thermal_limit_a = self.backend.thermal_limit_a.astype(dt_float)
        else:
            self.backend.set_thermal_limit(self._thermal_limit_a.astype(dt_float))

        *_, tmp = self.backend.generators_info()

        # rules of the game
        if not isinstance(legalActClass, type):
            raise Grid2OpException("Parameter \"legalActClass\" used to build the Environment should be a type "
                                   "(a class) and not an object (an instance of a class). "
                                   "It is currently \"{}\"".format(type(legalActClass)))
        if not issubclass(legalActClass, BaseRules):
            raise Grid2OpException(
                "Parameter \"legalActClass\" used to build the Environment should derived form the "
                "grid2op.BaseRules class, type provided is \"{}\"".format(
                    type(legalActClass)))
        self._game_rules = RulesChecker(legalActClass=legalActClass)
        self._legalActClass = legalActClass

        # action helper
        if not isinstance(actionClass, type):
            raise Grid2OpException("Parameter \"actionClass\" used to build the Environment should be a type (a class) "
                                   "and not an object (an instance of a class). "
                                   "It is currently \"{}\"".format(type(legalActClass)))
        if not issubclass(actionClass, BaseAction):
            raise Grid2OpException(
                "Parameter \"actionClass\" used to build the Environment should derived form the "
                "grid2op.BaseAction class, type provided is \"{}\"".format(
                    type(actionClass)))

        if not isinstance(observationClass, type):
            raise Grid2OpException("Parameter \"actionClass\" used to build the Environment should be a type (a class) "
                                   "and not an object (an instance of a class). "
                                   "It is currently \"{}\"".format(type(legalActClass)))
        if not issubclass(observationClass, BaseObservation):
            raise Grid2OpException(
                "Parameter \"observationClass\" used to build the Environment should derived form the "
                "grid2op.BaseObservation class, type provided is \"{}\"".format(
                    type(observationClass)))

        # action affecting the grid that will be made by the agent
        bk_type = type(self.backend)  # be careful here: you need to initialize from the class, and not from the object
        self._rewardClass = rewardClass
        self._actionClass = actionClass.init_grid(gridobj=bk_type)
        self._actionClass._add_shunt_data()
        self._actionClass._update_value_set()
        self._observationClass = observationClass.init_grid(gridobj=bk_type)

        self._complete_action_cls = CompleteAction.init_grid(gridobj=bk_type)

        self._helper_action_class = ActionSpace.init_grid(gridobj=bk_type)
        self._action_space = self._helper_action_class(gridobj=bk_type,
                                                       actionClass=actionClass,
                                                       legal_action=self._game_rules.legal_action)
        # action that affect the grid made by the environment.
        self._helper_action_env = self._helper_action_class(gridobj=bk_type,
                                                            actionClass=CompleteAction,
                                                            legal_action=self._game_rules.legal_action)

        # handles input data
        if not isinstance(chronics_handler, ChronicsHandler):
            raise Grid2OpException(
                "Parameter \"chronics_handler\" used to build the Environment should derived form the "
                "grid2op.ChronicsHandler class, type provided is \"{}\"".format(
                    type(chronics_handler)))
        self.chronics_handler = chronics_handler
        self.chronics_handler.initialize(self.name_load, self.name_gen,
                                         self.name_line, self.name_sub,
                                         names_chronics_to_backend=names_chronics_to_backend)
        self._names_chronics_to_backend = names_chronics_to_backend

        # this needs to be done after the chronics handler: rewards might need information
        # about the chronics to work properly.
        self._helper_observation_class = ObservationSpace.init_grid(gridobj=bk_type)
        self._observation_space = self._helper_observation_class(gridobj=bk_type,
                                                                 observationClass=observationClass,
                                                                 actionClass=actionClass,
                                                                 rewardClass=rewardClass,
                                                                 env=self)

        # test to make sure the backend is consistent with the chronics generator
        self.chronics_handler.check_validity(self.backend)
        self.delta_time_seconds = dt_float(self.chronics_handler.time_interval.seconds)
        self._reset_storage()  # this should be called after the  self.delta_time_seconds is set

        # reward function
        self._reward_helper = RewardHelper(self._rewardClass)
        self._reward_helper.initialize(self)
        for k, v in self.other_rewards.items():
            v.initialize(self)

        # controller for voltage
        if not issubclass(self._voltagecontrolerClass, BaseVoltageController):
            raise Grid2OpException("Parameter \"voltagecontrolClass\" should derive from \"ControlVoltageFromFile\".")

        self._voltage_controler = self._voltagecontrolerClass(gridobj=bk_type,
                                                              controler_backend=self.backend,
                                                              actionSpace_cls=self._helper_action_class)

        # create the opponent
        # At least the 3 following attributes should be set before calling _create_opponent
        self._create_opponent()

        # create the attention budget
        self._create_attention_budget()

        # performs one step to load the environment properly (first action need to be taken at first time step after
        # first injections given)
        self._reset_maintenance()
        self._reset_redispatching()
        do_nothing = self._helper_action_env({})
        *_, fail_to_start, info = self.step(do_nothing)
        if fail_to_start:
            raise Grid2OpException("Impossible to initialize the powergrid, the powerflow diverge at iteration 0. "
                                   "Available information are: {}".format(info))

        # test the backend returns object of the proper size
        self.backend.assert_grid_correct_after_powerflow()

        # for gym compatibility
        self.reward_range = self._reward_helper.range()
        self.viewer = None
        self.viewer_fig = None

        self.metadata = {'render.modes': []}
        self.spec = None

        self.current_reward = self.reward_range[0]
        self.done = False

        # reset everything to be consistent
        self._reset_vectors_and_timings()

    def max_episode_duration(self):
        """
        Return the maximum duration (in number of steps) of the current episode.

        Notes
        -----
        For possibly infinite episode, the duration is returned as `np.iinfo(np.int32).max` which corresponds
        to the maximum 32 bit integer (usually `2147483647`)

        """
        tmp = dt_int(self.chronics_handler.max_episode_duration())
        if tmp < 0:
            tmp = dt_int(np.iinfo(dt_int).max)
        return tmp

    def set_max_iter(self, max_iter):
        """

        Parameters
        ----------
        max_iter: ``int``
            The maximum number of iteration you can do before reaching the end of the episode. Set it to "-1" for
            possibly infinite episode duration.

        Notes
        -------

        Maximum length of the episode can depend on the chronics used. See :attr:`Environment.chronics_handler` for
        more information

        """
        self.chronics_handler.set_max_iter(max_iter)

    @property
    def _helper_observation(self):
        return self._observation_space

    @property
    def _helper_action_player(self):
        return self._action_space

    def _handle_compat_glop_version(self):
        if self._compat_glop_version is not None and self._compat_glop_version != grid2op.__version__:
            warnings.warn("You are using a grid2op \"compatibility\" environment. This means that some "
                          "feature will not be available. This feature is absolutely NOT recommended except to "
                          "read back data (for example with EpisodeData) that were stored with previous "
                          "grid2op version.")
            self.backend.set_env_name(f"{self.name}_{self._compat_glop_version}")
            cls_bk = type(self.backend)
            cls_bk.glop_version = self._compat_glop_version
            if cls_bk.glop_version == cls_bk.BEFORE_COMPAT_VERSION:
                # oldest version: no storage and no curtailment available
                # deactivate storage
                # recompute the topology vector (more or less everything need to be adjusted...
                stor_locs = [pos for pos in cls_bk.storage_pos_topo_vect]
                for stor_loc in sorted(stor_locs, reverse=True):
                    for vect in [cls_bk.load_pos_topo_vect, cls_bk.gen_pos_topo_vect,
                                 cls_bk.line_or_pos_topo_vect, cls_bk.line_ex_pos_topo_vect]:
                        vect[vect >= stor_loc] -= 1

                # deals with the "sub_pos" vector
                for sub_id in range(cls_bk.n_sub):
                    if np.any(cls_bk.storage_to_subid == sub_id):
                        stor_ids = np.where(cls_bk.storage_to_subid == sub_id)[0]
                        stor_locs = cls_bk.storage_to_sub_pos[stor_ids]
                        for stor_loc in sorted(stor_locs, reverse=True):
                            for vect, sub_id_me in zip([cls_bk.load_to_sub_pos, cls_bk.gen_to_sub_pos,
                                                        cls_bk.line_or_to_sub_pos, cls_bk.line_ex_to_sub_pos],
                                                       [cls_bk.load_to_subid, cls_bk.gen_to_subid,
                                                        cls_bk.line_or_to_subid, cls_bk.line_ex_to_subid]):
                                vect[(vect >= stor_loc) & (sub_id_me == sub_id)] -= 1

                # remove storage from the number of element in the substation
                for sub_id in range(cls_bk.n_sub):
                    cls_bk.sub_info[sub_id] -= np.sum(cls_bk.storage_to_subid == sub_id)
                # remove storage from the total number of element
                cls_bk.dim_topo -= cls_bk.n_storage

                # recompute this private member
                cls_bk._topo_vect_to_sub = np.repeat(np.arange(cls_bk.n_sub), repeats=cls_bk.sub_info)
                self.backend._topo_vect_to_sub = np.repeat(np.arange(cls_bk.n_sub), repeats=cls_bk.sub_info)

                new_grid_objects_types = cls_bk.grid_objects_types
                new_grid_objects_types = new_grid_objects_types[new_grid_objects_types[:, cls_bk.STORAGE_COL] == -1,:]
                cls_bk.grid_objects_types = 1 * new_grid_objects_types
                self.backend.grid_objects_types = 1 * new_grid_objects_types

                # erase all trace of storage units
                cls_bk.set_no_storage()
                Environment.deactivate_storage(self.backend)

                # the following line must be called BEFORE "self.backend.assert_grid_correct()" !
                self.backend.storage_deact_for_backward_comaptibility()

                # and recomputes everything while making sure everything is consistent
                self.backend.assert_grid_correct()
                type(self.backend)._topo_vect_to_sub = np.repeat(np.arange(cls_bk.n_sub), repeats=cls_bk.sub_info)
                type(self.backend).grid_objects_types = new_grid_objects_types

    def _voltage_control(self, agent_action, prod_v_chronics):
        """
        INTERNAL

        .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

        Update the environment action "action_env" given a possibly new voltage setpoint for the generators. This
        function can be overide for a more complex handling of the voltages.

        It must update (if needed) the voltages of the environment action :attr:`BaseEnv.env_modification`

        Parameters
        ----------
        agent_action: :class:`grid2op.Action.Action`
            The action performed by the player (or do nothing is player action were not legal or ambiguous)

        prod_v_chronics: ``numpy.ndarray`` or ``None``
            The voltages that has been specified in the chronics

        """
        volt_control_act = self._voltage_controler.fix_voltage(self.current_obs,
                                                               agent_action,
                                                               self._env_modification,
                                                               prod_v_chronics)
        return volt_control_act

    def set_chunk_size(self, new_chunk_size):
        """
        For an efficient data pipeline, it can be usefull to not read all part of the input data
        (for example for load_p, prod_p, load_q, prod_v). Grid2Op support the reading of large chronics by "chunk"
        of given size.

        Reading data in chunk can also reduce the memory footprint, useful in case of multiprocessing environment while
        large chronics.

        It is critical to set a small chunk_size in case of training machine learning algorithm (reinforcement
        learning agent) at the beginning when the agent performs poorly, the software might spend most of its time
        loading the data.

        **NB** this has no effect if the chronics does not support this feature.

        **NB** The environment need to be **reset** for this to take effect (it won't affect the chronics already
        loaded)

        Parameters
        ----------
        new_chunk_size: ``int`` or ``None``
            The new chunk size (positive integer)

        Examples
        ---------
        Here is an example on how to use this function

        .. code-block:: python

            import grid2op

            # I create an environment
            env = grid2op.make("rte_case5_example", test=True)
            env.set_chunk_size(100)
            env.reset()  # otherwise chunk size has no effect !
            # and now data will be read from the hard drive 100 time steps per 100 time steps
            # instead of the whole episode at once.

        """
        if new_chunk_size is None:
            self.chronics_handler.set_chunk_size(new_chunk_size)
            return

        try:
            new_chunk_size = int(new_chunk_size)
        except Exception as exc_:
            raise Grid2OpException("Impossible to set the chunk size. It should be convertible a integer, and not"
                                   "{}. The error was: \n\"{}\"".format(new_chunk_size, exc_))

        if new_chunk_size <= 0:
            raise Grid2OpException("Impossible to read less than 1 data at a time. Please make sure \"new_chunk_size\""
                                   "is a positive integer.")

        self.chronics_handler.set_chunk_size(new_chunk_size)

    def simulate(self, action):
        """
        Another method to call `obs.simulate` to ensure compatibility between multi environment and
        regular one.

        Parameters
        ----------
        action:
            A grid2op action

        Returns
        -------
        Same return type as :func:`grid2op.Environment.BaseEnv.step` or
        :func:`grid2op.Observation.BaseObservation.simulate`

        Notes
        -----
        Prefer using `obs.simulate` if possible, it will be faster than this function.

        """
        return self.get_obs().simulate(action)

    def set_id(self, id_):
        """
        Set the id that will be used at the next call to :func:`Environment.reset`.

        **NB** this has no effect if the chronics does not support this feature.

        **NB** The environment need to be **reset** for this to take effect.

        Parameters
        ----------
        id_: ``int``
            the id of the chronics used.

        Examples
        --------
        Here an example that will loop 10 times through the same chronics (always using the same injection then):

        .. code-block:: python

            import grid2op
            from grid2op import make
            from grid2op.BaseAgent import DoNothingAgent

            env = make("rte_case14_realistic")  # create an environment
            agent = DoNothingAgent(env.action_space)  # create an BaseAgent

            for i in range(10):
                env.set_id(0)  # tell the environment you simply want to use the chronics with ID 0
                obs = env.reset()  # it is necessary to perform a reset
                reward = env.reward_range[0]
                done = False
                while not done:
                    act = agent.act(obs, reward, done)
                    obs, reward, done, info = env.step(act)

        And here you have an example on how you can loop through the scenarios in a given order:

        .. code-block:: python

            import grid2op
            from grid2op import make
            from grid2op.BaseAgent import DoNothingAgent

            env = make("rte_case14_realistic")  # create an environment
            agent = DoNothingAgent(env.action_space)  # create an BaseAgent
            scenario_order = [1,2,3,4,5,10,8,6,5,7,78, 8]
            for id_ in scenario_order:
                env.set_id(id_)  # tell the environment you simply want to use the chronics with ID 0
                obs = env.reset()  # it is necessary to perform a reset
                reward = env.reward_range[0]
                done = False
                while not done:
                    act = agent.act(obs, reward, done)
                    obs, reward, done, info = env.step(act)

        """
        try:
            id_ = int(id_)
        except Exception as exc_:
            raise EnvError("the \"id_\" parameters should be convertible to integer and not be of type {}"
                           "with error \n\"{}\"".format(type(id_), exc_))

        self.chronics_handler.tell_id(id_-1)

    def attach_renderer(self, graph_layout=None):
        """
        This function will attach a renderer, necessary to use for plotting capabilities.

        Parameters
        ----------
        graph_layout: ``dict``
            Here for backward compatibility. Currently not used.

            If you want to set a specific layout call :func:`BaseEnv.attach_layout`

            If ``None`` this class will use the default substations layout provided when the environment was created.
            Otherwise it will use the data provided.

        Examples
        ---------
        Here is how to use the function

        .. code-block:: python

            import grid2op

            # create the environment
            env = grid2op.make()

            if False:
                # if you want to change the default layout of the powergrid
                # assign coordinates (0., 0.) to all substations (this is a dummy thing to do here!)
                layout = {sub_name: (0., 0.) for sub_name in env.name_sub}
                env.attach_layout(layout)
                # NB again, this code will make everything look super ugly !!!! Don't change the
                # default layout unless you have a reason to.

            # and if you want to use the renderer
            env.attach_renderer()

            # and now you can "render" (plot) the state of the grid
            obs = env.reset()
            done = False
            reward = env.reward_range[0]
            while not done:
                env.render()
                action = agent.act(obs, reward, done)
                obs, reward, done, info = env.step(action)

        """
        # Viewer already exists: skip
        if self.viewer is not None:
            return

        # Do we have the dependency
        try:
            from grid2op.PlotGrid import PlotMatplot
        except ImportError:
            err_msg = "Cannot attach renderer: missing dependency\n" \
                      "Please install matplotlib or run pip install grid2op[optional]"
            raise Grid2OpException(err_msg) from None

        self.viewer = PlotMatplot(self._observation_space)
        self.viewer_fig = None
        # Set renderer modes
        self.metadata = {'render.modes': ["human", "silent"]}

    def __str__(self):
        return '<{} instance named {}>'.format(type(self).__name__, self.name)
        # TODO be closer to original gym implementation

    def reset_grid(self):
        """
        INTERNAL

        .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

            This is automatically called when using `env.reset`

        Reset the backend to a clean state by reloading the powergrid from the hard drive.
        This might takes some time.

        If the thermal has been modified, it also modify them into the new backend.

        """
        self.backend.reset(self._init_grid_path)  # the real powergrid of the environment
        self.backend.assert_grid_correct()

        if self._thermal_limit_a is not None:
            self.backend.set_thermal_limit(self._thermal_limit_a.astype(dt_float))

        self._backend_action = self._backend_action_class()
        do_nothing = self._helper_action_env({})
        *_, fail_to_start, info = self.step(do_nothing)
        if fail_to_start:
            raise Grid2OpException("Impossible to initialize the powergrid, the powerflow diverge at iteration 0. "
                                   "Available information are: {}".format(info))

    def add_text_logger(self, logger=None):
        """
        Add a text logger to this  :class:`Environment`

        Logging is for now an incomplete feature, really incomplete (not used)

        Parameters
        ----------
        logger:
           The logger to use

        """
        self.logger = logger
        return self

    def reset(self):
        """
        Reset the environment to a clean state.
        It will reload the next chronics if any. And reset the grid to a clean state.

        This triggers a full reloading of both the chronics (if they are stored as files) and of the powergrid,
        to ensure the episode is fully over.

        This method should be called only at the end of an episode.

        Examples
        --------
        The standard "gym loop" can be done with the following code:

        .. code-block:: python

            import grid2op

            # create the environment
            env = grid2op.make()

            # and now you can "render" (plot) the state of the grid
            obs = env.reset()
            done = False
            reward = env.reward_range[0]
            while not done:
                action = agent.act(obs, reward, done)
                obs, reward, done, info = env.step(action)
        """
        super().reset()
        self.chronics_handler.next_chronics()
        self.chronics_handler.initialize(self.backend.name_load, self.backend.name_gen,
                                         self.backend.name_line, self.backend.name_sub,
                                         names_chronics_to_backend=self._names_chronics_to_backend)
        self._env_modification = None
        self._reset_maintenance()
        self._reset_redispatching()
        self._reset_vectors_and_timings()  # it need to be done BEFORE to prevent cascading failure when there has been
        self.reset_grid()
        if self.viewer_fig is not None:
            del self.viewer_fig
            self.viewer_fig = None
        # if True, then it will not disconnect lines above their thermal limits
        self._reset_vectors_and_timings()  # and it needs to be done AFTER to have proper timings at tbe beginning
        # the attention budget is reset above

        # reset the opponent
        self._oppSpace.reset()

        # reset, if need, reward and other rewards
        self._reward_helper.reset(self)
        for extra_reward in self.other_rewards.values():
            extra_reward.reset(self)

        # and reset also the "simulated env" in the observation space
        self._observation_space.reset(self)

        return self.get_obs()

    def render(self, mode='human'):
        """
        Render the state of the environment on the screen, using matplotlib
        Also returns the Matplotlib figure

        Examples
        --------
        Rendering need first to define a "renderer" which can be done with the following code:

        .. code-block:: python

            import grid2op

            # create the environment
            env = grid2op.make()

            # if you want to use the renderer
            env.attach_renderer()

            # and now you can "render" (plot) the state of the grid
            obs = env.reset()
            done = False
            reward = env.reward_range[0]
            while not done:
                env.render()  # this piece of code plot the grid
                action = agent.act(obs, reward, done)
                obs, reward, done, info = env.step(action)
        """
        # Try to create a plotter instance
        # Does nothing if viewer exists
        # Raises if matplot is not installed
        self.attach_renderer()
        
        # Check mode is correct
        if mode not in self.metadata["render.modes"]:
            err_msg = "Renderer mode \"{}\" not supported. Available modes are {}."
            raise Grid2OpException(err_msg.format(mode, self.metadata["render.modes"]))

        # Render the current observation
        fig = self.viewer.plot_obs(self.current_obs, figure=self.viewer_fig, redraw=True)

        # First time show for human mode
        if self.viewer_fig is None and mode == "human":
            fig.show()
        else: # Update the figure content
            fig.canvas.draw()

        # Store to re-use the figure
        self.viewer_fig = fig
        # Return the figure in case it needs to be saved/used
        return self.viewer_fig

    def _custom_deepcopy_for_copy(self, new_obj):
        super()._custom_deepcopy_for_copy(new_obj)

        new_obj.name = self.name
        new_obj._read_from_local_dir = self._read_from_local_dir
        new_obj.metadata = copy.deepcopy(self.metadata)
        new_obj.spec = copy.deepcopy(self.spec)

        new_obj._raw_backend_class = self._raw_backend_class
        new_obj._compat_glop_version = self._compat_glop_version
        new_obj._actionClass_orig = self._actionClass_orig
        new_obj._observationClass_orig = self._observationClass_orig

    def copy(self):
        """
        Performs a deep copy of the environment

        Unless you have a reason to, it is not advised to make copy of an Environment.

        Examples
        --------
        It should be used as follow:

        .. code-block:: python

            import grid2op
            env = grid2op.make()
            cpy_of_env = env.copy()


        """
        # res = copy.deepcopy(self) # painfully slow...
        # create an empty "me"
        my_cls = type(self)
        res = my_cls.__new__(my_cls)
        # fill its attribute
        self._custom_deepcopy_for_copy(res)
        return res

    def get_kwargs(self, with_backend=True):
        """
        This function allows to make another Environment with the same parameters as the one that have been used
        to make this one.

        This is useful especially in cases where Environment is not pickable (for example if some non pickable c++
        code are used) but you still want to make parallel processing using "MultiProcessing" module. In that case,
        you can send this dictionary to each child process, and have each child process make a copy of ``self``

        **NB** This function should not be used to make a copy of an environment. Prefer using :func:`Environment.copy`
        for such purpose.


        Returns
        -------
        res: ``dict``
            A dictionary that helps build an environment like ``self`` (which is NOT a copy of self) but rather
            an instance of an environment with the same properties.

        Examples
        --------
        It should be used as follow:

        .. code-block:: python

            import grid2op
            from grid2op.Environment import Environment
            env = grid2op.make()  # create the environment of your choice
            copy_of_env = Environment(**env.get_kwargs())
            # And you can use this one as you would any other environment.
            # NB this is not a "proper" copy. for example it will not be at the same step, it will be possible
            # seeded with a different seed.
            # use `env.copy()` to make a proper copy of an environment.

        """
        res = {}
        res["init_grid_path"] = self._init_grid_path
        res["chronics_handler"] = copy.deepcopy(self.chronics_handler)
        if with_backend:
            res["backend"] = self.backend.copy()
            res["backend"]._is_loaded = False  # i can reload a copy of an environment
        res["parameters"] = copy.deepcopy(self._parameters)
        res["names_chronics_to_backend"] = copy.deepcopy(self._names_chronics_to_backend)
        res["actionClass"] = self._actionClass_orig
        res["observationClass"] = self._observationClass_orig
        res["rewardClass"] = self._rewardClass
        res["legalActClass"] = self._legalActClass
        res["epsilon_poly"] = self._epsilon_poly
        res["tol_poly"] = self._tol_poly
        res["thermal_limit_a"] = self._thermal_limit_a
        res["voltagecontrolerClass"] = self._voltagecontrolerClass
        res["other_rewards"] = {k: v.rewardClass for k, v in self.other_rewards.items()}
        res["name"] = self.name
        res["_raw_backend_class"] = self._raw_backend_class
        res["with_forecast"] = self.with_forecast

        res["opponent_action_class"] = self._opponent_action_class
        res["opponent_class"] = self._opponent_class
        res["opponent_init_budget"] = self._opponent_init_budget
        res["opponent_budget_per_ts"] = self._opponent_budget_per_ts
        res["opponent_budget_class"] = self._opponent_budget_class
        res["opponent_attack_duration"] = self._opponent_attack_duration
        res["opponent_attack_cooldown"] = self._opponent_attack_cooldown
        res["kwargs_opponent"] = self._kwargs_opponent

        res["attention_budget_cls"] = self._attention_budget_cls
        res["kwargs_attention_budget"] = copy.deepcopy(self._kwargs_attention_budget)
        res["has_attention_budget"] = self._has_attention_budget
        res["_read_from_local_dir"] = self._read_from_local_dir
        return res

    def _chronics_folder_name(self):
        return "chronics"

    def train_val_split(self,
                        val_scen_id,
                        add_for_train="train",
                        add_for_val="val",
                        remove_from_name=None):
        """
        This function is used as :func:`Environment.train_val_split_random`.

        Please refer to this the help of :func:`Environment.train_val_split_random` for more information about
        this function.

        Parameters
        ----------
        val_scen_id: ``list``
            List of the scenario names that will be placed in the validation set

        add_for_train: ``str``
            See :func:`Environment.train_val_split_random` for more information

        add_for_val: ``str``
            See :func:`Environment.train_val_split_random` for more information

        remove_from_name: ``str``
            See :func:`Environment.train_val_split_random` for more information

        Returns
        -------
        nm_train: ``str``
            See :func:`Environment.train_val_split_random` for more information

        nm_val: ``str``
            See :func:`Environment.train_val_split_random` for more information

        Examples
        --------

        A full example on a training / validation / test split with explicit specification of which
        chronics goes in which scenarios is:

        .. code-block:: python

            import grid2op
            import os

            env_name = "l2rpn_case14_sandbox"  # or any other...
            env = grid2op.make(env_name)

            # retrieve the names of the chronics:
            full_path_data = env.chronics_handler.subpaths
            chron_names = [os.path.split(el)[-1] for el in full_path_data]

            # splitting into training / test, keeping the "last" 10 chronics to the test set
            nm_env_trainval, nm_env_test = env.train_val_split(val_scen_id=chron_names[-10:],
                                                               add_for_val="test",
                                                               add_for_train="trainval")

            # now splitting again the training set into training and validation, keeping the last 10 chronics
            # of this environment for validation
            env_trainval = grid2op.make(nm_env_trainval)  # create the "trainval" environment
            full_path_data = env_trainval.chronics_handler.subpaths
            chron_names = [os.path.split(el)[-1] for el in full_path_data]
            nm_env_train, nm_env_val = env_trainval.train_val_split(val_scen_id=chron_names[-10:],
                                                                    remove_from_name="_trainval$")

            # and now you can use the following code to load the environments:
            env_train = grid2op.make(nm_env+"_train")
            env_val = grid2op.make(nm_env+"_val")
            env_test = grid2op.make(nm_env+"_test")

        For a more simple example, with less parametrization and with random assignment (recommended),
        please refer to the help of :func:`Environment.train_val_split_random`

        **NB** read the "Notes" of this section for possible "unexpected" behaviour of the code snippet above.

        Notes
        ------
        We don't recommend you to use this function. It provides a great level of control on which
        scenarios goes into which dataset, which is nice, but
        "*with great power comes great responsibilities*".

        Keep in mind that scenarios might be "sorted" by having some "month" in their names.
        For example, the first k scenarios might be called "April_XXX"
        and the last k ones having names with "September_XXX".

        In general, we would not consider good practice to have all validation (or test) scenarios coming
        from the same months. Keep that in mind if you use the code snippet above.

        """
        # define all the locations
        if re.match(self.REGEX_SPLIT, add_for_train) is None:
            raise EnvError(f"The suffixes you can use for training data (add_for_train) "
                           f"should match the regex \"{self.REGEX_SPLIT}\"")
        if re.match(self.REGEX_SPLIT, add_for_val) is None:
            raise EnvError(f"The suffixes you can use for validation data (add_for_val)"
                           f"should match the regex \"{self.REGEX_SPLIT}\"")

        from grid2op.Chronics import MultifolderWithCache, Multifolder
        if not isinstance(self.chronics_handler.real_data, (MultifolderWithCache, Multifolder)):
            raise EnvError("It does not make sense to split a environment between training / validation "
                           "if the chronics are not read from directories.")

        my_path = self.get_path_env()
        path_train = os.path.split(my_path)
        my_name = path_train[1]
        if remove_from_name is not None:
            if re.match(r"^[a-zA-Z0-9\\^\\$_]*$", remove_from_name) is None:
                raise EnvError("The suffixes you can remove from the name of the environment (remove_from_name)"
                               "should match the regex \"^[a-zA-Z0-9^$_]*$\"")
            my_name = re.sub(remove_from_name, "", my_name)

        nm_train = f'{my_name}_{add_for_train}'
        path_train = os.path.join(path_train[0], nm_train)
        path_val = os.path.split(my_path)
        nm_val = f'{my_name}_{add_for_val}'
        path_val = os.path.join(path_val[0], nm_val)
        chronics_dir = self._chronics_folder_name()

        # create the folder
        if os.path.exists(path_val):
            raise RuntimeError(f"Impossible to create the validation environment that should have the name "
                               f"\"{nm_val}\" because an environment is already named this way. If you want to "
                               f"continue either delete the folder \"{path_val}\" or name your validation environment "
                               f"differently "
                               f"using the \"add_for_val\" keyword argument of this function.")
        if os.path.exists(path_train):
            raise RuntimeError(f"Impossible to create the training environment that should have the name "
                               f"\"{nm_train}\" because an environment is already named this way. If you want to "
                               f"continue either delete the folder \"{path_train}\" or name your training environment "
                               f" differently "
                               f"using the \"add_for_train\" keyword argument of this function.")
        os.mkdir(path_val)
        os.mkdir(path_train)

        # assign which chronics goes where
        chronics_path = os.path.join(my_path, chronics_dir)
        all_chron = sorted(os.listdir(chronics_path))
        to_val = set(val_scen_id)

        # copy the files
        for el in os.listdir(my_path):
            tmp_path = os.path.join(my_path, el)
            if os.path.isfile(tmp_path):
                # this is a regular env file
                os.symlink(tmp_path, os.path.join(path_train, el))
                os.symlink(tmp_path, os.path.join(path_val, el))
            elif os.path.isdir(tmp_path):
                if el == chronics_dir:
                    # this is the chronics folder
                    os.mkdir(os.path.join(path_train, chronics_dir))
                    os.mkdir(os.path.join(path_val, chronics_dir))
                    for chron_name in all_chron:
                        tmp_path_chron = os.path.join(tmp_path, chron_name)
                        if chron_name in to_val:
                            os.symlink(tmp_path_chron, os.path.join(path_val, chronics_dir, chron_name))
                        else:
                            os.symlink(tmp_path_chron, os.path.join(path_train, chronics_dir, chron_name))
        return nm_train, nm_val

    def train_val_split_random(self,
                               pct_val=10.,
                               add_for_train="train",
                               add_for_val="val",
                               remove_from_name=None):
        """
        By default a grid2op environment contains multiple "scenarios" containing values for all the producers
        and consumers representing multiple days. In a "game like" environment, you can think of the scenarios as
        being different "game levels": different mazes in pacman, different levels in mario etc.

        We recommend to train your agent on some of these "chroncis" (aka levels) and test the performance of your
        agent on some others, to avoid overfitting.

        This function allows to easily split an environment into different part. This is most commonly used in machine
        learning where part of a dataset is used for training and another part is used for assessing the performance
        of the trained model.

        This function rely on "symbolic link" and will not duplicate data.

        New created environments will behave like regular grid2op environment and will be accessible with "make" just
        like any others (see the examples section for more information).

        This function will make the split at random. If you want more control on the which scenarios to use for
        training and which for validation, use the :func:`Environment.train_val_split` that allows to specify
        which scenarios goes in the validation environment (and the others go in the training environment).

        Parameters
        ----------

        pct_val: ``float``
            Percentage of chronics that will go to the validation set.
            For 10% of the chronics, set it to 10. and NOT to 0.1.

        add_for_train: ``str``
            Suffix that will be added to the name of the environment for the training set. We don't recommend to
            modify the default value ("train")

        add_for_val: ``str``
            Suffix that will be added to the name of the environment for the validation set. We don't recommend to
            modify the default value ("val")

        remove_from_name: ``str``
            If you "split" an environment multiple times, this allows you to keep "short" names (for example
            you will be able to call `grid2op.make(env_name+"_train")` instead of
            `grid2op.make(env_name+"_train_train")`)

        Returns
        -------
        nm_train: ``str``
            Complete name of the "training" environment

        nm_val: ``str``
            Complete name of the "validation" environment

        Examples
        --------
        This function can be used like:

        .. code-block:: python

            import grid2op
            env_name = "l2rpn_case14_sandbox"  # or any other...
            env = grid2op.make(env_name)

            # extract 1% of the "chronics" to be used in the validation environment. The other 99% will
            # be used for test
            nm_env_train, nm_env_val = env.train_val_split_random(pct_val=1.)

            # and now you can use the training set only to train your agent:
            print(f"The name of the training environment is \\"{nm_env_train}\\"")
            print(f"The name of the validation environment is \\"{nm_env_val}\\"")
            env_train = grid2op.make(nm_env_train)

        And even after you close the python session, you can still use this environment for training. If you used
        the exact code above that will look like:

        .. code-block:: python

            import grid2op
            env_name_train = "l2rpn_case14_sandbox_train"  # depending on the option you passed above
            env_train = grid2op.make(env_name_train)

        Notes
        -----
        This function will fail if an environment already exists with one of the name that would be given
        to the training environment or the validation environment.

        """
        if re.match(self.REGEX_SPLIT, add_for_train) is None:
            raise EnvError("The suffixes you can use for training data (add_for_train) "
                           "should match the regex \"{self.REGEX_SPLIT}\"")
        if re.match(self.REGEX_SPLIT, add_for_val) is None:
            raise EnvError("The suffixes you can use for validation data (add_for_val)"
                           "should match the regex \"{self.REGEX_SPLIT}\"")

        my_path = self.get_path_env()
        chronics_path = os.path.join(my_path, self._chronics_folder_name())
        all_chron = sorted(os.listdir(chronics_path))
        to_val = self.space_prng.choice(all_chron, int(len(all_chron) * pct_val * 0.01))
        return self.train_val_split(to_val,
                                    add_for_train=add_for_train,
                                    add_for_val=add_for_val,
                                    remove_from_name=remove_from_name)

    def get_params_for_runner(self):
        """
        This method is used to initialize a proper :class:`grid2op.Runner.Runner` to use this specific environment.

        Examples
        --------
        It should be used as followed:

        .. code-block:: python

            import grid2op
            from grid2op.Runner import Runner
            from grid2op.Agent import DoNothingAgent  # for example
            env = grid2op.make()  # create the environment of your choice

            # create the proper runner
            runner = Runner(**env.get_params_for_runner(), agentClass=DoNothingAgent)

            # now you can run
            runner.run(nb_episode=1)  # run for 1 episode

        """
        res = {}
        res["init_grid_path"] = self._init_grid_path
        res["path_chron"] = self.chronics_handler.path
        res["parameters_path"] = self._parameters.to_dict()
        res["names_chronics_to_backend"] = self._names_chronics_to_backend
        res["actionClass"] = self._actionClass_orig
        res["observationClass"] = self._observationClass_orig
        res["rewardClass"] = self._rewardClass
        res["legalActClass"] = self._legalActClass
        res["envClass"] = Environment
        res["gridStateclass"] = self.chronics_handler.chronicsClass
        res["backendClass"] = self._raw_backend_class
        res["verbose"] = False
        dict_ = copy.deepcopy(self.chronics_handler.kwargs)
        if 'path' in dict_:
            # path is handled elsewhere
            del dict_["path"]
        if self.chronics_handler.max_iter is not None:
            res["max_iter"] = self.chronics_handler.max_iter
        res["gridStateclass_kwargs"] = dict_
        res["thermal_limit_a"] = self._thermal_limit_a
        res["voltageControlerClass"] = self._voltagecontrolerClass
        res["other_rewards"] = {k: v.rewardClass for k, v in self.other_rewards.items()}
        res["grid_layout"] = self.grid_layout
        res["name_env"] = self.name

        res["opponent_action_class"] = self._opponent_action_class
        res["opponent_class"] = self._opponent_class
        res["opponent_init_budget"] = self._opponent_init_budget
        res["opponent_budget_per_ts"] = self._opponent_budget_per_ts
        res["opponent_budget_class"] = self._opponent_budget_class
        res["opponent_attack_duration"] = self._opponent_attack_duration
        res["opponent_attack_cooldown"] = self._opponent_attack_cooldown
        res["opponent_kwargs"] = self._kwargs_opponent

        res["attention_budget_cls"] = self._attention_budget_cls
        res["kwargs_attention_budget"] = copy.deepcopy(self._kwargs_attention_budget)
        res["has_attention_budget"] = self._has_attention_budget
        res["_read_from_local_dir"] = self._read_from_local_dir
        return res
