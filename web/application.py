"""
Web application
(from web.py)
"""
import webapi as web
import webapi, wsgi, utils
import debugerror
from utils import lstrips
import sys

import urllib
import traceback
import itertools
import os
import types

try:
    import wsgiref.handlers
except ImportError:
    pass # don't break people with old Pythons

__all__ = [
    "application", "auto_application",
    "subdir_application", "subdomain_application", 
    "combine_applications",
    "loadhook", "unloadhook"
]

class NotFound(Exception): 
    """Exception raised when an application can't handle a request."""
    pass

class application:
    """Application to delegate requests based on path.

        >>> urls = ("/hello", "hello")
        >>> app = application(urls, globals())
        >>> class hello:
        ...     def GET(self): return "hello"
        >>>
        >>> app.request("/hello").data
        'hello'
    """
    def __init__(self, mapping=(), fvars={}, autoreload=None):
        if autoreload is None:
            autoreload = web.config.get('debug', False)
        self.mapping = mapping
        self.fvars = fvars
        self.processors = []

        if autoreload:
            def modname(fvars):
                """find name of the module name from fvars."""
                file, name = fvars['__file__'], fvars['__name__']
                if name == '__main__':
                    # Since the __main__ module can't be reloaded, the module has 
                    # to be imported using its file name.                    
                    name = os.path.splitext(os.path.basename(file))[0]
                return name
                
            mapping_name = utils.dictfind(fvars, mapping)
            module_name = modname(fvars)
            
            def reload_mapping():
                """loadhook to reload mapping and fvars."""
                mod = __import__(module_name)
                self.fvars = mod.__dict__
                self.mapping = getattr(mod, mapping_name)
            
            # to reload modified modules
            self.add_processor(loadhook(Reloader()))

            # to update mapping and fvars
            self.add_processor(loadhook(reload_mapping))
            
    def add_mapping(self, pattern, classname):
        self.mapping += (pattern, classname)
        
    def add_processor(self, processor):
        """Adds a processor to the application. 
        
            >>> urls = ("/(.*)", "echo")
            >>> app = application(urls, globals())
            >>> class echo:
            ...     def GET(self, name): return name
            ...
            >>>
            >>> def hello(handler): return "hello, " +  handler()
            >>> app.add_processor(hello)
            >>> app.request("/web.py").data
            'hello, web.py'
        """
        self.processors.append(processor)

    def request(self, path='/', method='GET', data=None, host="0.0.0.0:8080", headers=None,https=False):
        """Makes request to this application for the specified path and method.
        Response will be a storage object with data, status and headers.
        
            >>> urls = ("/hello", "hello")
            >>> app = application(urls, globals())
            >>> class hello:
            ...     def GET(self): 
            ...         web.header('Content-Type', 'text/plain')
            ...         return "hello"
            ...
            >>> response = app.request("/hello")
            >>> response.data
            'hello'
            >>> response.status
            '200 OK'
            >>> response.headers['Content-Type']
            'text/plain'
            
        To use https, use https=True.
        
            >>> urls = ("/redirect", "redirect")
            >>> app = application(urls, globals())
            >>> class redirect:
            ...     def GET(self): raise web.seeother("/foo")
            ...
            >>> response = app.request("/redirect")
            >>> response.headers['Location']
            'http://0.0.0.0:8080/foo'
            >>> response = app.request("/redirect", https=True)
            >>> response.headers['Location']
            'https://0.0.0.0:8080/foo'
        """
        query = urllib.splitquery(path)[1] or ""
        env = dict(HTTP_HOST=host, REQUEST_METHOD=method, PATH_INFO=path, QUERY_STRING=query, HTTPS=https)
        headers = headers or {}
        for k, v in headers.items():
            env[k.upper()] = v
            
        if data:
            import StringIO
            q = urllib.urlencode(data)
            env['wsgi.input'] = StringIO.StringIO(q)
        response = web.storage()
        def start_response(status, headers):
            response.status = status
            response.headers = dict(headers)
        response.data = "".join(self.wsgifunc()(env, start_response))
        return response

    def handle(self):
        fn, args = self._match(self.mapping, web.ctx.path)
        return self._delegate(fn, self.fvars, args)
        
    def handle_with_processors(self):
        def process(processors):
            if processors:
                p, processors = processors[0], processors[1:]
                return p(lambda: process(processors))
            else:
                return self.handle()
                
        # processors must be applied in the resvere order.
        return process(self.processors)
                
    def wsgifunc(self, *middleware):
        """Returns a WSGI-compatible function for this application."""
        def peep(iterator):
            """Peeps into an iterator by doing an iteration
            and returns an equivalent iterator.
            """
            # wsgi requires the headers first
            # so we need to do an iteration
            # and save the result for later
            try:
                firstchunk = iterator.next()
            except StopIteration:
                firstchunk = ''
            
            return itertools.chain([firstchunk], iterator)    
                                
        def is_generator(x): return x and hasattr(x, 'next')
        
        def wsgi(env, start_resp):
            self.load(env)

            try:
                # allow uppercase methods only
                if web.ctx.method.upper() != web.ctx.method:
                    raise web.nomethod()

                result = self.handle_with_processors()
            except NotFound:
                web.ctx.status = "404 Not Found"
                result = self.notfound()
            except web.HTTPError, e:
                result = e.data
            except:
                print >> web.debug, traceback.format_exc()
                web.ctx.status = '500 Internal Server Error'
                web.header('Content-Type', 'text/html')
                result = self.internalerror()

            if is_generator(result):
                result = peep(result)
            else:
                result = [utils.utf8(result)]

            status, headers = web.ctx.status, web.ctx.headers
            start_resp(status, headers)

            #@@@
            # Since the CherryPy Webserver uses thread pool, the thread-local state is never cleared.
            # This interferes with the other requests. 
            # clearing the thread-local storage to avoid that.
            # see utils.ThreadedDict for details
            import threading
            t = threading.currentThread()
            if hasattr(t, '_d'):
                del t._d
        
            return result

        for m in middleware: 
            wsgi = m(wsgi)

        return wsgi

    def internalerror(self):
        """Message for `500 internal error`."""
        
        if web.config.get('debug'):
            return debugerror.debugerror()
        else:
            return "internal server error"

    def notfound(self):
        """Message for `404 not found`."""
        return "not found"
        
    def run(self, *middleware):
        """
        Starts handling requests. If called in a CGI or FastCGI context, it will follow
        that protocol. If called from the command line, it will start an HTTP
        server on the port named in the first command line argument, or, if there
        is no argument, on port 8080.
        
        `middleware` is a list of WSGI middleware which is applied to the resulting WSGI
        function.
        """
        return wsgi.runwsgi(self.wsgifunc(*middleware))
    
    def cgirun(self, *middleware):
        """
        Return a CGI handler. This is mostly useful with Google App Engine.
        There you can just do:
        
            main = app.cgirun()
        """
        wsgiapp = self.wsgifunc(*middleware)

        try:
            import google.appengine.ext.utils
            return google.appengine.ext.utils.run_wsgi_app(wsgiapp, debug=True)
        except ImportError:
            # we're not running from within Google App Engine
            return wsgiref.handlers.CGIHandler().run(wsgiapp)
    
    def load(self, env):
        """Initializes ctx using env."""
        ctx = web.ctx
        
        ctx.status = '200 OK'
        ctx.headers = []
        ctx.output = ''
        ctx.environ = ctx.env = env
        ctx.host = env.get('HTTP_HOST')
        ctx.protocol = env.get('HTTPS') and 'https' or 'http'
        ctx.homedomain = ctx.protocol + '://' + env.get('HTTP_HOST', '[unknown]')
        ctx.homepath = os.environ.get('REAL_SCRIPT_NAME', env.get('SCRIPT_NAME', ''))
        ctx.home = ctx.homedomain + ctx.homepath
        ctx.ip = env.get('REMOTE_ADDR')
        ctx.method = env.get('REQUEST_METHOD')
        ctx.path = env.get('PATH_INFO')
        # http://trac.lighttpd.net/trac/ticket/406 requires:
        if env.get('SERVER_SOFTWARE', '').startswith('lighttpd/'):
            ctx.path = lstrips(env.get('REQUEST_URI').split('?')[0], ctx.homepath)

        if env.get('QUERY_STRING'):
            ctx.query = '?' + env.get('QUERY_STRING', '')
        else:
            ctx.query = ''

        ctx.fullpath = ctx.path + ctx.query

    def _delegate(self, f, fvars, args=[]):
        def handle_class(cls):
            meth = web.ctx.method
            if meth == 'HEAD' and not hasattr(cls, meth):
                meth = 'GET'
            if not hasattr(cls, meth):
                raise web.nomethod(cls)
            tocall = getattr(cls(), meth)
            return tocall(*args)
            
        def is_class(o): return isinstance(o, (types.ClassType, type))
            
        if f is None:
            raise NotFound
        elif isinstance(f, application):
            return f.handle()
        elif is_class(f):
            return handle_class(f)
        elif isinstance(f, str):
            if '.' in f:
                x = f.split('.')
                mod, cls = '.'.join(x[:-1]), x[-1]
                mod = __import__(mod, globals(), locals(), [""])
                cls = getattr(mod, cls)
            else:
                cls = fvars[f]
            return handle_class(cls)
        elif hasattr(f, '__call__'):
            return f()
        else:
            return web.notfound()

    def _match(self, mapping, value):
        for pat, what in utils.group(mapping, 2):
            rx = utils.re_compile('^' + pat + '$')
            result = rx.match(value)
            if result:
                return what, [x and urllib.unquote(x) for x in result.groups()]
        return None, None

class auto_application(application):
    """Application similar to `application` but urls are constructed 
    automatiacally using metaclass.

        >>> app = auto_application()
        >>> class hello(app.page):
        ...     def GET(self): return "hello, world"
        ...
        >>> class foo(app.page):
        ...     path = '/foo/.*'
        ...     def GET(self): return "foo"
        >>> app.request("/hello").data
        'hello, world'
        >>> app.request('/foo/bar').data
        'foo'
    """
    def __init__(self):
        application.__init__(self)

        class metapage(type):
            def __init__(klass, name, bases, attrs):
                type.__init__(klass, name, bases, attrs)
                path = attrs.get('path', '/' + name)

                # path can be specified as None to ignore that class
                # typically required to create a abstract base class.
                if path is not None:
                    self.add_mapping(path, klass)

        class page:
            path = None
            __metaclass__ = metapage

        self.page = page

class subdir_application(application):
    """Application to delegate requests based on directory.

        >>> urls = ("/hello", "hello")
        >>> app = application(urls, globals())
        >>> class hello:
        ...     def GET(self): return "hello"
        >>>
        >>> mapping = ("/foo", app)
        >>> app2 = subdir_application(mapping)
        >>> app2.request("/foo/hello").data
        'hello'
    """
    def handle(self):
        for dir, what in utils.group(self.mapping, 2):
            if web.ctx.path.startswith(dir + '/'):
                # change paths to make path relative to dir
                web.ctx.home += dir
                web.ctx.homepath += dir
                web.ctx.path = web.ctx.path[len(dir):]
                web.ctx.fullpath = web.ctx.fullpath[len(dir):]
                return self._delegate(what, self.fvars)

        raise NotFound
                
class subdomain_application(application):
    """Application to delegate requests based on the host.

        >>> urls = ("/hello", "hello")
        >>> app = application(urls, globals())
        >>> class hello:
        ...     def GET(self): return "hello"
        >>>
        >>> mapping = ("hello.example.com", app)
        >>> app2 = subdomain_application(mapping)
        >>> app2.request("/hello", host="hello.example.com").data
        'hello'
        >>> response = app2.request("/hello", host="something.example.com")
        >>> response.status
        '404 Not Found'
        >>> response.data
        'not found'
    """
    def handle(self):
        host = web.ctx.host.split(':')[0] #strip port
        fn, args = self._match(self.mapping, host)
        return self._delegate(fn, self.fvars, args)

class combine_applications(application):
    """Combines a list of applications into single application.
    
        >>> app1 = auto_application()
        >>> class foo(app1.page):
        ...     def GET(self): return "foo"
        ...
        >>> app2 = auto_application()
        >>> class bar(app2.page):
        ...     def GET(self): return "bar"
        ...
        >>> app = combine_applications(app1, app2)
        >>> app.request('/foo').data
        'foo'
        >>> app.request('/bar').data
        'bar'
        >>> response = app.request("/hello")
        >>> response.status
        '404 Not Found'
        >>> response.data
        'not found'
    """
    def __init__(self, *apps):
        self.apps = apps
        application.__init__(self)
        
    def handle(self):
        for a in self.apps:
            try:
                return a.handle()
            except NotFound:
                pass
        raise NotFound
        
def loadhook(h):
    """Converts a load hook into an application processor.
    
        >>> app = auto_application()
        >>> def f(): "something done before handling request"
        ...
        >>> app.add_processor(loadhook(f))
    """
    def processor(handler):
        h()
        return handler()
        
    return processor
    
def unloadhook(h):
    """Converts an unload hook into an application processor.
    
        >>> app = auto_application()
        >>> def f(): "something done after handling request"
        ...
        >>> app.add_processor(unloadhook(f))    
    """
    def processor(handler):
        try:
            return handler()
        finally:
            h()
            
    return processor
    
class Reloader:
    """Checks to see if any loaded modules have changed on disk and, 
    if so, reloads them.
    """
    def __init__(self):
        self.mtimes = {}

    def __call__(self):
        for mod in sys.modules.values():
            self.check(mod)
            
    def check(self, mod):
        try: 
            mtime = os.stat(mod.__file__).st_mtime
        except (AttributeError, OSError, IOError):
            return
        if mod.__file__.endswith('.pyc') and os.path.exists(mod.__file__[:-1]):
            mtime = max(os.stat(mod.__file__[:-1]).st_mtime, mtime)
            
        if mod not in self.mtimes:
            self.mtimes[mod] = mtime
        elif self.mtimes[mod] < mtime:
            try: 
                reload(mod)
                self.mtimes[mod] = mtime
            except ImportError: 
                pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()
