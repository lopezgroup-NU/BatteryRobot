import sys
sys.path.append('C:\\Users\\llf1362\\Desktop\\BatteryRobot\\MainProject\\src\\main\\settings')

from north import NorthC9
from time import perf_counter
import time
import pandas as pd

from dataclasses import dataclass

@dataclass
class PowderSettings:
    opening_deg: int  # (0, 90] how many degrees to open the valve during dispense
    percent_target: float  # (0, 1] dispense iter target is percent_target*remaining
    max_growth: float  # how much the dispense time can grow/shrink between iters (i.e. 2x)
    thresh : float = 10  # settings take effect below this amount remaining - unless there is a lower one
    amplitude: int = 100  # (0, 100] vibratory amplitude in %
    freq: int = 80  # vibratory freq in hz
    max_shake_t: int = 1000 # max shake time in ms
    min_shake_t: int = 25 # min shake time in ms
    shut_valve: bool = True  # shut valve between every iteration - needed for free-flowing powders

    
@dataclass
class PowderProtocol:
    tol : float  # best expected dispense tolerance
    fast_settings: PowderSettings
    med_settings: PowderSettings
    slow_settings: PowderSettings
    scale_delay: float = 0.5  # seconds before measuring powder... fall time for small amounts of solids


default_ps = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 50,
                                percent_target = 0.75,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 5,
                                opening_deg = 30,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                amplitude = 75
                                ),
                            slow_settings = PowderSettings(
                                thresh = 3,
                                opening_deg = 25,
                                percent_target = 1,
                                max_growth = 1.1,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )
                            
potato_starch = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 40,
                                percent_target = 0.5,
                                max_growth = 2,
                                freq = 80,
                                shut_valve = False
                                ),
                            med_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 35,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                freq = 80,
                                amplitude = 90,
                                shut_valve = False,
                                ),
                            slow_settings = PowderSettings(
                                thresh = 3,
                                opening_deg = 25,
                                percent_target = 0.5,
                                max_growth = 1.1,
                                shut_valve = False,
                                freq = 80,
                                amplitude = 70,
                                min_shake_t = 100,
                                max_shake_t = 250
                                ),
                             scale_delay=2
                            )

flour = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 45,
                                percent_target = 0.5,
                                max_growth = 2,
                                shut_valve = False
                                ),
                            med_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 30,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                shut_valve = False,
                                amplitude=80
                                ),
                            slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 25,
                                percent_target = 0.25,
                                max_growth = 1.1,
                                shut_valve = False,
                                amplitude = 70
                                ),
                             scale_delay=2.5
                            )

fumed_silica = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 45,
                                percent_target = 0.5,
                                max_growth = 2,
                                shut_valve = True
                                ),
                            med_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 40,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                shut_valve = True
                                ),
                            slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 30,
                                percent_target = 0.25,
                                max_growth = 1.1,
                                shut_valve = True
                                ),
                             scale_delay=2.5
                            )


manganese_oxide = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 45,
                                percent_target = 0.5,
                                max_growth = 2,
                                shut_valve = True
                                ),
                            med_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 40,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                shut_valve = True
                                ),
                            slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 30,
                                percent_target = 0.25,
                                max_growth = 1.1,
                                shut_valve = True
                                ),
                             scale_delay=2.5
                            )


manganese_oxybromide = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 45,
                                percent_target = 0.5,
                                max_growth = 2,
                                shut_valve = True
                                ),
                            med_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 40,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                shut_valve = True
                                ),
                            slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 30,
                                percent_target = 0.25,
                                max_growth = 1.1,
                                shut_valve = True
                                ),
                             scale_delay=2.5
                            )




class PowderShaker(NorthC9):
    
    #def init(self):
    #    self.home_OL_stepper(0, 300)

    def init(self, n=None):
        """
        Initiates the powderShaker objects by activating the correct channel to operate each of the servos which open 
        and close the powder dispensers. The way these operate is that each channel controls two servo positions, with 
        3 channels = 6 servos in total on the carousel. Once a channel is activated, all action commands sent to the powder
        shaker default to being performed by the active channel servo/s. I'm not 100% sure how to control the second servo of
        each of the channels yet, but it is clear that the first servo is the default one
        """
        if n is not None:
            self.activate_powder_channel(n)
        #this home_OL_stepper command does a "buzz" action which may be helpful to emulate for future advances in powder dispensation. Check north_c9.py
        #self.home_OL_stepper(0, 300)

    def set_opening(self, deg):
        """
        Opens the powder dispenser chute by deg degrees. When powder clumps, it may not dispense even with the chute open
        """
        self.move_axis(0, deg*(1000/360.0), accel=5000)

    def shake(self, t, f=120, a=100, wait=True):
        """
        This seems not to do anything. Test after winter break
        """
        #t in ms
        #f in hz [40, 80, 100, 120]
        #a in %
        
        return self.amc_pwm(int(f), int(t), int(a), wait=wait)
    
    def shake_mk2(self, t=50, f=100, a=40, wait=True):
        #TODO The timing on this shake will be off quite a bit because it doesn't account for time spent opening and closing the chute. Investigating this may lead to more accurate dispensing
        """A manual shake"""
        #t in ms
        #f in hz [40, 80, 100, 120]
        #a in %
        t_between_toggles = 0.5/f

        num_cycles = round(t/(2*1000*t_between_toggles))

        for cycle in range(0,num_cycles):
            print(f"{t_between_toggles}___{a/2}")
            
            #opens and closes at max speed.
            self.set_opening((a/2))
            #self.move_axis(0, (a/2)*(1000/360.0), vel=100, accel=1000)
            time.sleep(t_between_toggles)
            self.set_opening(0)
            #self.move_axis(0, 0, vel=100, accel=1000)
            time.sleep(t_between_toggles)

        #return self.amc_pwm(int(f), int(t), int(a), wait=wait)
    

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
        while mg_togo > protocol.tol:  #TODO should have a max count condition? other timeout?
            count += 1                
            #TODO: rewrite below:
            #if write_file:
                #file.record(shake_t, delta_mass, iter_target, mg_togo)
            self.set_opening(ps.opening_deg)  
            #print(shake_t)
            #print(ps.freq)
            #print(ps.amplitude)


            self.shake_mk2(shake_t, ps.freq, ps.opening_deg)
            if ps.shut_valve:
                self.set_opening(0)
            robot.delay(0.5)
            robot.read_steady_scale()  # dummy read to wait for steady
            robot.delay(protocol.scale_delay)  # delay after steady to allow for more settling time
            meas_mass = robot.read_steady_scale() * 1000 - tare
            
            mg_togo = mg_target - meas_mass
            delta_mass = meas_mass - prev_mass
            prev_mass = meas_mass
            
            if mg_togo <= protocol.slow_settings.thresh:
                ps = protocol.slow_settings
            elif mg_togo <= protocol.med_settings.thresh:
                ps = protocol.med_settings
            elif mg_togo <= protocol.fast_settings.thresh:
                ps = protocol.fast_settings

            #TODO Ultra slow settings don't yet exist. Add them? Maybe uses the amc_pwm command if that shakes it
            """
            if mg_togo <= protocol.ultra_slow_settings.thresh:
                ps = protocol.ultra_slow_settings
            elif mg_togo <= protocol.slow_settings.thresh:
                ps = protocol.slow_settings
            elif mg_togo <= protocol.med_settings.thresh:
                ps = protocol.med_settings
            """
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
        #self.set_opening(100)
        #self.set_opening(0)
     
        print(f'Result:')
        print(f'\tLast iter:  {delta_mass:.1f} mg')
        print(f'\tDispensed: {meas_mass:.1f} mg')
        print(f'\tRemaining: {mg_togo:.1f} mg')
        print(f'\tTime:      {int(perf_counter()-start_t)} s')
        print('')

        return meas_mass
