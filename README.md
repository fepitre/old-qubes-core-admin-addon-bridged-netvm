qubes-core-admin extension for handling Bridged NetVM
---------------------------------------------------------------

This extension allows you to connect a qube to a ___bridge___ network created inside another qube.

In order to use this extension, you need to first create a bridge into a qube and then, adding specific features to each qube connected to it.

For example, if we assume that you have created a bridge ```br0``` into ```sys-bridge``` and you want to connect a qube ```bridged-appvm``` to this ```br0``` then, you need to add three features to the qube:

* ```bridge_name```
* ```bridge_mac```
* ```bridge_backenddomain```

In order to perform that, in ```dom0``` or any ```adminvm``` having proper allowed qubes-rpc to ```bridged-appvm```, do:

* ```qvm-features bridged-appvm bridge_name br0```
* ```qvm-features bridged-appvm bridge_mac 00:16:3E:5A:51:8A```
* ```qvm-features bridged-appvm bridge_backenddomain sys-bridge```

Please note that the specified MAC is arbitrary. In the case where you want to connect ```bridged-appvm``` to any usual NetVM but also, add a second interface to a bridge, you need to ensure that the mac provided by Qubes and the one you specified in the features ___are not the same___.