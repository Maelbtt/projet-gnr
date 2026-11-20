import sys, pandas as pd
df=pd.read_csv(sys.argv[1],sep=';',skiprows=4,encoding='latin-1',nrows=116,usecols=range(8))
df['w']=df.Weight.str.replace(',','.').astype(float)
eq=df[(df.Ticker!='-')&~df.Name.str.contains('DEC26')&(df.w>0)].copy()
eq=eq[~((eq.Ticker=='NTR')&(eq['Local Currency']=='USD'))]  # doublon Nutrien
suf={'GBP':'.L','CAD':'.TO','AUD':'.AX','SEK':'.ST','NOK':'.OL','JPY':'.T','HKD':'.HK','ILS':'.TA','SGD':'.SI','CHF':'.S'}
eur={'TTE':'TTEF.PA','UPM':'UPM.HE','STERV':'STERV.HE','ENI':'ENI.MI','REP':'REP.MC','MT':'MT.AS','TEN':'TENR.MI','WISA':'WISA.HE'}
special={'BP.':'BP.L','SCA B':'SCAb.ST','TECK.B':'TECKb.TO','F34':'WLIL.SI','SIGN':'SIGNC.S','FANG':'FANG.O','BKR':'BKR.O','STLD':'STLD.O'}
def ric(r):
    t,c=r.Ticker.strip(),r['Local Currency']
    if t in special: return special[t]
    if c=='EUR': return eur.get(t,t)
    if c=='USD': return t+'.N'
    return t+suf.get(c,'')
eq['RIC']=eq.apply(ric,axis=1)
eq[['RIC','Name','Ticker','Local Currency']].to_csv(sys.argv[2],index=False,sep=';',encoding='utf-8-sig')
print(len(eq)); print(eq.RIC.tolist())
