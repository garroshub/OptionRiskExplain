"""Generate synthetic EOD option positions with two exception cases."""
import csv
from datetime import date
from pathlib import Path
from option_lab import price_european

ROOT = Path(__file__).resolve().parents[1]
FIELDS=("as_of","underlying","option_type","expiry","strike","quantity",
        "multiplier","spot","mark","volatility","rate","dividend_yield","bid","ask","source")
BOOK=[
    ("SPY","call","2026-11-20",550,25,100,550,545,.22,.23,.010),
    ("SPY","put","2026-11-20",535,-14,100,550,545,.24,.25,.010),
    ("SPY","call","2026-12-18",570,-10,100,550,545,.215,.218,.010),
    ("AAPL","call","2026-11-20",255,40,100,250,253,.32,.325,.005),
    ("AAPL","put","2026-11-20",240,15,100,250,253,.35,.348,.005),
]
for i,as_of in enumerate(("2026-10-05","2026-10-06")):
    rows=[]
    for sym,side,expiry,k,q,m,s0,s1,v0,v1,div in BOOK:
        spot=(s0,s1)[i]; vol=(v0,v1)[i]; rate=(.041,.040)[i]
        days=(date.fromisoformat(expiry)-date.fromisoformat(as_of)).days
        model=price_european(spot,k,days/365,rate,div,vol)[side]
        mark=round(model,2)
        # Market/model basis adjustment.
        if i==1 and sym=="SPY" and side=="call" and k==550:
            mark=round(mark+.45,2)
        bid=round(max(0,mark-.12),2);ask=round(mark+.12,2)
        # Mark outside quoted spread.
        if i==1 and sym=="AAPL" and side=="put":
            bid=round(mark+.12,2);ask=round(mark+.36,2)
        rows.append({
            "as_of":as_of,"underlying":sym,"option_type":side,"expiry":expiry,
            "strike":k,"quantity":q,"multiplier":m,"spot":spot,"mark":mark,
            "volatility":vol,"rate":rate,"dividend_yield":div,
            "bid":bid,"ask":ask,"source":"SYNTHETIC_EOD"
        })
    target=ROOT/"examples"/f"positions_{as_of}.csv"
    target.parent.mkdir(exist_ok=True)
    with target.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
    print("SYNTHETIC_SNAPSHOT",as_of,len(rows),target)
