# -*- coding: utf-8 -*-


import sys
from itertools import islice
from nose.tools import eq_, ok_, assert_raises

from iterpipes3 import (bincmd, cmd, linecmd, run, call, check_call, format,
                       compose, CalledProcessError)
from iterpipes3.testing import Fun, each, join, strip
from subprocess import STDOUT

import six

STDOUT_FILENO = 1

def test_basic_single():
    eq_(''.join(run(cmd('ls -d /'))), '/\n')

def test_basic_many():
    eq_(''.join(run(cmd('echo foo | wc -l'))), '1\n')

def test_huge_input():
    wc = compose(join, cmd('wc -l'))
    eq_(wc('%d\n' % x for x in range(10000)), '10000\n')

def test_make_pipeline():
    lines = ''.join(run(cmd(r'echo a b c b a | tr {} \\n | sort | uniq',
                            ' ')))
    eq_(lines, 'a\nb\nc\n')

def _test_really_huge_input():
    cat = bincmd('cat')
    sum = 0
    BUFSIZE = 10000
    TIMES = 10000
    with open('/dev/zero', 'rb') as fd:
        for x in cat(islice(iter(lambda: fd.read(BUFSIZE), ''), TIMES)):
            sum += len(x)
    eq_(sum, BUFSIZE * TIMES)

def test_dont_touch_stdout():
    eq_(''.join(run(cmd('ls -d /', stdout=STDOUT_FILENO))), '')

def test_nonexistent_command():
    with open('/dev/null', 'wb') as null:
        ok_(call(bincmd('echo foo | bar --baz', stderr=null)) != 0)

def test_stdin_iterable_excpt():
    class E(Exception): pass
    def g():
        raise E('foo')
        yield 'bar'
    assert_raises(E, lambda: ''.join(run(cmd('grep foo'), g())))

def test_subst_curly_brackets():
    eq_(format('echo {} | wc {}', ['{}', '-l']), 'echo {} | wc -l')
    eq_(format('echo {{}}', ['x']), 'echo {x}')
    eq_(format('echo {{}}', ['{}']), 'echo {{}}')

def test_format_args_count():
    eq_(format('f', []), 'f')
    eq_(format('f {}', ['x']), 'f x')
    assert_raises(TypeError, lambda: format('f {} {}', ['a']))
    assert_raises(TypeError, lambda: format('f {} {}', ['a', 'b', 'c']))

def test_line_buffering():
    eq_(list(cmd('echo "foo\nbar"', bufsize=1)([])), ['foo\n', 'bar\n'])

def test_cmd():
    text = six.u('привет, λ!\nλx. x\nдо свидания\n')
    regexp = six.u('λ[a-zA-Z]\.')
    grep = compose(join, cmd('grep {}', regexp))
    eq_(grep(text), six.u('λx. x\n'))

def test_linecmd():
    text = six.u('абв\nabc\n')
    tr = linecmd('tr a-z A-Z')
    eq_(list(tr(text)), [six.u('абв\n'), six.u('ABC\n')])

def test_run_output():
    eq_(''.join(run(cmd('echo foo'))), 'foo\n')
    eq_(run(compose(join, cmd('echo foo'))), 'foo\n')
    eq_(call(cmd('echo foo')), 0)

def test_or_operator():
    eq_(run(Fun(cmd('echo foo')) | (lambda x: x) | join), 'foo\n')
    eq_(run(Fun(lambda _: ['a']) | cmd('tr a-z A-Z') | join), 'A')

def test_each():
    upper = lambda x: x.upper()
    eq_(run(Fun(linecmd('echo "a\nb\nc"')) |
            each(upper) |
            strip('\n') |
            join),
        'ABC')

def test_calls():
    mkdir = cmd('mkdir foo', stderr=STDOUT)
    rmdir = cmd('rmdir foo', stderr=STDOUT)
    call(rmdir)
    check_call(mkdir)
    assert_raises(CalledProcessError, lambda: check_call(mkdir))
    eq_(call(rmdir), 0)
    ok_(call(rmdir) != 0)

def test_string_input():
    eq_(''.join(run(cmd('tr t T'), 'input')), six.u('inpuT'))
    eq_(''.join(run(cmd('tr t T'), six.u('input'))), six.u('inpuT'))
    eq_(''.join(run(cmd('tr t T'), [six.u('input')])), six.u('inpuT'))

if __name__ == '__main__':
    test_basic_single()

