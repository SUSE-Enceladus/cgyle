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
import sys
import logging as log

from cgyle.cli import Cli
from cgyle.exceptions import CgyleError


def main() -> None:
    """
    cgyle - container preload
    """
    try:
        Cli()
    except CgyleError as issue:
        # known exception, log information and exit
        log.error(f'{type(issue).__name__}: {issue}')
        sys.exit(1)
    except KeyboardInterrupt:
        log.error('cgyle aborted by keyboard interrupt')
        sys.exit(1)
    except SystemExit as error:
        # user exception, program aborted by user
        sys.exit(format(error))
    except Exception:
        # exception we did no expect, show python backtrace
        log.error('Unexpected error:')
        raise
