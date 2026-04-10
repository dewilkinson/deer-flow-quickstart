import pandas as pd
import numpy as np
from smartmoneyconcepts import smc

df=pd.DataFrame({
    'open':np.random.rand(100),
    'high':np.random.rand(100),
    'low':np.random.rand(100),
    'close':np.random.rand(100),
    'volume':np.random.rand(100)
})
swings=smc.swing_highs_lows(df)

bos=smc.bos_choch(df, swings)
fvg=smc.fvg(df)
ob=smc.ob(df, swings)
liq=smc.liquidity(df, swings)

with open("smc_cols.txt", "w", encoding="utf-8") as f:
    f.write("BOS: " + str(bos.columns.tolist()) + "\n")
    f.write("FVG: " + str(fvg.columns.tolist()) + "\n")
    f.write("OB: " + str(ob.columns.tolist()) + "\n")
    f.write("LIQ: " + str(liq.columns.tolist()) + "\n")
