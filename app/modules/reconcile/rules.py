from collections import defaultdict
from decimal import Decimal
from app.coerce import money

def tier_of(tiers, weight):
    current={'min_kg':'0','per_kg':'0'}
    for tier in sorted(tiers,key=lambda t:Decimal(t['min_kg'])):
        if weight>=Decimal(tier['min_kg']): current=tier
    return current

def households(state):
    tiers=state['context'].get('rebate',{}).get('tiers',[])
    versions=defaultdict(dict)
    for row in state['settlements']: versions[row['ticket']][row['version']]=row
    conflicts=defaultdict(list)
    for row in state['version_conflicts']: conflicts[row.get('buyer','')].append(row)
    groups=defaultdict(list)
    for row in state['final']: groups[row['buyer']].append(row)
    homes=[]
    for buyer,rows in sorted(groups.items()):
        weight=sum((Decimal(r['net_kg']) for r in rows),Decimal(0))
        amount=sum((Decimal(r['amount']) for r in rows),Decimal(0))
        paid=sum((Decimal(r['paid']) for r in rows),Decimal(0))
        due=sum((Decimal(r['due']) for r in rows),Decimal(0))
        tier=tier_of(tiers,weight)
        rebate=money(Decimal(tier['per_kg'])*weight)
        # 上一确认态：本批被更正的票回退到其 replaces 指向的版本，重算整户净重与档位
        prev_weight=weight;triggers=[];lines=[];base_missing=False
        for row in rows:
            if row['version']>1:
                prev=versions.get(row['ticket'],{}).get(int(row['replaces'] or 0))
                if prev is None: base_missing=True;continue
                prev_weight+=Decimal(prev['net_kg'])-Decimal(row['net_kg'])
                triggers.append(f"{row['ticket']} v{prev['version']}→v{row['version']}")
                lines.extend(prev['lines']+row['lines'])
        prev_tier=tier_of(tiers,prev_weight)
        granted=money(Decimal(prev_tier['per_kg'])*prev_weight)
        delta=money(Decimal(rebate)-Decimal(granted))
        payable=money(amount-Decimal(rebate))
        household_due=money(due-Decimal(delta))
        # 对平：票账、返利账各自独立重算勾稽，且户内无版本冲突、回退基准齐全
        balanced=(not base_missing and not conflicts.get(buyer)
            and amount==paid+due
            and Decimal(rebate)==Decimal(granted)+Decimal(delta)
            and Decimal(payable)==amount-Decimal(rebate)
            and Decimal(payable)==paid-Decimal(granted)+Decimal(household_due))
        homes.append({'buyer':buyer,'tickets':len(rows),'net_kg':str(weight),'per_kg':tier['per_kg'],
            'tier':f"≥{tier['min_kg']}kg·{tier['per_kg']}/kg",'amount':money(amount),'rebate':rebate,
            'granted':granted,'delta':delta,'payable':payable,'paid':money(paid),'due':household_due,
            'trigger':'、'.join(triggers),'lines':sorted(set(lines)),'balanced':balanced})
    return homes

def balance(state):
    c=state['counts'];accepted=len(state['records']);quarantined=len(state['quarantine'])
    explained=accepted+quarantined+c['blank']+c['duplicate']+c['repeated_header']
    total=sum((Decimal(r['amount']) for r in state['final']),Decimal(0))
    paid=sum((Decimal(r['paid']) for r in state['final']),Decimal(0));due=sum((Decimal(r['due']) for r in state['final']),Decimal(0))
    homes=state.get('households',[])
    rebate=sum((Decimal(h['rebate']) for h in homes),Decimal(0))
    granted=sum((Decimal(h['granted']) for h in homes),Decimal(0))
    delta=sum((Decimal(h['delta']) for h in homes),Decimal(0))
    return {'input':c['input'],'accepted':accepted,'quarantined':quarantined,'blank':c['blank'],'duplicate':c['duplicate'],
      'repeated_header':c['repeated_header'],'row_balanced':explained==c['input'],'amount':money(total),'paid':money(paid),'due':money(due),
      'money_balanced':total==paid+due,'blocked':len(state['version_conflicts']),
      'rebate':money(rebate),'granted':money(granted),'delta':money(delta),
      'payable':money(total-rebate),'household_due':money(due-delta),
      'households':len(homes),'households_blocked':sum(1 for h in homes if not h['balanced'])}

def apply(state):
    state['households']=households(state)
    state['balance']=balance(state)
    state['views']['reconcile']={'title':'整户返利台账','rows':state['households'],'metrics':{'整户应付_CNY':state['balance']['payable'],'返利差额_CNY':state['balance']['delta'],'未对平户':state['balance']['households_blocked']}}
