#  -*- coding: latin-1 -*-
#  vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright (c) 2013, GEM Foundation

#  OpenQuake is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  OpenQuake is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU Affero General Public License
#  along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

"""
Validation library for the engine, the desktop tools, and anything else
"""

import re
import ast
import logging
from openquake.hazardlib import imt


def compose(*validators):
    """
    Implement composition of validators. For instance

    >>> utf8_not_empty = compose(utf8, not_empty)
    >>> utf8_not_empty  # doctest: +ELLIPSIS
    <function compose(utf8,not_empty) at ...>
    """
    def composed_validator(value):
        out = value
        for val in reversed(validators):
            out = val(out)
        return out
    composed_validator.__name__ = 'compose(%s)' % ','.join(
        val.__name__ for val in validators)
    return composed_validator


class NoneOr(object):
    """
    Accept the empty string (casted to None) or something else validated
    by the underlying `cast` validator.
    """
    def __init__(self, cast):
        self.cast = cast
        self.__name__ = cast.__name__

    def __call__(self, value):
        if value:
            return self.cast(value)


class Choice(object):
    """
    Check if the choice is valid.
    """
    def __init__(self, *choices):
        self.choices = choices
        self.__name__ = 'Choice%s' % str(choices)

    def __call__(self, value):
        if not value in self.choices:
            raise ValueError('%r is not a valid choice in %s' % (
                             value, self.choices))
        return value

category = Choice('population', 'buildings')


class Regex(object):
    """
    Compare the value with the given regex
    """
    def __init__(self, regex):
        self.rx = re.compile(regex)
        self.__name__ = 'Regex[%s]' % regex

    def __call__(self, value):
        if self.rx.match(value) is None:
            raise ValueError('%r does not match the regex %r' %
                             (value, self.rx.pattern))
        return value

name = Regex(r'^[a-zA-Z_]\w*$')


class FloatRange(object):
    def __init__(self, minrange, maxrange):
        self.minrange = minrange
        self.maxrange = maxrange
        self.__name__ = 'FloatRange[%s:%s]' % (minrange, maxrange)

    def __call__(self, value):
        f = float(value)
        if f > self.maxrange:
            raise ValueError('%r is bigger than the max, %r' %
                             (f, self.maxrange))
        if f < self.minrange:
            raise ValueError('%r is smaller than the min, %r' %
                             (f, self.minrange))
        return f


def not_empty(value):
    """Check that the string is not empty"""
    if not value:
        raise ValueError('Got an empty string')
    return value


def utf8(value):
    r"""
    Check that the string is UTF-8. Returns a unicode object.

    >>> utf8('�')
    Traceback (most recent call last):
    ...
    ValueError: Not UTF-8: '\xe0'
    """
    try:
        return value.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('Not UTF-8: %r' % value)


def utf8_not_empty(value):
    """Check that the string is UTF-8 and not empty"""
    return utf8(not_empty(value))


def namelist(value):
    """
    :param value: input string
    :returns: list of identifiers

    >>> namelist('a1  b_2\t_c')
    ['a1', 'b_2', '_c']

    >>> namelist('a1 b_2 1c')
    Traceback (most recent call last):
        ...
    ValueError: List of names containing an invalid name: 1c
    """
    names = value.split()
    if not names:
        raise ValueError('Got an empty name list')
    for n in names:
        try:
            name(n)
        except ValueError:
            raise ValueError('List of names containing an invalid name:'
                             ' %s' % n)
    return names


def longitude(value):
    """
    :param value: input string
    :returns: longitude float
    """
    lon = float(value)
    if lon > 180.:
        raise ValueError('longitude %s > 180' % lon)
    elif lon < -180.:
        raise ValueError('longitude %s < -180' % lon)
    return lon


def latitude(value):
    """
    :param value: input string
    :returns: latitude float
    """
    lat = float(value)
    if lat > 90.:
        raise ValueError('latitude %s > 90' % lat)
    elif lat < -90.:
        raise ValueError('latitude %s < -90' % lat)
    return lat


def lonlat(value):
    """
    :param value: a pair of coordinates
    :returns: a tuple (longitude, latitude)

    >>> lonlat('12 14')
    (12.0, 14.0)
    """
    lon, lat = value.split()
    return longitude(lon), latitude(lat)


def coordinates(value):
    """
    Convert a non-empty string into a list of lon-lat coordinates
    >>> coordinates('')
    Traceback (most recent call last):
    ...
    ValueError: Empty list of coordinates: ''
    >>> coordinates('1.1 1.2')
    [(1.1, 1.2)]
    >>> coordinates('1.1 1.2, 2.2 2.3')
    [(1.1, 1.2), (2.2, 2.3)]
    """
    if not value.strip():
        raise ValueError('Empty list of coordinates: %r' % value)
    return map(lonlat, value.split(','))


def positiveint(value):
    """
    :param value: input string
    :returns: positive integer
    """
    i = int(not_empty(value))
    if i < 0:
        raise ValueError('integer %d < 0' % i)
    return i


def positivefloat(value):
    """
    :param value: input string
    :returns: positive float
    """
    f = float(not_empty(value))
    if f < 0:
        raise ValueError('float %d < 0' % f)
    return f


_BOOL_DICT = {
    '': False,
    '0': False,
    '1': True,
    'false': False,
    'true': True,
}


def boolean(value):
    """
    :param value: input string such as '0', '1', 'true', 'false'
    :returns: boolean

    >>> boolean('')
    False
    >>> boolean('True')
    True
    >>> boolean('false')
    False
    >>> boolean('t')
    Traceback (most recent call last):
        ...
    ValueError: Not a boolean: t
    """
    value = value.strip().lower()
    try:
        return _BOOL_DICT[value]
    except KeyError:
        raise ValueError('Not a boolean: %s' % value)


probability = FloatRange(0, 1)


def probabilities(value):
    """
    :param value: input string, comma separated or space separated
    :returns: a list of probabilities

    >>> probabilities('')
    []
    >>> probabilities('1')
    [1.0]
    >>> probabilities('0.1 0.2')
    [0.1, 0.2]
    >>> probabilities('0.1, 0.2')  # commas are ignored
    [0.1, 0.2]
    """
    return map(probability, value.replace(',', ' ').split())


def intensity_measure_types(value):
    """
    :param value: input string
    :returns: non-empty list of Intensity Measure Type objects

    >>> intensity_measure_types('PGA')
    ['PGA']
    >>> intensity_measure_types('PGA, SA(1.00)')
    ['PGA', 'SA(1.0)']
    """
    imts = []
    for chunk in value.split(','):
        imts.append(str(imt.from_string(chunk.strip())))
    return imts


def intensity_measure_types_and_levels(value):
    """
    :param value: input string
    :returns: Intensity Measure Type and Levels dictionary

    >>> intensity_measure_types_and_levels('{"PGA": [0.1, 0.2]}')
    {'PGA': [0.1, 0.2]}

    >>> intensity_measure_types_and_levels('{"PGA": [0.1]}')
    Traceback (most recent call last):
       ...
    ValueError: Not enough imls for PGA: [0.1]
    """
    dic = dictionary(value)
    for imt, imls in dic.iteritems():
        if len(imls) < 2:
            raise ValueError('Not enough imls for %s: %s' % (imt, imls))
        map(positivefloat, imls)
        if imls != sorted(imls):
            raise ValueError('The imls for %s are not sorted: %s' %
                             (imt, imls))
    return dic


def dictionary(value):
    """
    :param value: input string
    :returns: a Python dictionary

    >>> dictionary('')
    {}
    >>> dictionary('{}')
    {}
    >>> dictionary('{"a": 1}')
    {'a': 1}
    """
    if not value:
        return {}
    try:
        return ast.literal_eval(value)
    except:
        raise ValueError('%r is not a valid Python dictionary' % value)


def parameters(**names_vals):
    """
    Returns a dictionary {name: validator} by making sure
    that the validators are callable objects with a `__name__`.
    """
    for name, val in names_vals.iteritems():
        if not callable(val):
            raise ValueError(
                '%r for %s is not a validator: it is not callable'
                % (val, name))
        if not hasattr(val, '__name__'):
            raise ValueError(
                '%r for %s is not a validator: it has no __name__'
                % (val, name))
    return names_vals


# used in commonlib.oqvalidation
class ParamSet(object):
    """
    A set of valid interrelated parameters. Here is an example
    of usage:

    >>> class MyParams(ParamSet):
    ...     params = parameters(a=positiveint, b=positivefloat)
    ...
    ...     def constrain_not_too_big(self):
    ...         "The sum of a={a} and b={b} must be under 10"
    ...         return self.a + self.b < 10

    >>> MyParams(a='1', b='7.2')
    <MyParams a=1, b=7.2>

    >>> MyParams(a='1', b='9.2')
    Traceback (most recent call last):
    ...
    ValueError: The sum of a=1 and b=9.2 must be under 10

    The constrains are applied in lexicographic order.
    """
    params = {}

    def __init__(self, **names_vals):
        for name, val in names_vals.iteritems():
            if name.startswith(('_', 'constrain_')):
                raise NameError('The parameter name %s is not acceptable'
                                % name)
            try:
                convert = self.__class__.params[name]
            except KeyError:
                logging.warn('The parameter %r is unknown, ignoring' % name)
                continue
            try:
                value = convert(val)
            except:
                raise ValueError('Could not convert to %s: %s=%s'
                                 % (convert.__name__, name, val))
            setattr(self, name, value)

        constrains = sorted(getattr(self, constrain)
                            for constrain in dir(self.__class__)
                            if constrain.startswith('constrain_'))
        for constrain in constrains:
            if not constrain():
                dump = '\n'.join('%s=%s' % (n, v)
                                 for n, v in sorted(self.__dict__.items()))
                raise ValueError(constrain.__doc__ + 'Got:\n' + dump)

    def __repr__(self):
        names = sorted(n for n in vars(self) if not n.startswith('_'))
        nameval = ', '.join('%s=%s' % (n, getattr(self, n)) for n in names)
        return '<%s %s>' % (self.__class__.__name__, nameval)
