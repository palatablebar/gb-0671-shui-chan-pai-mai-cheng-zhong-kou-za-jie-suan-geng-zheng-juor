import hashlib, json

def archive_decision(state):
    b=state['balance']
    ready=(b['row_balanced'] and b['money_balanced'] and not b['blocked']
        and not b.get('households_blocked'))
    seal=hashlib.sha256(json.dumps({'final':state['final'],'households':state.get('households',[])},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {'seal':seal,'status':'可归档' if ready else '待处理','tickets':len(state['final']),
            'reasons':len(state['quarantine']),'households_blocked':b.get('households_blocked',0)}

def apply(state):
    state['archive']=archive_decision(state)
    state['views']['archive']={'title':'结算封存','rows':state['version_audit'],'metrics':{'封存票':state['archive']['tickets'],'隔离证据':len(state['quarantine']),'未对平户':state['archive']['households_blocked'],'状态':state['archive']['status']}}
