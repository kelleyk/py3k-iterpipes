# -*- coding: utf-8 -*-

# Copyright (c) 2009-2010 Andrey Vlasovskikh
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

r'''A library for running shell pipelines using shell-like syntax.


Rationale
---------

Python is a good choice for many software tools, but it lacks clarity and
simplicity of command shells when it comes to running command pipelines from
scripts. The standard [subprocess][] module provides basic inter-processing
tools, but it requires lots of lines to express a single shell line.

`iterpipes` is trying to overcome this limitation by representing a shell
command pipeline as *a function over iterables*, similar to functions from the
standard [itertools][] module.


Description
-----------

`iterpipes` is a thin wrapper around the standard [subprocess][] module. It
represents a shell command pipeline as a function over iterables that maps its
`stdin` to `stdout`. As `iterpipes` deals with iterables, it plays nicely with
[itertools][] from the standard library, as well as with list comprehensions and
generator expressions.

To invoke a shell command pipeline, you should:

1. Create it using a command constructor
2. Execute it directly or via a helper function


### Command Constructors

Commands are created using command constructors. Command constructors take a
string `command` to run as their first argument. Special values `'{}'` in the
`command` are replaced with constructors' positional arguments using *safe shell
escaping*.

Keyword arguments of constructors are almost identical to the keyword arguments
of `subprocess.Popen` from [subprocess][]. This allows redirecting `stdout` to a
file, merging `stdout` and `stderr`, etc.

Here are several examples for using command constructors:

    cmd('rm -fr {}', dirname)

    linecmd('find {} -name {} -print0 | xargs -0 wc -l'
            dirname,
            '\*.py')

    cmd(r'ls -d .* | tr \n \0 | xargs -0 rm -f')

Command constructors summary:

* `bincmd`:
    a binary command, that works with `str` iterables
* `cmd`:
    a string command, that works with `unicode` iterables and performs necessary
    encoding conversions
* `linecmd`:
    a line-oriented command, that returns buffered `unicode` lines delimited by
    the newline character `'\n'`


### Execution Helpers

As a command is an ordinary function over iterables, you can run it by passing
an `stdin` iterable as its `input` and iterating over its `stdout` result:

    for line in linecmd('gunzip | head')(zipped_data):
        print line.rstrip('\\n')

If a command returns a non-zero code, then the `CalledProcessError` exception is
raised.

It is often the case that a command doesn't require any `stdin` data or doesn't
write anything useful to `stdout`. There are several helper functions for such
cases.

If a command doesn't need any `stdin` data, you may run it using `None` or `[]`
as its `input` or use the `run` helper function to get a little bit more
readable syntax:

    for line in run(linecmd('ls -a')):
        print line.rstrip('\\n')

If a command delivers no useful data to `stdout`, then you may use `call` or
`check_call` helpers. If you need a return code of the command, use the `call`
helper:

    retcode = call(cmd('rm -f {}', filename))

otherwise use the `check_call` helper that raises `CalledProcessError` on errors:

    check_call(cmd('rm -f {}', filename))

Execution helpers summary:

* `run`:
    run a command with `None` as the default `input` value
* `call`:
    run a command and return its return code
* `check_call`:
    run a command and raise an exception if it returned a non-zero code

All the execution helpers accept `input` as their second argument. The default
value for `input` is `None`.


### Other Functions

* `format`:
    format a shell command using safe escapes and argument substitutions
* `compose`:
    function composition from the functional programming world


Examples
--------

It is useful to abstract the execution of a command using a Python function. For
example, you may find yourself writing several lines of code for creating
tarball archives of directories. You can hide details of creating tarballs by
defining the following function:

    def make_zipped_tarball(dirname, output_path='.'):
        name = os.path.basename(os.path.normpath(dirname))
        tar = cmd('tar -czf {} {}',
                  os.path.join(output_path, '%s.tar.gz' % name),
                  dirname)
        check_call(tar)


  [subprocess]: http://docs.python.org/library/subprocess.html
  [itertools]: http://docs.python.org/library/itertools.html

'''
from __future__ import with_statement

from contextlib import contextmanager
import re, errno, locale
from subprocess import Popen, PIPE, CalledProcessError
from threading import Thread
from codecs import iterdecode
from functools import reduce

import six


__all__ = [
    'cmd', 'bincmd', 'linecmd', 'run', 'call', 'check_call', 'format',
    'compose',
]

DEFAULT_READ_BUFSIZE = 4096

def bincmd(command, *args, **kwargs):
    '''Create a binary command.

    Arguments:

    * `command`:
        a shell pipeline string. Special `'{}'` values in `command` are replaced
        with positional arguments using safe shell escaping

    The keyword arguments are identical to the keyword arguments of
    `subprocess.Popen`.

    Return value:

    A binary command that works with `str` iterables. It is a function from
    `stdin` iterable to `stdout` iterable. It also may accept a single `str`
    value or `None`.

    '''
    kwargs = kwargs.copy()
    kwargs.setdefault('stdout', PIPE)
    command = format(command, args)
    return lambda input: _run_pipeline(command, input, **kwargs)

def cmd(command, *args, **kwargs):
    '''Create a string command.

    It is an extension of `bincmd` that performs necessary encoding conversions
    for `unicode` values.

    Arguments:

    * `command`:
        a shell pipeline string. Special `'{}'` values in `command` are replaced
        with positional arguments using safe shell escaping

    Keyword arguments:

    * `encoding`:
        a string encoding for `unicode` values. If not specified, the
        locale-specific encoding will be used

    The other keyword arguments are identical to the keyword arguments of
    `subprocess.Popen`.

    Return value:

    A string command that works with `unicode` iterables and performs necessary
    encoding conversions. It is a function from `stdin` iterable to `stdout`
    iterable. It also may accept a single `unicode` value or `None`.

    '''
    def decode(xs):
        return iterdecode(xs, encoding)

    def encode(xs):
        if isinstance(input, six.text_type):
            return [xs.encode(encoding)]
        elif xs is None:
            return xs
        else:
            return (x.encode(encoding) for x in xs)

    kwargs = kwargs.copy()
    encoding = kwargs.setdefault('encoding', locale.getpreferredencoding())
    kwargs.pop('encoding')
    return compose(decode, bincmd(command, *args, **kwargs), encode)

def linecmd(command, *args, **kwargs):
    r'''Create a line-oriented command.

    It is an extension of `cmd` that returns buffered `unicode` lines.

    Arguments:

    * `command`:
        a shell pipeline string. Special `'{}'` values in `command` are replaced
        with positional arguments using safe shell escaping

    Keyword arguments:

    * `encoding`:
        a string encoding for `unicode` values. If not specified, the
        locale-specific encoding will be used

    The other keyword arguments are identical to the keyword arguments of
    `subprocess.Popen`.

    Return value:

    A line-oriented command that returns buffered `unicode` lines delimited by
    the newline character `'\n'`. It works with `unicode` iterables and performs
    necessary encoding conversions. It is a function from `stdin` iterable to
    `stdout` iterable. It also may accept a single `unicode` value or `None`.

    '''
    kwargs = kwargs.copy()
    kwargs['bufsize'] = 1
    return cmd(command, *args, **kwargs)

def run(cmd, input=None):
    '''Run a command with `None` as the default `input` value.

    If the process running `cmd` returns a non-zero code, then a
    `CalledProcessError` is raised.

    Arguments:

    * `cmd`:
        a command to run. It is a function over iterables.
    * `input`:
        the `stdin` data. It may be an iterable, a single value or `None`.

    The return value is the `cmd`'s resulting `stdout` iterable.

    '''
    return cmd(input)

def call(cmd, input=None):
    '''Run a command and return its return code.

    Arguments:

    * `cmd`:
        a command to run. It is a function over iterables.
    * `input`:
        the `stdin` data. It may be an iterable, a single value or `None`.

    The return value is the return code of the process running `cmd`.

    '''
    return _retcode(run(cmd, input))

def check_call(cmd, input=None):
    '''Run a command and raise an exception if it returned a non-zero code.

    If the process running `cmd` returns a non-zero code, then a
    `CalledProcessError` is raised.

    Arguments:

    * `cmd`:
        a command to run. It is a function over iterables.
    * `input`:
        the `stdin` data. It may be an iterable, a single value or `None`.

    There is no return value.

    '''
    _consume(run(cmd, input))

def format(command, args):
    r'''Format a shell command using safe escapes and argument substitutions.

    Examples:

        >>> format('ls -l {} | grep {} | wc', ['foo 1', 'bar$baz'])
        'ls -l foo\\ 1 | grep bar\\$baz | wc'

    '''
    if command.count('{}') != len(args):
        raise TypeError('arguments do not match the format string %r: %r',
                        (command, args))
    fmt = command.replace('%', '%%').replace('{}', '%s')
    return fmt % tuple(map(_shell_escape, args))

def compose(*fs):
    '''Function composition from the functional programming world.'''
    f = lambda x: reduce(lambda x, f: f(x), reversed(fs), x)
    f.__name__ = ', '.join(f.__name__ for f in fs)
    return f

def _consume(xs):
    'Iterable(a) -> None'
    for x in xs:
        pass

def _retcode(xs):
    'Iterable(a) -> int'
    try:
        _consume(xs)
    except CalledProcessError as e:
        return e.returncode
    else:
        return 0

def _shell_escape(str):
    'unicode -> unicode'
    return re.sub(r'''([ \t'"\$])''', r'\\\1', str)

def _run_pipeline(command, input, **opts):
    if not (_is_iterable(input) or input is None):
        raise TypeError('input must be iterable or None, got %r' %
                        type(input).__name__)

    if isinstance(input, six.text_type):
        input = [input]

    opts = opts.copy()
    opts.update(dict(shell=True, stdin=input))
    bs_opt = opts.get('bufsize', 0)
    bufsize = DEFAULT_READ_BUFSIZE if bs_opt <= 0 else bs_opt

    with _popen(command, **opts) as p:
        if p.stdout is None:
            return
        xs = (iter(lambda: p.stdout.read(bufsize), six.b(''))
              if bufsize != 1
              else p.stdout)
        for x in xs:
            yield x

def _is_iterable(x):
    'object -> bool'
    return hasattr(x, '__iter__')

@contextmanager
def _popen(*args, **kwargs):
    '... -> ContextManager(Popen)'
    def write(fd, xs):
        try:
            for x in xs:
                fd.write(x)
        except IOError as e:
            if e.errno != errno.EPIPE:
                write_excpts.append(e)
        except Exception as e:
            write_excpts.append(e)
        finally:
            fd.close()

    write_excpts = []
    stdin = kwargs.get('stdin')
    if _is_iterable(stdin):
        kwargs = kwargs.copy()
        kwargs['stdin'] = PIPE

    p = Popen(*args, **kwargs)
    try:
        if _is_iterable(stdin):
            writer = Thread(target=write, args=(p.stdin, iter(stdin)))
            writer.start()
            try:
                yield p
            finally:
                writer.join()
                if len(write_excpts) > 0:
                    raise write_excpts.pop()
        else:
            yield p
    except Exception as e:
        if hasattr(p, 'terminate'):
            p.terminate()
        raise
    else:
        ret = p.wait()
        if ret != 0:
            raise CalledProcessError(ret, *args)

