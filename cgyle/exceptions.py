# Copyright (c) 2024 SUSE Software Solutions Germany GmbH.  All rights reserved.
#
# This file is part of cgyle.
#
# cgyle is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# cgyle is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with cgyle.  If not, see <http://www.gnu.org/licenses/>
#
class CgyleError(Exception):
    """
    Base class to handle all known exceptions

    Specific exceptions are implemented as sub classes of CgyleError
    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return format(self.message)


class CgyleJsonError(CgyleError):
    """
    Exception raised if HTTP response cannot be converted to JSON
    """


class CgyleCommandError(CgyleError):
    """
    Exception raised if an external command call failed
    """


class CgyleFilterExpressionError(CgyleError):
    """
    Exception raised on invalid regular expression
    """


class CgyleRequestError(CgyleError):
    """
    Exception raised if http request cannot be processed
    """


class CgyleCatalogError(CgyleError):
    """
    Exception raised if the expected v2 catalog format doesn't exist
    """
