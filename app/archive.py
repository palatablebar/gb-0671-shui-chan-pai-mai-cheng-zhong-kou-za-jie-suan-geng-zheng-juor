import io, csv, json, zipfile, hashlib, base64
from app.errors import BusinessError

def serialize(result):
    if not result.get('manifest') or not result.get('views'):
        raise BusinessError('INCOMPLETE_RUN','批次尚未完成')
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',json.dumps({**result['manifest'],'revision':result.get('revision',1),'status':result.get('status','待复核')},ensure_ascii=False,indent=2))
        archive.writestr('evidence.json',json.dumps({'counts':result['counts'],'views':result['views'],'quarantine':result['quarantine'],'households':result.get('households',[])},ensure_ascii=False,indent=2))
        snapshot=result.get('input_snapshot')
        if snapshot:
            # 原始称重证据随凭证封存，重跑与归档均不改写
            archive.writestr('source.csv',base64.b64decode(snapshot['bytes_b64']))
    return buffer.getvalue()
