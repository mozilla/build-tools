from sqlalchemy import types, exceptions

class Enum(types.TypeDecorator):
  impl = types.Unicode
  
  def __init__(self, values, empty_to_none=False, strict=False):
    """Emulate an Enum type.

    values:
       A list of valid values for this column
    empty_to_none:
       Optional, treat the empty string '' as None
    strict:
       Also insist that columns read from the database are in the
       list of valid values.  Note that, with strict=True, you won't
       be able to clean out bad data from the database through your
       code.
    """

    if values is None or len(values) is 0:
      raise exceptions.AssertionError('Enum requires a list of values')
    self.empty_to_none = empty_to_none
    self.strict = strict
    self.values = values[:]

    # The length of the string/unicode column should be the longest string
    # in values
    size = max([len(v) for v in values if v is not None])
    super(Enum, self).__init__(size)    
    
    
  def convert_bind_param(self, value, engine):
    if self.empty_to_none and value is '':
      value = None
    if value not in self.values:
      raise exceptions.AssertionError('"%s" not in Enum.values' % value)
    return super(Enum, self).convert_bind_param(value, engine)
    
    
  def convert_result_value(self, value, engine):
    if self.strict and value not in self.values:
      raise exceptions.AssertionError('"%s" not in Enum.values' % value)
    return super(Enum, self).convert_result_value(value, engine)

if __name__ == '__main__':
  from sqlalchemy import *
  t = Table('foo', MetaData('sqlite:///'),
        Column('id', Integer, primary_key=True),
        Column('e', Enum(['foobar', 'baz', 'quux', None])))
  t.create()

  t.insert().execute(e='foobar')
  t.insert().execute(e='baz')
  t.insert().execute(e='quux')
  t.insert().execute(e=None)
  # boom!
  t.insert().execute(e='lala')
  
  print list(t.select().execute())
