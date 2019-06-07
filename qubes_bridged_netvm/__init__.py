# -*- encoding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2019 Frédéric Pierret <frederic.pierret@qubes-os.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

"""qubes-core-admin extension for handling Bridged NetVM"""

import qubes.ext
import asyncio


class QubesBridgedNetVMExtension(qubes.ext.Extension):
    """qubes-core-admin extension for handling Bridged NetVM"""

    @qubes.ext.handler('domain-pre-start')
    @asyncio.coroutine
    def on_domain_pre_start(self, vm, event, start_guid, **kwargs):
        if 'bridge_backenddomain' in vm.features:
            backenddomain = vm.features['bridge_backenddomain']
            try:
                bridge_backenddomain = vm.app.domains[backenddomain]
            except KeyError:
                vm.log.error('QubesBridgedNetVMExtension: Bridged NetVM not provided.')
                return

            if bridge_backenddomain.qid != 0:
                if not bridge_backenddomain.is_running():
                    yield from bridge_backenddomain.start(start_guid=start_guid, notify_function=None)
