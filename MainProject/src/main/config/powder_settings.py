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
    name : str
    tol : float  # best expected dispense tolerance
    fast_settings: PowderSettings
    med_settings: PowderSettings
    slow_settings: PowderSettings
    ultra_slow_settings: PowderSettings
    scale_delay: float = 0.5  # seconds before measuring powder... fall time for small amounts of solids