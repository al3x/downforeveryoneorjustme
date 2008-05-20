"""
Database API
(part of web.py)
"""

__all__ = [
  "UnknownParamstyle", "UnknownDB", "TransactionError", 
  "sqllist", "sqlors", "reparam", "sqlquote",
  "SQLQuery", "SQLParam", "sqlparam",
  "SQLLiteral", "sqlliteral",
  "database", 'DB',
]

import time
try:
    import datetime
except ImportError:
    datetime = None

from utils import threadeddict, storage, iters, iterbetter

try:
    # db module can work independent of web.py
    from webapi import debug
except:
    import sys
    debug = sys.stderr

class UnknownDB(Exception):
    """raised for unsupported dbms"""
    pass

class _ItplError(ValueError): 
    def __init__(self, text, pos):
        ValueError.__init__(self)
        self.text = text
        self.pos = pos
    def __str__(self):
        return "unfinished expression in %s at char %d" % (
            repr(self.text), self.pos)

class TransactionError(Exception): pass

class UnknownParamstyle(Exception): 
    """
    raised for unsupported db paramstyles

    (currently supported: qmark, numeric, format, pyformat)
    """
    pass
    
class SQLParam:
    """Parameter in SQLQuery.
    
        >>> q = SQLQuery(["SELECT * FROM test WHERE name=", SQLParam("joe")])
        >>> q
        <sql: "SELECT * FROM test WHERE name='joe'">
        >>> q.query()
        'SELECT * FROM test WHERE name=%s'
        >>> q.values()
        ['joe']
    """
    def __init__(self, value):
        self.value = value
        
    def get_marker(self, paramstyle='pyformat'):
        if paramstyle == 'qmark':
            return '?'
        elif paramstyle == 'numeric':
            return ':1'
        elif paramstyle is None or paramstyle in ['format', 'pyformat']:
            return '%s'
        raise UnknownParamstyle, paramstyle
        
    def sqlquery(self): 
        return SQLQuery([self])
        
    def __add__(self, other):
        return self.sqlquery() + other
        
    def __radd__(self, other):
        return other + self.sqlquery() 
            
    def __str__(self): 
        return str(self.value)
    
    def __repr__(self):
        return '<param: %s>' % repr(self.value)

sqlparam =  SQLParam

class SQLQuery:
    """
    You can pass this sort of thing as a clause in any db function.
    Otherwise, you can pass a dictionary to the keyword argument `vars`
    and the function will call reparam for you.
    """
    # tested in sqlquote's docstring
    def __init__(self, items=[]):
        """Creates a new SQLQuery.
        
            >>> SQLQuery("x")
            <sql: 'x'>
            >>> q = SQLQuery(['SELECT * FROM ', 'test', ' WHERE x=', SQLParam(1)])
            >>> q
            <sql: 'SELECT * FROM test WHERE x=1'>
            >>> q.query(), q.values()
            ('SELECT * FROM test WHERE x=%s', [1])
            >>> SQLQuery(SQLParam(1))
            <sql: '1'>
        """
        if isinstance(items, list):
            self.items = items
        elif isinstance(items, SQLParam):
            self.items = [items]
        elif isinstance(items, SQLQuery):
            self.items = list(items.items)
        else:
            self.items = [str(items)]
            
        # Take care of SQLLiterals
        for i, item in enumerate(self.items):
            if isinstance(item, SQLParam) and isinstance(item.value, SQLLiteral):
                self.items[i] = item.value.v

    def __add__(self, other):
        if isinstance(other, str):
            items = [other]
        elif isinstance(other, SQLQuery):
            items = other.items
        else:
            return NotImplemented
        return SQLQuery(self.items + items)

    def __radd__(self, other):
        if isinstance(other, str):
            items = [other]
        else:
            return NotImplemented
            
        return SQLQuery(items + self.items)

    def __len__(self):
        return len(self.query())
        
    def query(self, paramstyle=None):
        """
        Returns the query part of the sql query.
            >>> q = SQLQuery(["SELECT * FROM test WHERE name=", SQLParam('joe')])
            >>> q.query()
            'SELECT * FROM test WHERE name=%s'
            >>> q.query(paramstyle='qmark')
            'SELECT * FROM test WHERE name=?'
        """
        s = ''
        for x in self.items:
            if isinstance(x, SQLParam):
                x = x.get_marker(paramstyle)
            s += x
        return s
    
    def values(self):
        """
        Returns the values of the parameters used in the sql query.
            >>> q = SQLQuery(["SELECT * FROM test WHERE name=", SQLParam('joe')])
            >>> q.values()
            ['joe']
        """
        return [i.value for i in self.items if isinstance(i, SQLParam)]
        
    def join(items, sep=' '):
        """
        Joins multiple queries.
        
        >>> SQLQuery.join(['a', 'b'], ', ')
        <sql: 'a, b'>
        """
        if len(items) == 0:
            return SQLQuery("")
            
        q = SQLQuery(items[0])
        for i in items[1:]:
            q = q + sep + i
        
        return q
    
    join = staticmethod(join)

    def __str__(self):
        try:
            return self.query() % tuple([sqlify(x) for x in self.values()])
        except (ValueError, TypeError):
            return self.query()

    def __repr__(self):
        return '<sql: %s>' % repr(str(self))

class SQLLiteral: 
    """
    Protects a string from `sqlquote`.

        >>> sqlquote('NOW()')
        <sql: "'NOW()'">
        >>> sqlquote(SQLLiteral('NOW()'))
        <sql: 'NOW()'>
    """
    def __init__(self, v): 
        self.v = v

    def __repr__(self): 
        return self.v

sqlliteral = SQLLiteral

def reparam(string_, dictionary): 
    """
    Takes a string and a dictionary and interpolates the string
    using values from the dictionary. Returns an `SQLQuery` for the result.

        >>> reparam("s = $s", dict(s=True))
        <sql: "s = 't'">
    """
    vals = []
    result = []
    for live, chunk in _interpolate(string_):
        if live:
            v = eval(chunk, dictionary)
            result.append(sqlparam(v))
        else: 
            result.append(chunk)
    return SQLQuery.join(result, '')

def sqlify(obj): 
    """
    converts `obj` to its proper SQL version

        >>> sqlify(None)
        'NULL'
        >>> sqlify(True)
        "'t'"
        >>> sqlify(3)
        '3'
    """
    # because `1 == True and hash(1) == hash(True)`
    # we have to do this the hard way...

    if obj is None:
        return 'NULL'
    elif obj is True:
        return "'t'"
    elif obj is False:
        return "'f'"
    elif datetime and isinstance(obj, datetime.datetime):
        return repr(obj.isoformat())
    else:
        return repr(obj)

def sqllist(lst): 
    """
    Converts the arguments for use in something like a WHERE clause.
    
        >>> sqllist(['a', 'b'])
        'a, b'
        >>> sqllist('a')
        'a'
    """
    if isinstance(lst, str): 
        return lst
    else:
        return ', '.join(lst)

def sqlors(left, lst):
    """
    `left is a SQL clause like `tablename.arg = ` 
    and `lst` is a list of values. Returns a reparam-style
    pair featuring the SQL that ORs together the clause
    for each item in the lst.

        >>> sqlors('foo = ', [])
        <sql: '2+2=5'>
        >>> sqlors('foo = ', [1])
        <sql: 'foo = 1'>
        >>> sqlors('foo = ', 1)
        <sql: 'foo = 1'>
        >>> sqlors('foo = ', [1,2,3])
        <sql: '(foo = 1 OR foo = 2 OR foo = 3)'>
    """
    if isinstance(lst, iters):
        lst = list(lst)
        ln = len(lst)
        if ln == 0:
            return SQLQuery("2+2=5")
        if ln == 1:
            lst = lst[0]

    if isinstance(lst, iters):
        return '(' + SQLQuery.join([left + sqlparam(x) for x in lst], ' OR ') + ')'
    else:
        return left + sqlparam(lst)
        
def sqlwhere(dictionary, grouping=' AND '): 
    """
    Converts a `dictionary` to an SQL WHERE clause `SQLQuery`.
    
        >>> sqlwhere({'cust_id': 2, 'order_id':3})
        <sql: 'order_id = 3 AND cust_id = 2'>
        >>> sqlwhere({'cust_id': 2, 'order_id':3}, grouping=', ')
        <sql: 'order_id = 3, cust_id = 2'>
        >>> sqlwhere({'a': 'a', 'b': 'b'}).query()
        'a = %s AND b = %s'
    """
    return SQLQuery.join([k + ' = ' + sqlparam(v) for k, v in dictionary.items()], grouping)

def sqlquote(a): 
    """
    Ensures `a` is quoted properly for use in a SQL query.

        >>> 'WHERE x = ' + sqlquote(True) + ' AND y = ' + sqlquote(3)
        <sql: "WHERE x = 't' AND y = 3">
    """
    return sqlparam(a).sqlquery()

class Transaction:
    """Database transaction."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.transaction_count = transaction_count = len(ctx.transactions)

        class transaction_engine:
            def do_transact(self):
                ctx.db.commit()

            def do_commit(self):
                ctx.db.commit()

            def do_rollback(self):
                ctx.db.rollback()

        class subtransaction_engine:
            def query(self, q):
                db_cursor = ctx.db.cursor()
                ctx.db_execute(db_cursor, SQLQuery(q % transaction_count))

            def do_transact(self):
                self.query('SAVEPOINT webpy_sp_%s')

            def do_commit(self):
                self.query('RELEASE SAVEPOINT webpy_sp_%s')

            def do_rollback(self):
                self.query('ROLLBACK TO SAVEPOINT webpy_sp_%s')

        class dummy_engine:
            do_transact = do_commit = do_rollback = lambda self: None

        if self.transaction_count:
            # nested transactions are not supported in some databases
            if self.ctx.get('ignore_nested_transactions'):
                self.engine = dummy_engine()
            else:
                self.engine = subtransaction_engine()
        else:
            self.engine = transaction_engine()

        self.engine.do_transact()
        self.ctx.transactions.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exctype, excvalue, traceback):
        if exctype is not None:
            self.rollback()
        else:
            self.commit()

    def commit(self):
        if len(self.ctx.transactions) > self.transaction_count:
            self.engine.do_commit()
            self.ctx.transactions = self.ctx.transactions[:self.transaction_count]

    def rollback(self):
        if len(self.ctx.transactions) > self.transaction_count:
            self.engine.do_rollback()
            self.ctx.transactions = self.ctx.transactions[:self.transaction_count]

class DB: 
    """Database"""
    def __init__(self):
        self._ctx = threadeddict()

        # flag to enable/disable printing queries
        self.printing = False

    def _getctx(self): 
        if not self._ctx.get('db'):
            self._load_context()
        return self._ctx
    ctx = property(_getctx)

    def _load_context(self):
        self._ctx.dbq_count = 0
        self._ctx.transactions = [] # stack of transactions
        self._ctx.db = self.db_module.connect(**self.keywords)
        self._ctx.db_execute = self._db_execute
        
        if not hasattr(self._ctx.db, 'commit'):
            self._ctx.db.commit = lambda: None

        if not hasattr(self._ctx.db, 'rollback'):
            self._ctx.db.rollback = lambda: None

    def _db_cursor(self):
        return self.ctx.db.cursor()

    def _param_marker(self):
        """Returns parameter marker based on paramstyle attribute if this database."""
        style = getattr(self, 'paramstyle', 'pyformat')

        if style == 'qmark':
            return '?'
        elif style == 'numeric':
            return ':1'
        elif style in ['format', 'pyformat']:
            return '%s'
        raise UnknownParamstyle, style

    def _db_execute(self, cur, sql_query, dorollback=True): 
        """executes an sql query"""
        self.ctx.dbq_count += 1

        try:
            a = time.time()
            paramstyle = getattr(self, 'paramstyle', 'pyformat')
            out = cur.execute(sql_query.query(paramstyle), sql_query.values())
            b = time.time()
        except:
            if self.printing:
                print >> debug, 'ERR:', str(sql_query)
            if dorollback: 
                if self.ctx.transactions:
                    self.ctx.transactions[-1].rollback()
                else:
                    self.ctx.db.rollback()
            raise

        if self.printing:
            print >> debug, '%s (%s): %s' % (round(b-a, 2), self.ctx.dbq_count, str(sql_query))
        return out
    
    def _where(self, where, vars): 
        if isinstance(where, (int, long)):
            where = "id = " + sqlparam(where)
        #@@@ for backward-compatibility
        elif isinstance(where, (list, tuple)) and len(where) == 2:
            where = SQLQuery(where[0], where[1])
        elif isinstance(where, SQLQuery):
            pass
        else:
            where = reparam(where, vars)        
        return where
    
    def query(self, sql_query, vars=None, processed=False, _test=False): 
        """
        Execute SQL query `sql_query` using dictionary `vars` to interpolate it.
        If `processed=True`, `vars` is a `reparam`-style list to use 
        instead of interpolating.
        
            >>> db = DB()
            >>> db.query("SELECT * FROM foo", _test=True)
            <sql: 'SELECT * FROM foo'>
            >>> db.query("SELECT * FROM foo WHERE x = $x", vars=dict(x='f'), _test=True)
            <sql: "SELECT * FROM foo WHERE x = 'f'">
            >>> db.query("SELECT * FROM foo WHERE x = " + sqlquote('f'), _test=True)
            <sql: "SELECT * FROM foo WHERE x = 'f'">
        """
        if vars is None: vars = {}
        
        if not processed and not isinstance(sql_query, SQLQuery):
            sql_query = reparam(sql_query, vars)
        
        if _test: return sql_query
        
        db_cursor = self._db_cursor()
        self._db_execute(db_cursor, sql_query)
        
        if db_cursor.description:
            names = [x[0] for x in db_cursor.description]
            def iterwrapper():
                row = db_cursor.fetchone()
                while row:
                    yield storage(dict(zip(names, row)))
                    row = db_cursor.fetchone()
            out = iterbetter(iterwrapper())
            out.__len__ = lambda: int(db_cursor.rowcount)
            out.list = lambda: [storage(dict(zip(names, x))) \
                               for x in db_cursor.fetchall()]
        else:
            out = db_cursor.rowcount
        
        if not self.ctx.transactions: self.ctx.db.commit()
        return out
    
    def select(self, tables, vars=None, what='*', where=None, order=None, group=None, 
               limit=None, offset=None, _test=False): 
        """
        Selects `what` from `tables` with clauses `where`, `order`, 
        `group`, `limit`, and `offset`. Uses vars to interpolate. 
        Otherwise, each clause can be a SQLQuery.
        
            >>> db = DB()
            >>> db.select('foo', _test=True)
            <sql: 'SELECT * FROM foo'>
            >>> db.select(['foo', 'bar'], where="foo.bar_id = bar.id", limit=5, _test=True)
            <sql: 'SELECT * FROM foo, bar WHERE foo.bar_id = bar.id LIMIT 5'>
        """
        if vars is None: vars = {}
        sql_clauses = self.sql_clauses(what, tables, where, group, order, limit, offset)
        clauses = [self.gen_clause(sql, val, vars) for sql, val in sql_clauses if val is not None]
        qout = SQLQuery.join(clauses)
        if _test: return qout
        return self.query(qout, processed=True)
    
    def sql_clauses(self, what, tables, where, group, order, limit, offset): 
        return (
            ('SELECT', what),
            ('FROM', sqllist(tables)),
            ('WHERE', where),
            ('GROUP BY', group),
            ('ORDER BY', order),
            ('LIMIT', limit),
            ('OFFSET', offset))
    
    def gen_clause(self, sql, val, vars): 
        if isinstance(val, (int, long)):
            if sql == 'WHERE':
                nout = 'id = ' + sqlquote(val)
            else:
                nout = SQLQuery(val)
        #@@@
        elif isinstance(val, (list, tuple)) and len(val) == 2:
            nout = SQLQuery(val[0], val[1]) # backwards-compatibility
        elif isinstance(val, SQLQuery):
            nout = val
        else:
            nout = reparam(val, vars)

        def xjoin(a, b):
            if a and b: return a + ' ' + b
            else: return a or b

        return xjoin(sql, nout)

    def insert(self, tablename, seqname=None, _test=False, **values): 
        """
        Inserts `values` into `tablename`. Returns current sequence ID.
        Set `seqname` to the ID if it's not the default, or to `False`
        if there isn't one.
        
            >>> db = DB()
            >>> q = db.insert('foo', name='bob', age=2, created=SQLLiteral('NOW()'), _test=True)
            >>> q
            <sql: "INSERT INTO foo (age, name, created) VALUES (2, 'bob', NOW())">
            >>> q.query()
            'INSERT INTO foo (age, name, created) VALUES (%s, %s, NOW())'
            >>> q.values()
            [2, 'bob']
        """
        def q(x): return "(" + x + ")"
        
        if values:
            _keys = SQLQuery.join(values.keys(), ', ')
            _values = SQLQuery.join([sqlparam(v) for v in values.values()], ', ')
            sql_query = "INSERT INTO %s " % tablename + q(_keys) + ' VALUES ' + q(_values)
        else:
            sql_query = SQLQuery("INSERT INTO %s DEFAULT VALUES" % tablename)

        if _test: return sql_query
        
        db_cursor = self._db_cursor()
        if seqname is not False: 
            sql_query = self._process_insert_query(sql_query, tablename, seqname)

        if isinstance(sql_query, tuple):
            # for some databases, a separate query has to be made to find 
            # the id of the inserted row.
            q1, q2 = sql_query
            self._db_execute(db_cursor, q1)
            self._db_execute(db_cursor, q2)
        else:
            self._db_execute(db_cursor, sql_query)

        try: 
            out = db_cursor.fetchone()[0]
        except Exception: 
            out = None
        
        if not self.ctx.transactions: self.ctx.db.commit()
        return out
    
    def update(self, tables, where, vars=None, _test=False, **values): 
        """
        Update `tables` with clause `where` (interpolated using `vars`)
        and setting `values`.

            >>> db = DB()
            >>> name = 'Joseph'
            >>> q = db.update('foo', where='name = $name', name='bob', age=2,
            ...     created=SQLLiteral('NOW()'), vars=locals(), _test=True)
            >>> q
            <sql: "UPDATE foo SET age = 2, name = 'bob', created = NOW() WHERE name = 'Joseph'">
            >>> q.query()
            'UPDATE foo SET age = %s, name = %s, created = NOW() WHERE name = %s'
            >>> q.values()
            [2, 'bob', 'Joseph']
        """
        if vars is None: vars = {}
        where = self._where(where, vars)

        query = (
          "UPDATE " + sqllist(tables) + 
          " SET " + sqlwhere(values, ', ') + 
          " WHERE " + where)

        if _test: return query
        
        db_cursor = self._db_cursor()
        self._db_execute(db_cursor, query)
        if not self.ctx.transactions: self.ctx.db.commit()
        return db_cursor.rowcount
    
    def delete(self, table, where=None, using=None, vars=None, _test=False): 
        """
        Deletes from `table` with clauses `where` and `using`.

            >>> db = DB()
            >>> name = 'Joe'
            >>> db.delete('foo', where='name = $name', vars=locals(), _test=True)
            <sql: "DELETE FROM foo WHERE name = 'Joe'">
        """
        if vars is None: vars = {}
        where = self._where(where, vars)

        q = 'DELETE FROM ' + table
        if where: q += ' WHERE ' + where
        if using: q += ' USING ' + sqllist(using)

        if _test: return q

        db_cursor = self._db_cursor()
        self._db_execute(db_cursor, q)
        if not self.ctx.transactions: self.ctx.db.commit()
        return db_cursor.rowcount

    def _process_insert_query(self, query, tablename, seqname):
        return query

    def transaction(self): 
        """Start a transaction."""
        return Transaction(self.ctx)
    
class PostgresDB(DB): 
    """Postgres driver."""
    def __init__(self, **keywords):
        DB.__init__(self)
        if 'pw' in keywords:
            keywords['password'] = keywords['pw']
            del keywords['pw']
        keywords['database'] = keywords['db']
        del keywords['db']

        self.dbname = "postgres"
        self.db_module = self.get_db_module()
        self.paramstyle = self.db_module.paramstyle
        self.keywords = keywords

    def get_db_module(self):
        try: 
            import psycopg2 as db
            import psycopg2.extensions
            psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
        except ImportError: 
            try: 
                import psycopg as db
            except ImportError: 
                import pgdb as db
        return db

    def _process_insert_query(self, query, tablename, seqname):
        if seqname is None: 
            seqname = tablename + "_id_seq"
        return query + "; SELECT currval('%s')" % seqname

    def _load_context(self):
        DB._load_context(self)
        self.ctx.db.set_client_encoding('UTF8')

class MySQLDB(DB): 
    def __init__(self, **keywords):
        DB.__init__(self)
        import MySQLdb as db
        if 'pw' in keywords:
            keywords['passwd'] = keywords['pw']
            del keywords['pw']
        self.paramstyle = db.paramstyle = 'pyformat' # it's both, like psycopg
        self.db_module = db
        self.keywords = keywords
        self.dbname = "mysql"

    def _process_insert_query(self, query, tablename, seqname):
        return query, SQLQuery('SELECT last_insert_id();')


class SqliteDB(DB): 
    def __init__(self, **keywords):
        DB.__init__(self)
        try:
            import sqlite3 as db
            db.paramstyle = 'qmark'
        except ImportError:
            try:
                from pysqlite2 import dbapi2 as db
                db.paramstyle = 'qmark'
            except ImportError:
                import sqlite as db
        #web.config._hasPooling = False
        self.paramstyle = db.paramstyle
        keywords['database'] = keywords['db']
        del keywords['db']
        self.keywords = keywords
        self.db_module = db
        self.dbname = "sqlite"

    def _process_insert_query(self, query, tablename, seqname):
        return query, SQLQuery('SELECT last_insert_rowid();')
    
    def query(self, *a, **kw):
        out = DB.query(self, *a, **kw)
        if isinstance(out, iterbetter):
            # rowcount is not provided by sqlite
            del out.__len__
        return out

class FirebirdDB(DB):
    """Firebird Database.
    """
    def __init__(self, **keywords):
        DB.__init__(self)
        try:
            import kinterbasdb as db
        except Exception:
            db = None
            pass
        if 'pw' in keywords:
            keywords['passwd'] = keywords['pw']
            del keywords['pw']
        keywords['database'] = keywords['db']
        del keywords['db']
        self.keywords = keywords
        self.db_module = db

    def delete(self, table, where=None, using=None, vars=None, _test=False):
        # firebird doesn't support using clause
        using=None
        return DB.delete(self, table, where, using, vars, _test)

    def sql_clauses(self, what, tables, where, group, order, limit, offset):
        return (
            ('SELECT', ''),
            ('FIRST', limit),
            ('SKIP', offset),
            ('', what),
            ('FROM', sqllist(tables)),
            ('WHERE', where),
            ('GROUP BY', group),
            ('ORDER BY', order)
        )

_databases = {}
def database(dburl=None, **params):
    """Creates appropriate database using params.
    """
    dbn = params.pop('dbn')
    if dbn in _databases:
        return _databases[dbn](**params)
    else:
        raise UnknownDB, dbn

def register_database(name, clazz):
    """Register a database.

        >>> class LegacyDB(DB): 
        ...     def __init__(self, **params): 
        ...        pass 
        ...
        >>> register_database('legacy', LegacyDB)
        >>> db = database(dbn='legacy', db='test', user='joe', passwd='secret') 
    """
    _databases[name] = clazz

register_database('mysql', MySQLDB)
register_database('postgres', PostgresDB)
register_database('sqlite', SqliteDB)
register_database('firebird', FirebirdDB)

def _interpolate(format): 
    """
    Takes a format string and returns a list of 2-tuples of the form
    (boolean, string) where boolean says whether string should be evaled
    or not.

    from <http://lfw.org/python/Itpl.py> (public domain, Ka-Ping Yee)
    """
    from tokenize import tokenprog

    def matchorfail(text, pos):
        match = tokenprog.match(text, pos)
        if match is None:
            raise _ItplError(text, pos)
        return match, match.end()

    namechars = "abcdefghijklmnopqrstuvwxyz" \
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_";
    chunks = []
    pos = 0

    while 1:
        dollar = format.find("$", pos)
        if dollar < 0: 
            break
        nextchar = format[dollar + 1]

        if nextchar == "{":
            chunks.append((0, format[pos:dollar]))
            pos, level = dollar + 2, 1
            while level:
                match, pos = matchorfail(format, pos)
                tstart, tend = match.regs[3]
                token = format[tstart:tend]
                if token == "{": 
                    level = level + 1
                elif token == "}":  
                    level = level - 1
            chunks.append((1, format[dollar + 2:pos - 1]))

        elif nextchar in namechars:
            chunks.append((0, format[pos:dollar]))
            match, pos = matchorfail(format, dollar + 1)
            while pos < len(format):
                if format[pos] == "." and \
                    pos + 1 < len(format) and format[pos + 1] in namechars:
                    match, pos = matchorfail(format, pos + 1)
                elif format[pos] in "([":
                    pos, level = pos + 1, 1
                    while level:
                        match, pos = matchorfail(format, pos)
                        tstart, tend = match.regs[3]
                        token = format[tstart:tend]
                        if token[0] in "([": 
                            level = level + 1
                        elif token[0] in ")]":  
                            level = level - 1
                else: 
                    break
            chunks.append((1, format[dollar + 1:pos]))

        else:
            chunks.append((0, format[pos:dollar + 1]))
            pos = dollar + 1 + (nextchar == "$")

    if pos < len(format): 
        chunks.append((0, format[pos:]))
    return chunks

if __name__ == "__main__":
    import doctest
    doctest.testmod()
