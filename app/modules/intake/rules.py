from .reader import read_source
FIELDS=['id', 'ticket', 'buyer', 'kind', 'weight', 'unit', 'fish', 'price', 'rate', 'version', 'replaces', 'paid']
def apply(state):
    read_source(state,FIELDS,{'编号':'id','买家':'buyer'})
