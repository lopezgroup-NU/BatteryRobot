from north import NorthC9
from Locator import *
from utils import BatteryRobot,PowderShaker,T8, MongoQuery
from datetime import datetime

c9 = BatteryRobot('A', network_serial='AU06EZ1P', home= False)

c9.goto_safe(dropcast_aspirate)
c9.star_dropcast_prep(3, True)
now = datetime.now()
print(f"Date is {now.month} {now.day}")

# for locations in dropcast_coords_eight:
#     c9.aspirate_ml(3, 0.5)
#     c9.star_dropcast(locations)
#     c9.delay(2)
    