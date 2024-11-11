import sys
sys.path.append('C:\\Users\\llf1362\\Desktop\\BatteryRobot\\MainProject\\src\\main\\settings')

from config import PowderProtocol, PowderSettings
from north import NorthC9
from time import perf_counter
import pandas as pd

class PowderShaker(NorthC9):
    
    def init(self):
        self.home_OL_stepper(0, 300)

    def set_opening(self, deg):
        self.move_axis(0, deg*(1000/360.0), accel=5000)

    def shake(self, t, f=120, a=100, wait=True):
        #t in ms
        #f in hz [40, 80, 100, 120]
        #a in %
        return self.amc_pwm(int(f), int(t), int(a), wait=wait)
    
    """
    Dispenses powder of mass {mg_target}. Follows powder protocol if provided, else uses default.
    """
    def cl_pow_dispense(self, robot, mg_target, protocol=None, zero_scale=True, write_file=False):        

        start_t = perf_counter()
        mg_togo = mg_target
        if protocol is None:
            protocol = default_ps 
        ps = protocol.fast_settings
            
        #intialize

        prev_mass = 0
        delta_mass = 0
        shake_t = ps.min_shake_t
        
        if zero_scale:
            robot.zero_scale()
            robot.delay(protocol.scale_delay)
        tare = robot.read_steady_scale() * 1000
        
        count = 0
        while mg_togo > protocol.tol:  # should have a max count condition? other timeout?
            count += 1                
            #todo: rewrite below:
            #if write_file:
                #file.record(shake_t, delta_mass, iter_target, mg_togo)
            self.set_opening(ps.opening_deg)  
            self.shake(shake_t, ps.freq, ps.amplitude)
            if ps.shut_valve:
                self.set_opening(0)
            robot.delay(0.5)
            robot.read_steady_scale()  # dummy read to wait for steady
            robot.delay(protocol.scale_delay)  # delay after steady to allow for more settling time
            meas_mass = robot.read_steady_scale() * 1000 - tare
            
            mg_togo = mg_target - meas_mass
            delta_mass = meas_mass - prev_mass
            prev_mass = meas_mass

            if mg_togo <= protocol.ultra_slow_settings.thresh:
                ps = protocol.ultra_slow_settings
            elif mg_togo <= protocol.slow_settings.thresh:
                ps = protocol.slow_settings
            elif mg_togo <= protocol.med_settings.thresh:
                ps = protocol.med_settings

            iter_target = (ps.percent_target*mg_togo)
            max_new_t = ps.max_growth*shake_t
            if delta_mass <= 0:
                shake_t = max_new_t
            else:
                shake_t *= (iter_target/delta_mass)
            shake_t = min(max_new_t, shake_t)  # no larger than max growth allows
            shake_t = max(ps.min_shake_t, shake_t)  # no shorter than min time
            shake_t = min(ps.max_shake_t, shake_t)  # no longer than max time
            
            print(f'Iteration {count}:')
            print(f'\tJust dispensed:  {delta_mass:.1f} mg')
            print(f'\tRemaining:       {mg_togo:.1f} mg')
            print(f'\tNext target:     {iter_target:.1f} mg')
            print(f'\tNext time:       {int(shake_t)} ms')
            print('')
        self.set_opening(100)
        self.set_opening(0)
     
        print(f'Result:')
        print(f'\tLast iter:  {delta_mass:.1f} mg')
        print(f'\tDispensed: {meas_mass:.1f} mg')
        print(f'\tRemaining: {mg_togo:.1f} mg')
        print(f'\tTime:      {int(perf_counter()-start_t)} s')
        print('')

        return meas_mass
