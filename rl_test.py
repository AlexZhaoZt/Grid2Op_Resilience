import grid2op

# print(grid2op.__version__)
import lightsim2grid
print(lightsim2grid.__version__)

from lightsim2grid import LightSimBackend
backend = LightSimBackend()
env = grid2op.make(backend=backend)
# do regular computation as you would with grid2op