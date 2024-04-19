#powder testing

from north import NorthC9
from time import perf_counter

#import ftdi_serial


#home valve:
#p2.home_OL_stepper(0, 300)

def cl_pow_dispense (robot, p2, mg_target, protocol=None, zero_scale=True, write_file=False):
    rob.get_info()
    p2.get_info()

    def init():
        p2.home_OL_stepper(0, 300)

    def set_opening(deg):
        p2.move_axis(0, deg*(1000/360.0), accel=5000)

    def shake(t, f=120, a=100, wait=True):
        #t in ms
        #f in hz [40, 80, 100, 120]
        #a in %
        return p2.amc_pwm(int(f), int(t), int(a), wait=wait)
    
    start_t = perf_counter()
    mg_togo = mg_target
    
    if protocol is None:
        protocol = default_ps 
    ps = protocol.fast_settings
    if mg_togo < protocol.slow_settings.thresh:
        ps = protocol.slow_settings
    elif mg_togo < protocol.med_settings.thresh:
        ps = protocol.med_settings
        
    #intialize
    set_opening(0)  # make sure everything starts closed  
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
        set_opening(ps.opening_deg)  
        shake(shake_t, ps.freq, ps.amplitude)
        if ps.shut_valve:
            set_opening(0)
        robot.delay(0.5)
        robot.read_steady_scale()  # dummy read to wait for steady
        robot.delay(protocol.scale_delay)  # delay after steady to allow for more settling time
        meas_mass = robot.read_steady_scale() * 1000 - tare
        
        mg_togo = mg_target - meas_mass
        delta_mass = meas_mass - prev_mass
        prev_mass = meas_mass

        if mg_togo < protocol.slow_settings.thresh:
            ps = protocol.slow_settings
        elif mg_togo < protocol.med_settings.thresh:
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
        
    set_opening(0)
 
    print(f'Result:')
    print(f'\tLast iter:  {delta_mass:.1f} mg')
    print(f'\tDispensed: {meas_mass:.1f} mg')
    print(f'\tRemaining: {mg_togo:.1f} mg')
    print(f'\tTime:      {int(perf_counter()-start_t)} s')
    print('')

    return meas_mass

