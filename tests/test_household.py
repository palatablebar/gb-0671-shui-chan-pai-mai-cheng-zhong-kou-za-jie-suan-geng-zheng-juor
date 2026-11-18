from app.engine import evaluate
from app.modules.reconcile.rules import households
from app.modules.archive.rules import archive_decision
from app.archive import serialize
from app import store
from copy import deepcopy
import io, zipfile, json, base64

# 复秤更正减重，整户累计净重跌破档位：应退返利
DROP_CSV = """id,ticket,buyer,kind,weight,unit,fish,price,rate,version,replaces,paid
a1,00001,B001,gross,1310,kg,黄鱼,12.30,0.05,1,,0
a2,00001,B001,tare,10,kg,黄鱼,12.30,0.05,1,,0
b1,00002,B001,gross,310,kg,黄鱼,12.30,0.05,1,,0
b2,00002,B001,tare,10,kg,黄鱼,12.30,0.05,1,,0
c1,00001,B001,gross,1110,kg,黄鱼,12.30,0.05,2,1,15190.50
c2,00001,B001,tare,10,kg,黄鱼,12.30,0.05,2,1,0
"""

# 断裂更正：v3 声明替代 v1，但当前生效版是 v2
STALE_CSV = """id,ticket,buyer,kind,weight,unit,fish,price,rate,version,replaces,paid
a1,00001,B001,gross,1310,kg,黄鱼,12.30,0.05,1,,0
a2,00001,B001,tare,10,kg,黄鱼,12.30,0.05,1,,0
c1,00001,B001,gross,1110,kg,黄鱼,12.30,0.05,2,1,15190.50
c2,00001,B001,tare,10,kg,黄鱼,12.30,0.05,2,1,0
d1,00001,B001,gross,1150,kg,黄鱼,12.30,0.05,3,1,0
d2,00001,B001,tare,10,kg,黄鱼,12.30,0.05,3,1,0
"""

def test_tier_real(sample):
    h=sample['households'][0]
    assert h['buyer']=='B001' and h['net_kg']=='2029' and h['per_kg']=='0.35'

def test_rebate_ledger_real(sample):
    # 当前态2029kg×0.35=710.15；上一确认态2019kg×0.20=403.80；只付差额
    h=sample['households'][0]
    assert h['rebate']=='710.15' and h['granted']=='403.80' and h['delta']=='306.35'

def test_household_payable_real(sample):
    h=sample['households'][0]
    assert h['payable']=='22998.76' and h['due']=='22234.06' and h['balanced']
    assert h['trigger']=='00001 v1→v2' and h['lines']

def test_confirmed_tickets_untouched(sample):
    # 整户重算不改写票账：票应付/已付/待付保持原口径
    assert sample['balance']['amount']=='23708.91'
    assert sample['balance']['paid']=='1168.50'
    assert sample['balance']['due']=='22540.41'
    assert sample['balance']['payable']=='22998.76'
    assert sample['balance']['household_due']=='22234.06'

def test_drop_below_tier():
    s=evaluate({'csv_text':DROP_CSV})
    h=s['households'][0]
    assert h['net_kg']=='1400' and h['per_kg']=='0'
    assert h['granted']=='320.00' and h['rebate']=='0.00' and h['delta']=='-320.00'
    assert h['payable']=='16359.00' and h['due']=='1488.50' and h['balanced']

def test_switch_failure_keeps_previous():
    s=evaluate({'csv_text':STALE_CSV})
    kept=[r for r in s['final'] if r['ticket']=='00001']
    assert kept[0]['version']==2 and kept[0]['code']=='KEPT_PREVIOUS'
    assert s['version_conflicts'][0]['code']=='STALE_CORRECTION'
    assert s['balance']['households_blocked']==1
    assert s['archive']['status']=='待处理'

def test_unbalanced_household_detected(sample):
    s=deepcopy(sample);s['final'][0]['due']='1'
    assert not households(s)[0]['balanced']

def test_archive_blocks_unbalanced(sample):
    s=deepcopy(sample);s['balance']['households_blocked']=1
    assert archive_decision(s)['status']=='待处理'

def test_rerun_adds_no_rebate(tmp_path):
    path=str(tmp_path/'rerun.sqlite')
    first=store.save(path,evaluate())
    second=store.save(path,evaluate())
    assert first['manifest']['run_id']==second['manifest']['run_id']
    assert len(store.history(path))==1
    replay=evaluate({'dataset':'dirty'},snapshot=first['input_snapshot'])
    assert replay['households']==first['households']
    assert replay['manifest']['run_id']==first['manifest']['run_id']

def test_export_keeps_source_and_households(sample):
    z=zipfile.ZipFile(io.BytesIO(serialize(sample)))
    assert z.read('source.csv')==base64.b64decode(sample['input_snapshot']['bytes_b64'])
    data=json.loads(z.read('evidence.json'))
    assert data['households'][0]['delta']=='306.35'
    assert len(data['quarantine'])==8

def test_quarantine_evidence_kept(sample):
    raw=next(r for r in sample['quarantine'] if r['id']=='bad-1')
    assert raw['raw']['weight']=='NULL' and raw['line']==44
