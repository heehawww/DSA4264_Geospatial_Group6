import pandas as pd
df = pd.read_csv("hedonic_model/outputs/ols_coefficients.csv")
print(df.columns.tolist())
print(df.head(3))      