import pandas as pd
from temper_windows import TemperWindows
import time
df = pd.read_csv("disp_rack.csv", header=None)

print(df)
print(df.loc[0,7])

