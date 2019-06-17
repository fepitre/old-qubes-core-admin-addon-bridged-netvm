all:
	python3 setup.py build

install:
	# force /usr/bin before /bin to have /usr/bin/python instead of /bin/python
	PATH="/usr/bin:$$PATH" python3 setup.py install $(PYTHON_PREFIX_ARG) -O1 --skip-build --root $(DESTDIR)

	# We currently copy bridge.xml as xen-dist.xml in the global rendering as we
	# still have not a proper way of stacking specific configuration for core-admin addons
	mkdir -p $(DESTDIR)/etc/qubes/templates/libvirt/
	install -m 660 bridge.xml $(DESTDIR)/etc/qubes/templates/libvirt/xen-dist.xml
