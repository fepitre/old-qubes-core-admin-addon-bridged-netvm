RPM_SPEC_FILES.dom0 := rpm_spec/qubes-core-admin-addon-bridged-netvm.spec

RPM_SPEC_FILES := $(RPM_SPEC_FILES.$(PACKAGE_SET))

# vim: ft=make
