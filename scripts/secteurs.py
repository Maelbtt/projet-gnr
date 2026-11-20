"""Classement des valeurs de l'indice dans les 3 sous-indices S&P (classement manuel)."""
import sys, pandas as pd
E='Énergie'; M='Métaux et mines'; A='Agriculture'
S={E:['SHEL.L','XOM.N','TTEF.PA','CVX.N','BP.L','CNQ.TO','SU.TO','COP.N','ENI.MI','MPC.N','WDS.AX','VLO.N','PSX.N','CVE.TO','REP.MC','EQNR.OL','PBR.N','EOG.N','1605.T','IMO.TO','DVN.N','BKR.O','SLB.N','HAL.N','OXY.N','FANG.O','EQT.N','TENR.MI','EC.N','CCO.TO'],
   M:['BHP.AX','RIO.AX','VALE.N','FMG.AX','AAL.L','GLEN.L','FCX.N','SCCO.N','ANTO.L','FM.TO','TECKb.TO','2899.HK','2259.HK','NEM.N','ABX.TO','AEM.TO','K.TO','NST.AX','AU.N','GFI.N','WPM.TO','FNV.TO','NUE.N','STLD.O','RS.N','MT.AS','5401.T','PKX.N','NHY.OL','1378.HK'],
   A:['NTR.TO','CF.N','MOS.N','YAR.OL','ICL.TA','CTVA.N','VYLR.N','FMC.N','SMG.N','ADM.N','BG.N','WLIL.SI','DAR.N','INGR.N',
      'UPM.HE','STERV.HE','SCAb.ST','3861.T','MNDI.L','SUZ.N','WISA.HE','WFG.TO','WY.N','RYN.N',
      'IP.N','PKG.N','SW.N','AMCR.N','AVY.N','SIGNC.S','SON.N','GPK.N']}
sous={'NTR.TO':'Engrais','CF.N':'Engrais','MOS.N':'Engrais','YAR.OL':'Engrais','ICL.TA':'Engrais',
 'CTVA.N':'Semences et phyto','VYLR.N':'Semences et phyto','FMC.N':'Semences et phyto','SMG.N':'Semences et phyto',
 'ADM.N':'Négoce et transformation','BG.N':'Négoce et transformation','WLIL.SI':'Négoce et transformation','DAR.N':'Négoce et transformation','INGR.N':'Négoce et transformation',
 'MPC.N':'Raffinage','VLO.N':'Raffinage','PSX.N':'Raffinage','BKR.O':'Services pétroliers','SLB.N':'Services pétroliers','HAL.N':'Services pétroliers','TENR.MI':'Services pétroliers','CCO.TO':'Uranium',
 'NEM.N':'Or','ABX.TO':'Or','AEM.TO':'Or','K.TO':'Or','NST.AX':'Or','AU.N':'Or','GFI.N':'Or','2259.HK':'Or','WPM.TO':'Streaming métaux précieux','FNV.TO':'Streaming métaux précieux',
 'NUE.N':'Acier','STLD.O':'Acier','RS.N':'Acier','MT.AS':'Acier','5401.T':'Acier','PKX.N':'Acier','NHY.OL':'Aluminium','1378.HK':'Aluminium',
 'FCX.N':'Cuivre','SCCO.N':'Cuivre','ANTO.L':'Cuivre','FM.TO':'Cuivre','2899.HK':'Cuivre'}
for r in ['BHP.AX','RIO.AX','VALE.N','FMG.AX','AAL.L','GLEN.L','TECKb.TO']: sous[r]='Mines diversifiées et fer'
for r in ['UPM.HE','STERV.HE','SCAb.ST','3861.T','MNDI.L','SUZ.N','WISA.HE','WFG.TO','WY.N','RYN.N']: sous[r]='Papier, bois et forêts'
for r in ['IP.N','PKG.N','SW.N','AMCR.N','AVY.N','SIGNC.S','SON.N','GPK.N']: sous[r]='Emballage'
for r in ['SHEL.L','XOM.N','TTEF.PA','CVX.N','BP.L','ENI.MI','REP.MC','EQNR.OL','PBR.N','IMO.TO','EC.N','SU.TO','CVE.TO']: sous[r]='Pétrolières intégrées'
for r in ['CNQ.TO','COP.N','WDS.AX','EOG.N','1605.T','DVN.N','OXY.N','FANG.O','EQT.N']: sous[r]='Exploration-production'
m={r:s for s,l in S.items() for r in l}
w=pd.read_csv(sys.argv[1],sep=';',decimal=',',encoding='utf-8-sig')
w['secteur']=w.RIC.map(m); w['sous_secteur']=w.RIC.map(sous)
assert w.secteur.notna().all(), w[w.secteur.isna()].RIC.tolist()
assert w.sous_secteur.notna().all(), w[w.sous_secteur.isna()].RIC.tolist()
assert sum(len(v) for v in S.values())==len(set(m))==len(w)
w.to_csv(sys.argv[2],index=False,sep=';',decimal=',',encoding='utf-8-sig',float_format='%.6f')
print(w.groupby('secteur').agg(n=('RIC','size'),poids=('poids_3110','sum')).round(2))
print(w.groupby(['secteur','sous_secteur']).agg(n=('RIC','size'),poids=('poids_3110','sum')).round(2).to_string())
