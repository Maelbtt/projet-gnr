"""Poids de l'indice S&P Global Natural Resources au 31/10/2026.
Méthode : nombre d'actions SSGA (GNR) au 18/11 x cours de clôture au 30/10 en USD (LSEG, Curn=USD)."""
import sys, pandas as pd
hold, rics, px_f, out = sys.argv[1:5]
h=pd.read_csv(hold,sep=';',skiprows=4,encoding='latin-1',nrows=116,usecols=range(8))
h['sh']=h['Shares Held'].str.replace(',','.').astype(float)
h['w_ssga']=h.Weight.str.replace(',','.').astype(float)
# Nutrien : deux cotations (CAD, USD) d'une même société -> on additionne les actions
h.loc[h.Ticker=='NTR','sh']=h.loc[h.Ticker=='NTR','sh'].sum()
h=h[~((h.Ticker=='NTR')&(h['Local Currency']=='USD'))]
m=pd.read_csv(rics,sep=';',encoding='utf-8-sig')
m['RIC']=m.RIC.replace({'TTE.PA':'TTEF.PA','TEN.MI':'TENR.MI'})
px=pd.read_csv(px_f,sep=';',encoding='utf-8-sig'); px.columns=['RIC','_','px_usd','date','ccy_px']
px['px_usd']=pd.to_numeric(px.px_usd.astype(str).str.replace(',','.'),errors='coerce')
d=m.merge(h[['Name','Ticker','sh','w_ssga']],on=['Name','Ticker']).merge(px[['RIC','px_usd']],on='RIC',how='left')
d['mv_usd']=d.sh*d.px_usd
d['poids_3110']=d.mv_usd/d.mv_usd.sum()*100
d['poids_3110']=d.poids_3110.fillna(0)          # Wisa : pas coté au 30/10
d['w_ssga_1811']=d.w_ssga/d.w_ssga.sum()*100
d=d.sort_values('poids_3110',ascending=False)
d[['RIC','Name','Local Currency','sh','px_usd','poids_3110','w_ssga_1811']].rename(columns={'Local Currency':'devise','sh':'nb_actions'}).to_csv(out,index=False,sep=';',decimal=',',encoding='utf-8-sig',float_format='%.6f')
print(d[['Name','poids_3110']].head(10).round(2).to_string(index=False))
print('somme',d.poids_3110.sum().round(4),'| lignes >0',(d.poids_3110>0).sum())
c=d.groupby('Local Currency').poids_3110.sum().sort_values(ascending=False).round(2); print(c.to_string())
