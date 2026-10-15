import unittest

from hearth.drivers import Probe, status


def linux(**kwargs) -> Probe:
    base = dict(system="Linux", have_systemctl=True)
    base.update(kwargs)
    return Probe(**base)


class DriverPlanTests(unittest.TestCase):
    def test_macos_needs_nothing(self):
        report = status(Probe(system="Darwin"))
        self.assertFalse(report.needed)
        self.assertTrue(report.ready)
        self.assertEqual(report.command, ())
        self.assertEqual(report.action, "")

    def test_a_live_socket_is_enough(self):
        report = status(linux(socket_open=True))
        self.assertTrue(report.ready)
        self.assertEqual(report.command, ())

    def test_an_installed_daemon_is_started(self):
        report = status(linux(have_usbmuxd=True))
        self.assertEqual(report.kind, "start")
        self.assertEqual(report.action, "Start USB service")
        self.assertEqual(report.command[:3], ("pkexec", "sh", "-c"))
        self.assertIn("systemctl enable --now usbmuxd", report.command[3])
        self.assertIn("pkexec", report.manual)

    def test_pacman_installs_and_starts(self):
        report = status(linux(package_manager="pacman"))
        self.assertEqual(report.kind, "install")
        self.assertEqual(report.action, "Install USB service")
        self.assertIn("pacman -S --needed --noconfirm usbmuxd", report.command[3])
        self.assertIn("systemctl enable --now usbmuxd", report.command[3])

    def test_apt_installs_without_a_prompt(self):
        report = status(linux(package_manager="apt-get"))
        self.assertIn("DEBIAN_FRONTEND=noninteractive", report.command[3])
        self.assertIn("apt-get install -y usbmuxd", report.command[3])

    def test_flatpak_runs_the_install_on_the_host(self):
        report = status(linux(flatpak=True, package_manager="pacman"))
        self.assertEqual(report.command[:4], ("flatpak-spawn", "--host", "pkexec", "sh"))
        self.assertNotIn("flatpak-spawn", report.manual)

    def test_an_unknown_distro_shows_commands_and_does_not_guess(self):
        report = status(linux(have_systemctl=False))
        self.assertEqual(report.kind, "manual")
        self.assertEqual(report.command, ())
        self.assertEqual(report.action, "")
        self.assertIn("pacman", report.manual)
        self.assertIn("apt install", report.manual)

    def test_windows_running_service_is_ready(self):
        report = status(Probe(system="Windows", windows_installed=True, windows_running=True))
        self.assertTrue(report.ready)
        self.assertEqual(report.command, ())

    def test_windows_stopped_service_is_started(self):
        report = status(Probe(system="Windows", windows_installed=True))
        self.assertEqual(report.kind, "start")
        self.assertEqual(report.command, ("net", "start", "Apple Mobile Device Service"))

    def test_windows_uses_winget_for_the_driver_package(self):
        report = status(Probe(system="Windows", have_winget=True))
        self.assertEqual(report.kind, "install")
        self.assertEqual(report.action, "Install driver")
        self.assertIn("Apple.AppleMobileDeviceSupport", report.command)
        self.assertIn("--disable-interactivity", report.command)
        self.assertEqual(report.url, "")

    def test_windows_without_winget_opens_the_store(self):
        report = status(Probe(system="Windows"))
        self.assertEqual(report.kind, "browse")
        self.assertEqual(report.command, ())
        self.assertEqual(report.action, "Open Apple Devices")
        self.assertIn("9np83lwlpz9k", report.url)

    def test_other_systems_are_told_the_limit(self):
        report = status(Probe(system="FreeBSD"))
        self.assertFalse(report.ready)
        self.assertEqual(report.command, ())
        self.assertIn("macOS", report.detail)

    def test_live_probe_does_not_install_anything(self):
        report = status()
        self.assertIn(report.kind, ("ready", "install", "start", "manual", "browse"))
        if report.ready:
            self.assertEqual(report.command, ())


class QuietCommandTests(unittest.TestCase):
    def test_windows_helpers_get_no_console_window(self):
        from unittest import mock
        from hearth import drivers

        done = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(drivers, "_system", return_value="Windows"), \
                mock.patch.object(drivers.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                mock.patch.object(drivers.subprocess, "run", return_value=done) as run:
            drivers._run(("net", "start", "x"), timeout=5)
            drivers._windows_service()
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["creationflags"], 0x08000000)
            self.assertIs(call.kwargs["stdin"], drivers.subprocess.DEVNULL)

    def test_other_systems_pass_no_creation_flags(self):
        from unittest import mock
        from hearth import drivers

        with mock.patch.object(drivers, "_system", return_value="Linux"):
            self.assertNotIn("creationflags", drivers._quiet())
