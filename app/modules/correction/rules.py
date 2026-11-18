from collections import defaultdict
from decimal import Decimal
from app.coerce import money

def select_versions(settlements):
    grouped=defaultdict(list)
    for row in settlements: grouped[row['ticket']].append(row)
    final=[];conflicts=[];audit=[]
    for ticket,versions in sorted(grouped.items()):
        current=None;stale=False
        for row in sorted(versions,key=lambda r:r['version']):
            target=row['replaces'].strip()
            if current is None:
                if target: conflicts.append({'ticket':ticket,'buyer':row.get('buyer',''),'code':'MISSING_BASE','version':row['version']});current=None;break
            elif target!=str(current['version']):
                # 切换失败保留旧版：当前生效版继续结算，断裂版本记入冲突并阻断该户对平
                conflicts.append({'ticket':ticket,'buyer':row.get('buyer',''),'code':'STALE_CORRECTION','version':row['version'],'expected':current['version'],'kept':current['version']})
                stale=True;break
            audit.append({'ticket':ticket,'version':row['version'],'replaces':target,'amount':row['amount'],'lines':row['lines']})
            current=row
        if current:
            paid=max(Decimal(r['paid']) for r in versions)
            code='KEPT_PREVIOUS' if stale else ('CORRECTED' if len(versions)>1 else 'ORIGINAL')
            final.append({**current,'paid':money(paid),'due':money(Decimal(current['amount'])-paid),'code':code})
    return final,conflicts,audit

def apply(state):
    final,conflicts,audit=select_versions(state['settlements'])
    state.update(final=final,version_conflicts=conflicts,version_audit=audit)
    kept=sum(1 for r in final if r['code']=='KEPT_PREVIOUS')
    state['views']['correction']={'title':'更正裁决','rows':final+conflicts,'metrics':{'生效票':len(final),'版本冲突':len(conflicts),'保留旧版':kept,'追溯版':len(audit)}}
