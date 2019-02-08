import numpy as np
from dolfin import Function, info


class Progress:
    def __init__(self, t_start, t_end, show_bar):
        self._show_bar = show_bar

        if self._show_bar:
            from tqdm import tqdm

            fmt = "{l_bar}{bar}{rate_fmt}"
            self._pbar = tqdm(total=t_end - t_start, ascii=True, bar_format=fmt)

    def _green(self, msg):
        info("\033[32m" + msg + "\033[m")

    def _red(self, msg):
        info("\033[31m" + msg + "\033[m")

    def iteration_info(self, t, dt, iterations):
        return "at t = {:8.5f} after {:2} iteration(s) with dt = {:8.5f}.".format(
            t, iterations, dt
        )

    def success(self, t, dt, iterations):
        if self._show_bar:
            self._pbar.update(dt)
            self._pbar.set_description("dt = {:8.5f}".format(dt))
        else:
            self._green("Convergence " + self.iteration_info(t, dt, iterations))

    def error(self, t, dt, iterations):
        if not self._show_bar:
            self._red("No Convergence " + self.iteration_info(t, dt, iterations))

    def __del__(self):
        if self._show_bar:
            self._pbar.close()


class CheckPoints:
    def __init__(self, points, t_start, t_end):
        self.points = np.sort(np.array(points))

        if self.points.size == 0:
            return
        if self.points.max() > t_end or self.points.min() < t_start:
            raise RuntimeError("Checkpoints outside of integration range.")

    def _first_checkpoint_within(self, t0, t1):
        id_range = (self.points > t0) & (self.points < t1)
        points_within_dt = self.points[id_range]
        if points_within_dt.size != 0:
            return points_within_dt[0]
        return None


    def timestep(self, t, dt):
        """
        Searches a checkpoint t_check within [t, t+dt]. Picks the one
        with the lowest time if multiple are found. 
        If there is such a point, the dt = t_check - t is returned.
        If nothing is found, the unmodified dt is returned.
        """
        t_check = self._first_checkpoint_within(t, t+dt)
        if t_check:
            return t_check - t
        return dt

class Adaptive:
    def __init__(self, solve, post_process, u):
        assert isinstance(u, Function)
        self.dt_min = 1.e-6
        self.dt_max = 0.1
        self.decrease_factor = 0.5
        self.increase_factor = 1.5
        self.increase_num_iter = 4
        self._solve = solve
        self._post_process = post_process
        self._u = u

    def run(self, t_end, t_start=0.0, dt=None, checkpoints=[], show_bar=False):
        if dt is None:
            dt = self.dt_max

        u_prev = self._u.copy(deepcopy=True)
        t = t_start
        self._post_process(t)

        progress = Progress(t_start, t_end, show_bar)
        checkpoints = CheckPoints(checkpoints, t_start, t_end)
        

        dt0 = dt
        while t < t_end:
            dt, dt0 = checkpoints.timestep(t, dt0), dt0
            # We keep track of two time steps. dt0 is the time step that
            # ignores the checkpoints. This is the one that is adapted upon
            # fast/no convergence. dt is smaller than dt0
            assert(dt <= dt0)
            # and coveres checkpoints.

            print(dt, dt0)

            t += dt

            num_iter, converged = self._solve(t)
            assert(isinstance(converged, bool))
            assert(type(num_iter) == int) # isinstance(False, int) is True...

            if converged:
                progress.success(t, dt, num_iter)
                u_prev.assign(self._u)
                self._post_process(t)

                # increase the time step for fast convergence
                if dt == dt0 and num_iter < self.increase_num_iter and dt < self.dt_max:
                    dt0 *= self.increase_factor
                    dt0 = min(dt, self.dt_max)
                    if not show_bar:
                        info("Increasing time step to dt = {}.".format(dt0))

                # adjust dt to end at t_end
                dt0 = min(dt0, t_end - t)

            else:
                progress.error(t, dt, num_iter)

                self._u.assign(u_prev)
                t -= dt
                dt *= self.decrease_factor

                if dt == dt0: 
                    dt0 *= self.decrease_factor
                if not show_bar:
                    info("Reduce time step to dt = {}.".format(dt0))
                if dt0 < self.dt_min:
                    info("Abort since dt({}) < dt_min({})".format(dt0, self.dt_min))
                    return False
        return True


class Equidistant:
    def __init__(self, solve, post_process):
        self._solve = solve
        self._post_process = post_process

    def run(self, t_end, dt, t_start=0.0, checkpoints=[], show_bar=False):
        progress = Progress(t_start, t_end, show_bar)

        points_in_time = np.append(np.arange(t_start, t_end, dt), t_end)
        checkpoints = CheckPoints(checkpoints, t_start, t_end)
        points_in_time = np.append(points_in_time, checkpoints.points)

        for t in np.sort(points_in_time):
            num_iter, converged = self._solve(t)
            assert(isinstance(converged, bool))

            if converged:
                progress.success(t, dt, num_iter)
                self._post_process(t)
            else:
                progress.error(t, dt, num_iter)
                return False
        return True
