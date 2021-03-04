import fenics_helpers.boundary
import fenics_helpers.timestepping
import fenics_helpers.rk
try:
    import fenics_helpers.plotting
except ImportError as e:
    print("Skip import of plotting module." + e)
