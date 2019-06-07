# vim: fileencoding=utf-8

import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='qubes_bridged_netvm',
        version=open('version').read().strip(),
        author='QubesOS',
        author_email='frederic.pierret@qubes-os.org',
        description='Qubes Bridged NetVM core-admin extension',
        license='GPL2+',
        url='https://www.qubes-os.org/',

        packages=('qubes_bridged_netvm',),

        entry_points={
            'qubes.ext': [
                'qubes_bridged_netvm = qubes_bridged_netvm:QubesBridgedNetVMExtension',
            ],
        }
    )
