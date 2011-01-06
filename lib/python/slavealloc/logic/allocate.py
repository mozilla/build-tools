from slavealloc import exceptions
from slavealloc.data import queries, model

def get_allocation(eng, slavename):
    """
    Return the C{masters} row for the master to which C{slavename}
    should be assigned.
    """
    q = queries.best_master
    q.bind = eng
    allocation = q.execute(slavename=slavename).fetchone()
    if not allocation:
        raise exceptions.NoAllocationError
    return allocation

def allocate(eng, slavename, allocation):
    """
    Allocate C{slavename} to the master given by C{allocation} (as returned by
    get_allocation).
    """
    q = model.slaves.update(whereclause=(model.slaves.c.name == slavename),
                        values=dict(current_masterid=allocation.masterid))
    eng.execute(q)
