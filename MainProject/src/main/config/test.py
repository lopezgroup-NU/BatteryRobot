import pandas as pd
from temper_windows import TemperWindows
import time
# df = pd.read_csv("disp_rack.csv", header=None)

# df = df.iloc[:, ::-1]
# cont = []
# for col in df:
#     for el in df[col]:
#         cont.append(el)

# print(len(cont))

# try:
#     raise InitializationException("AHHHH")
# except InitializationException as e:
#     print(e)

df_file = "../res/cv/2M_cv0.csv"
s_df_file = "../res/cv_test_summaries.csv"
df = pd.read_csv(df_file, index_col='# Point')
s_df = pd.read_csv(s_df_file)

temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
temperature = temper.get_temperature()[1]
s = time.localtime(time.time())
curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)

targ_max = 0.000024
targ_min = -0.000024
im_col = df["Im"]

#get xmax
im_col_translated = (im_col - targ_max).abs()
min_idx = im_col_translated.idxmin()
vf_max = df['Vf'].loc[min_idx]  # Use .loc to get the value at that index
print(vf_max)

#get xmin
im_col_translated = (im_col - targ_min).abs()
min_idx = im_col_translated.idxmin()
vf_min = df['Vf'].loc[min_idx]  # Use .loc to get the value at that index
print(vf_min)

vf_diff = vf_max-vf_min

new_row = pd.DataFrame([["2M_cv0", vf_max, vf_min, vf_diff, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff', 'temp', 'time'])
s_df = pd.concat([s_df, new_row], ignore_index=True)
s_df.to_csv(s_df_file, index=False)   
