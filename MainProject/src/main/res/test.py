import pandas as pd
df = pd.read_csv("control.csv", index_col='# point')
s_df = pd.read_csv("test_summaries.csv")
reflected_zimag = [-val for val in df['zimag']]

min_zimag = min(reflected_zimag)
id_min = reflected_zimag.index(min_zimag) # get id of min value
cor_real = df['zreal'][id_min]
new_row = pd.DataFrame([["contorol", cor_real, min_zimag]], columns=['Test Name', 'zreal', 'min_zimag'])
s_df = pd.concat([s_df, new_row], ignore_index=True)

print(s_df)