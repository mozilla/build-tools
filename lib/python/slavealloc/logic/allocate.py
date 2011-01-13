from slavealloc import exceptions
from slavealloc.data import queries, model

class Allocation(object):
    """A container class to hold all of the information necessary to make an allocation"""
    # (all fields filled in by get_allocation)
    slavename = None # the slave name
    slaveid = None # its slaveid
    master_row = None # a row from the masters table
    slave_row = None # the slave's row
    slave_password = None # the slave's password

    def commit(self):
        """
        Commit this allocation to the database
        """
        q = model.slaves.update(whereclause=(model.slaves.c.slaveid == self.slaveid),
                            values=dict(current_masterid=self.master_row.masterid))
        q.execute()

def get_allocation(slavename):
    """
    Return the C{masters} row for the master to which C{slavename}
    should be assigned.
    """
    allocation = Allocation()
    allocation.slavename = slavename

    q = model.slaves.select(whereclause=(model.slaves.c.name == slavename))
    allocation.slave_row = q.execute().fetchone()
    if not allocation.slave_row:
        raise exceptions.NoAllocationError

    allocation.slaveid = allocation.slave_row.slaveid

    q = queries.slave_password
    allocation.slave_password = q.execute(slaveid=allocation.slaveid).scalar()

    # if this slave has a locked_masterid, just get that row; otherwise, run
    # the allocation algorithm
    if allocation.slave_row.locked_masterid:
        q = model.masters.select(whereclause=(
            model.masters.c.masterid == allocation.slave_row.locked_masterid))
        allocation.master_row = q.execute().fetchone()
    else:
        # TODO: use slaveid, lose a join
        q = queries.best_master
        allocation.master_row = q.execute(slavename=slavename).fetchone()

    if not allocation.master_row:
        raise exceptions.NoAllocationError

    return allocation
