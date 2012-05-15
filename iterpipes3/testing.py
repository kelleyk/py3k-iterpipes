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

'''Various experimental stuff for iterpipes.'''

from iterpipes3 import compose

class Fun(object):
    'Function wrapper that defines the function composition operator `|`.'
    def __init__(self, f):
        self.f = f

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)

    def __or__(self, other):
        return Fun(compose(other, self))

    def __repr__(self):
        return repr(self.f)

    def __getattr__(self, name):
        return getattr(self.f, name)

def join(xs):
    'Iterable(bytes or str) -> bytes or str'
    return ''.join(xs)

def each(f):
    '(a -> b) -> (Iterable(a) -> Iterable(b)'
    return lambda xs: map(f, xs)

def strip(chars=None):
    return each(lambda s: s.strip(chars))

