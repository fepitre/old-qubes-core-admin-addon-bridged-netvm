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
import re
import libvirt


def check_mac(mac):
    """Check MAC format."""
    mac_regex = re.compile('^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    return bool(re.match(mac_regex, mac))


def get_bridged_ifaces(vm):
    """Get bridged interfaces from features"""
    ifaces = []

    bridge_macs = sorted(list(set([str(br).split('_')[1] for br in vm.features if 'bridge_' in br])))
    for mac in bridge_macs:
        if check_mac(mac):
            name = vm.features.get('bridge_' + mac + '_name', '')
            backenddomain = vm.features.get('bridge_' + mac + '_backenddomain', '')

            if name and backenddomain:
                bridge = {
                    'mac': mac.lower(),
                    'name': vm.features.get('bridge_' + mac + '_name', ''),
                    'backenddomain': vm.features.get('bridge_' + mac + '_backenddomain', ''),
                    'ip': vm.features.get('bridge_' + mac + '_ip', ''),
                    'netmask': vm.features.get('bridge_' + mac + '_netmask', ''),
                    'gateway': vm.features.get('bridge_' + mac + '_gateway', '')
                }

                ifaces.append(bridge)
            else:
                vm.log.warning(
                    'QubesBridgedNetVMExtension: missing bridge name or backenddomain for interface {}'.format(mac))
        else:
            vm.log.warning('QubesBridgedNetVMExtension: invalid MAC {}'.format(mac))

    return ifaces


def attach_bridged_network(vm, bridge):
    """Attach network in this machine to it's bridged NetVM."""

    if vm.is_running():
        if vm.app.domains[bridge['backenddomain']] is None:
            raise qubes.exc.QubesVMError(vm, 'Bridged NetVM {} not found'.format(vm.app.domains[bridge['backenddomain']]))

        bridge_xml = '''
            <interface type="bridge">
                <source bridge="{name}" />
                <mac address="{mac}" />
                <backenddomain name="{backenddomain}" />
                <script path="vif-bridge" />
            </interface>
            '''.format(name=bridge['name'], mac=bridge['mac'], backenddomain=bridge['backenddomain'])

        vm.libvirt_domain.attachDevice(bridge_xml)


class QubesBridgedNetVMExtension(qubes.ext.Extension):
    """qubes-core-admin extension for handling Bridged NetVM"""

    @qubes.ext.handler('domain-qdb-create')
    def on_qdb_create(self, vm, event):
        for bridge in get_bridged_ifaces(vm):
            vm.untrusted_qdb.write('/net-config/' + bridge['mac'] + '/ip', bridge['ip'])
            vm.untrusted_qdb.write('/net-config/' + bridge['mac'] + '/netmask', bridge['netmask'])
            vm.untrusted_qdb.write('/net-config/' + bridge['mac'] + '/gateway', bridge['gateway'])

    @qubes.ext.handler('domain-pre-start')
    @asyncio.coroutine
    def on_domain_pre_start(self, vm, event, start_guid, **kwargs):
        for bridge in get_bridged_ifaces(vm):
            try:
                bridge_backenddomain = vm.app.domains[bridge['backenddomain']]
            except KeyError:
                vm.log.error('QubesBridgedNetVMExtension: Bridged NetVM not provided.')
                return

            if bridge_backenddomain.qid != 0:
                if not bridge_backenddomain.is_running():
                    yield from bridge_backenddomain.start(start_guid=start_guid, notify_function=None)

    @qubes.ext.handler('domain-start')
    def on_domain_start(self, vm, event, start_guid, **kwargs):
        for bridge in get_bridged_ifaces(vm):
            vm.log.info('Attaching bridged network {mac}'.format(mac=bridge['mac']))
            try:
                attach_bridged_network(vm, bridge)
            except (qubes.exc.QubesException, libvirt.libvirtError):
                vm.log.warning('Cannot attach network {mac}'.format(mac=bridge['mac']), exc_info=1)
