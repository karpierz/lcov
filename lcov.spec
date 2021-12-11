Summary: A graphical GCOV front-end
Name: lcov
Version: 1.15
Release: 1
License: GPLv2+
Group: Development/Tools
URL: http://ltp.sourceforge.net/coverage/lcov.php
Source0: http://downloads.sourceforge.net/ltp/%{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-root
BuildArch: noarch
Requires: perl >= 5.8.8

%prep
%setup -q -n %{name}-%{version}

%build
exit 0

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT PREFIX=/usr CFG_DIR=/etc

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/usr/bin/*
/usr/share/man/man*/*
%config /etc/*
