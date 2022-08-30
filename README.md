# Grid2Op+Resilience

[Grid2Op](https://grid2op.readthedocs.io/) is a Python-based modular power grid simulation platform. It is frequently used to deploy reinforcement learning algorithms for power grid control.

Grid2Op+Resilience implements a new backend, the resilience backend. Together with our modified (pandapower+Resilience)[https://github.com/AlexZhaoZt/pandapower_resilience], the framework supports running a power network after the default "gameover" state.  

## Requirements:
*   Python >= 3.6
*   [pandapower+Resilience](https://github.com/AlexZhaoZt/pandapower_resilience)

# Main Features:
In addition to the core functionalities mentioned in the official [Grid2Op](https://github.com/rte-france/Grid2Op) repository, Grid2Op+Resilience supports:
* emulate a powergrid of any size until the last component (slack bus, generator, or load) dies.
* emulate a powergrid broken into many disconnected subgrids.
* provide multiple new definition of reward and metrics for evaluating the grid in such states.
* provide an adversarial agent that implements harsh powergrid disruptions, such as multiple powerline disconnections in one timestep.
* has an RL-focused interface just like the original Grid2Op
* allow for both OPF and PF simulation
