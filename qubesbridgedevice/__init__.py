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

"""qubes-core-admin extension for handling Bridge Device"""

import qubes.ext
import re
import lxml
import string
import random
import ipaddress
import jinja2

name_re = re.compile(r"^[a-z0-9-]{1,12}$")


def rand_mac():
    return "00:16:3e:%02x:%02x:%02x" % (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def check_mac(mac):
    """Check MAC format."""
    mac_regex = re.compile('^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    return bool(re.match(mac_regex, mac))


def check_ip(ip):
    """Check ip format."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def get_netmask_from_prefix(prefix):
    try:
        network_conf = ipaddress.IPv4Interface('0.0.0.0' + '/' + prefix)
    except ipaddress.NetmaskValueError:
        raise qubes.exc.QubesValueError('Invalid prefix: ' + prefix)

    return str(network_conf.network.netmask)


def get_prefix_from_netmask(netmask):
    try:
        network_conf = ipaddress.IPv4Interface('0.0.0.0' + '/' + netmask)
    except ipaddress.NetmaskValueError:
        raise qubes.exc.QubesValueError('Invalid netmask: ' + netmask)

    return str(network_conf.network.prefixlen)


def get_subnet(ip, netmask):
    try:
        network_conf = ipaddress.IPv4Interface(ip + '/' + netmask)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        raise qubes.exc.QubesValueError('Invalid ip/netmask: ' + ip + '/' + netmask)

    return str(network_conf.network.network_address)


class BridgeDevice(qubes.devices.DeviceInfo):
    def __init__(self, backend_domain, ident):
        super(BridgeDevice, self).__init__(backend_domain=backend_domain, ident=ident)
        self._description = None

    @property
    def description(self):
        """Human readable device description"""
        if self._description is None:
            if not self.backend_domain.is_running():
                return self.ident
            safe_set = {ord(c) for c in string.ascii_letters + string.digits + '()+,-.:=_/ '}
            untrusted_desc = self.backend_domain.untrusted_qdb.read(
                '/qubes-bridge-devices/{}/desc'.format(self.ident))
            if not untrusted_desc:
                return ''
            desc = ''.join((chr(c) if c in safe_set else '_') for c in untrusted_desc)
            self._description = desc
        return self._description


class BridgeDeviceExtension(qubes.ext.Extension):
    @qubes.ext.handler('domain-init', 'domain-load')
    def on_domain_init_load(self, vm, event):
        """Initialize watching for changes"""
        vm.watch_qdb_path('/qubes-bridge-devices')

    @qubes.ext.handler('domain-qdb-change:/qubes-bridge-devices')
    def on_qdb_change(self, vm, event, path):
        """A change in QubesDB means a change in device list"""
        vm.fire_event('device-list-change:bridge')

    @staticmethod
    def device_get(vm, ident):
        """Read information about device from QubesDB

        :param vm: backend VM object
        :param ident: device identifier
        :returns BridgeDevice"""

        untrusted_qubes_device_attrs = vm.untrusted_qdb.list('/qubes-bridge-devices/{}/'.format(ident))
        if not untrusted_qubes_device_attrs:
            return None
        return BridgeDevice(vm, ident)

    @qubes.ext.handler('device-list:bridge')
    def on_device_list_bridge(self, vm, event):
        if not vm.is_running():
            return

        untrusted_qubes_devices = vm.untrusted_qdb.list('/qubes-bridge-devices/')
        untrusted_idents = set(untrusted_path.split('/', 3)[2] for untrusted_path in untrusted_qubes_devices)

        for untrusted_ident in untrusted_idents:
            if not name_re.match(untrusted_ident):
                msg = ("%s vm's device path name contains unsafe characters. "
                       "Skipping it.")
                vm.log.warning(msg % vm.name)
                continue

            ident = untrusted_ident

            device_info = self.device_get(vm, ident)
            if device_info:
                yield device_info

    @qubes.ext.handler('device-get:bridge')
    def on_device_get_bridge(self, vm, event, ident):
        if not vm.is_running():
            return
        if not vm.app.vmm.offline_mode:
            device_info = self.device_get(vm, ident)
            if device_info:
                yield device_info

    @staticmethod
    def generate_unused_mac(vm):
        """Generate unused MAC address for <mac address=.../> parameter"""
        assert vm.is_running()

        xml = vm.libvirt_domain.XMLDesc()
        parsed_xml = lxml.etree.fromstring(xml)
        used = [target.get('dev', None) for target in parsed_xml.xpath("//domain/devices/interface/mac")]

        # We generate arbitraly at most 32 MAC address in case of collisions
        available_macs = (rand_mac() for _ in range(32))

        for mac in available_macs:
            if mac not in used:
                return mac
        return None

    @qubes.ext.handler('device-pre-attach:bridge')
    def on_device_pre_attached_bridge(self, vm, event, device, options):
        # validate options
        for option, value in options.items():
            if option == 'mac':
                if not check_mac(value):
                    raise qubes.exc.QubesValueError('Invalid MAC address: ' + value)
            elif option == 'ip' or option == 'netmask' or option == 'gateway':
                if not check_ip(value):
                    raise qubes.exc.QubesValueError('Invalid ' + option + ' address: ' + value)
            else:
                raise qubes.exc.QubesValueError(
                    'Unsupported option {}'.format(option))

        if not vm.is_running():
            return

        if not device.backend_domain.is_running():
            raise qubes.exc.QubesVMNotRunningError(device.backend_domain,
                                                   'Domain {} needs to be running to attach device from it'.format(
                                                       device.backend_domain.name))

        if 'mac' not in options:
            options['mac'] = self.generate_unused_mac(vm)

        # Write network configuration
        if 'ip' in options and 'netmask' in options:
            vm.untrusted_qdb.write('/net-config/' + options['mac'] + '/ip', options['ip'])
            vm.untrusted_qdb.write('/net-config/' + options['mac'] + '/netmask', options['netmask'])

            if 'gateway' in options:
                vm.untrusted_qdb.write('/net-config/' + options['mac'] + '/gateway', options['gateway'])

            vm.libvirt_domain.attachDevice(self.generate_bridge_xml(device, options))

    @qubes.ext.handler('device-list-attached:bridge')
    def on_device_list_attached(self, vm, event, **kwargs):
        if not vm.is_running():
            return

        xml_desc = lxml.etree.fromstring(vm.libvirt_domain.XMLDesc())

        for iface in xml_desc.findall('devices/interface'):
            if iface.get('type') != 'bridge':
                continue

            backend_domain_node = iface.find('backenddomain')
            if backend_domain_node is None:
                continue
            backend_domain = vm.app.domains[backend_domain_node.get('name')]

            bridge_name_node = iface.find('source')
            if bridge_name_node is None:
                continue
            ident = bridge_name_node.get('bridge')

            options = {}

            mac_node = iface.find('mac')
            if mac_node is None:
                continue
            mac = mac_node.get('address')
            if not mac:
                continue
            options['mac'] = mac

            ip_node = iface.find('ip')
            if ip_node is None:
                continue
            ip = ip_node.get('address')
            prefix = ip_node.get('prefix')
            if not ip or not prefix:
                continue

            options['ip'] = ip
            options['netmask'] = get_netmask_from_prefix(prefix)

            route_node = iface.find('route')
            if route_node is not None:
                gateway = route_node.get('gateway')

                if gateway:
                    options['gateway'] = gateway

            yield (BridgeDevice(backend_domain, ident), options)

    @qubes.ext.handler('device-pre-detach:bridge')
    def on_device_pre_detached_bridge(self, vm, event, device):
        if not vm.is_running():
            return

        for attached_device, options in self.on_device_list_attached(vm, event):
            if attached_device == device:
                vm.libvirt_domain.detachDevice(self.generate_bridge_xml(device, options))
                break

    @staticmethod
    def generate_bridge_xml(device, options):
        options_ext = dict(options)
        options_ext['prefix'] = get_prefix_from_netmask(options['netmask'])
        options_ext['subnet'] = get_subnet(options['ip'], options['netmask'])

        bridge_xml = '''
            <interface type="bridge">
                <source bridge="{{device.ident}}" />
                <mac address="{{options.get('mac')}}" />
                <backenddomain name="{{device.backend_domain.name}}" />
                <script path="vif-bridge" />
                {%- if options.get('ip') and options.get('prefix') %}
                <ip address="{{options.get('ip')}}" prefix="{{options.get('prefix')}}" />
                {%- if options.get('gateway') %}
                <route family="ipv4" address="{{options.get('subnet')}}" prefix="{{options.get('prefix')}}" gateway="{{options.get('gateway')}}" />
                {%- endif %}
                {%- endif %}
            </interface>
        '''

        return jinja2.Environment().from_string(bridge_xml).render(device=device, options=options_ext)

    @qubes.ext.handler('domain-start')
    def on_domain_start(self, vm, event, start_guid, **kwargs):
        for bridge in vm.devices['bridge'].assignments():
            self.on_device_pre_attached_bridge(vm, event, bridge.device, bridge.options)
