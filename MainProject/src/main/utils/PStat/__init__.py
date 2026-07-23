import sys
_GAMRY_TOOLKITPY = r'C:/Program Files (x86)/Gamry Instruments/Framework/toolkitpy'
if _GAMRY_TOOLKITPY not in sys.path:
    sys.path.append(_GAMRY_TOOLKITPY)
from .cv import *
from .geis import *
# from .poteis import *
from .experiment import *
from .ocv import *
from .dataanalysis import *
from .BUMPS import *