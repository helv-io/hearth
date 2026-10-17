import unittest
from pathlib import Path

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
        self.assertEqual(report.action, "Install USB driver")
        self.assertIn("Apple.AppleMobileDeviceSupport", report.command)
        self.assertIn("--disable-interactivity", report.command)
        self.assertIn("9np83lwlpz9k", report.url)

    def test_windows_without_winget_opens_the_store(self):
        report = status(Probe(system="Windows"))
        self.assertEqual(report.kind, "browse")
        self.assertEqual(report.command, ())
        self.assertEqual(report.action, "Open Apple Devices page")
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


class PlainTextTests(unittest.TestCase):
    WORDS = ("pkexec", "winget", "usbmuxd", "flatpak-spawn", "sudo", "systemctl", "net start", "sh -c")

    def probes(self):
        return [
            linux(socket_open=True),
            linux(have_usbmuxd=True),
            linux(package_manager="pacman"),
            linux(flatpak=True, package_manager="apt-get"),
            linux(flatpak=True, package_manager="pacman", have_agent=False),
            linux(flatpak=True, have_usbmuxd=True, have_agent=False),
            Probe(system="Windows", windows_installed=True),
            Probe(system="Windows", have_winget=True),
            Probe(system="Windows"),
            Probe(system="FreeBSD"),
        ]

    def test_the_words_a_person_reads_have_no_commands(self):
        for probe in self.probes():
            report = status(probe)
            for text in (report.headline, report.detail, report.action, report.url_action):
                for word in self.WORDS:
                    if report.kind == "manual" and word == "usbmuxd":
                        continue  # a Linux with no known installer is told the package name
                    self.assertNotIn(word, text, (probe, text))

    def test_a_manual_step_exists_whenever_there_is_a_command(self):
        for probe in self.probes():
            report = status(probe)
            if report.command:
                self.assertTrue(report.manual, probe)

    def test_windows_manual_steps(self):
        self.assertEqual(
            status(Probe(system="Windows", have_winget=True)).manual,
            "winget install -e --id Apple.AppleMobileDeviceSupport",
        )
        self.assertEqual(
            status(Probe(system="Windows", windows_installed=True)).manual,
            'net start "Apple Mobile Device Service"',
        )

    def test_a_failed_windows_install_offers_the_store_page(self):
        report = status(Probe(system="Windows", have_winget=True))
        self.assertIn("9np83lwlpz9k", report.url)
        self.assertEqual(report.url_action, "Open Apple Devices page")


class InstallMessageTests(unittest.TestCase):
    def run_install(self, code, plan_probe):
        from unittest import mock
        from hearth import drivers

        needed = status(plan_probe)
        with mock.patch.object(drivers, "status", return_value=needed), \
                mock.patch.object(drivers, "_run", return_value=(code, "pkexec: boom /usr/bin/x")), \
                mock.patch.object(drivers, "_is_windows", return_value=False):
            return drivers.install()

    def test_failures_are_plain_and_offer_a_retry(self):
        linux_plan = linux(package_manager="pacman")
        for code in (1, 124, 126, 127, 0):
            text = self.run_install(code, linux_plan)
            self.assertIn("Try again", text)
            for word in PlainTextTests.WORDS + ("boom", "/usr"):
                self.assertNotIn(word, text)

    def test_a_failed_windows_install_also_offers_the_page(self):
        text = self.run_install(1, Probe(system="Windows", have_winget=True))
        self.assertIn("Apple Devices page", text)


class FlatpakHostTests(unittest.TestCase):
    """Inside the Flatpak the USB service lives on the host, so Hearth asks the host what it has and runs the
    setup there. 0.6.2 asked, but squashed the answer onto one line, read nothing from it, and showed the
    'cannot set it up by itself' card on a Linux it could set up (Arch, with pacman)."""

    def inventory(self, tools):
        """Run the real host script with only `tools` on its PATH, the way flatpak-spawn --host would."""
        import os
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest import mock
        from hearth import drivers

        real_run = subprocess.run
        stack = tempfile.TemporaryDirectory()
        self.addCleanup(stack.cleanup)
        for name in tools:
            tool = Path(stack.name) / name
            tool.write_text("#!/bin/sh\n")
            tool.chmod(0o755)

        def fake(argv, **kwargs):
            self.assertEqual(argv[:3], ["flatpak-spawn", "--host", "sh"])
            return real_run(["/bin/sh", *argv[3:]], env=dict(os.environ, PATH=stack.name), **kwargs)

        with mock.patch.object(drivers.subprocess, "run", side_effect=fake):
            return drivers._linux_inventory(True)

    def test_the_host_answer_keeps_its_lines(self):
        from unittest import mock
        from hearth import drivers

        done = mock.Mock(returncode=0, stdout="SOCKET=0\nUSBMUXD=0\nSYSTEMCTL=1\nMANAGER=pacman\n", stderr="")
        with mock.patch.object(drivers.subprocess, "run", return_value=done):
            self.assertEqual(drivers._run(("x",), 5, keep_lines=True)[1], done.stdout)
            self.assertNotIn("\n", drivers._run(("x",), 5)[1])

    def test_an_arch_host_is_read_as_arch(self):
        found = self.inventory(["pacman", "systemctl"])
        self.assertEqual(found["manager"], "pacman")
        self.assertTrue(found["systemctl"])

    def test_a_debian_host_is_read_as_debian(self):
        found = self.inventory(["apt-get", "systemctl"])
        self.assertEqual(found["manager"], "apt-get")

    def test_a_fedora_host_is_read_as_fedora(self):
        found = self.inventory(["dnf", "systemctl"])
        self.assertEqual(found["manager"], "dnf")

    def test_a_host_with_the_service_installed_is_read_as_having_it(self):
        found = self.inventory(["pacman", "systemctl", "usbmuxd"])
        self.assertTrue(found["usbmuxd"])

    def test_a_host_that_cannot_be_asked_is_read_as_nothing_found(self):
        from unittest import mock
        from hearth import drivers

        with mock.patch.object(drivers, "_run", return_value=(127, "no such file")):
            self.assertEqual(
                drivers._linux_inventory(True),
                {"socket": False, "usbmuxd": False, "systemctl": False, "manager": "", "agent": True},
            )

    def test_flatpak_on_arch_offers_one_click_setup(self):
        report = status(linux(flatpak=True, package_manager="pacman"))
        self.assertTrue(report.needed and not report.ready)
        self.assertEqual(report.kind, "install")
        self.assertEqual(report.action, "Install USB service")
        self.assertEqual(report.command[:5], ("flatpak-spawn", "--host", "pkexec", "sh", "-c"))
        self.assertIn("pacman -S --needed --noconfirm usbmuxd", report.command[5])
        self.assertTrue(report.manual)
        self.assertNotIn("flatpak-spawn", report.manual)

    def test_flatpak_on_debian_and_fedora_offer_one_click_setup(self):
        for manager, word in (("apt-get", "apt-get install -y usbmuxd"), ("dnf", "dnf install -y usbmuxd")):
            report = status(linux(flatpak=True, package_manager=manager))
            self.assertEqual(report.kind, "install", manager)
            self.assertEqual(report.command[:3], ("flatpak-spawn", "--host", "pkexec"), manager)
            self.assertIn(word, report.command[-1], manager)

    def test_flatpak_with_the_service_installed_but_stopped_offers_to_start_it(self):
        report = status(linux(flatpak=True, have_usbmuxd=True, package_manager="pacman"))
        self.assertEqual(report.kind, "start")
        self.assertEqual(report.action, "Start USB service")
        self.assertEqual(report.command[:3], ("flatpak-spawn", "--host", "pkexec"))
        self.assertNotIn("pacman", report.command[-1])

    def test_a_running_service_on_the_host_needs_nothing(self):
        report = status(linux(flatpak=True, have_usbmuxd=True, socket_open=True, package_manager="pacman"))
        self.assertTrue(report.ready)
        self.assertEqual(report.command, ())

    def test_the_whole_path_from_the_host_answer_to_the_button(self):
        from unittest import mock
        from hearth import drivers

        answer = "SOCKET=0\nUSBMUXD=0\nSYSTEMCTL=1\nMANAGER=pacman\n"
        done = mock.Mock(returncode=0, stdout=answer, stderr="")
        with mock.patch.object(drivers, "_system", return_value="Linux"), \
                mock.patch.object(drivers, "in_flatpak", return_value=True), \
                mock.patch.object(drivers, "_has_stored_pairing", return_value=False), \
                mock.patch.object(drivers.subprocess, "run", return_value=done):
            report = drivers.status()
        self.assertEqual(report.kind, "install")
        self.assertEqual(report.action, "Install USB service")
        self.assertEqual(report.command[:3], ("flatpak-spawn", "--host", "pkexec"))

    def test_the_host_says_whether_a_password_window_exists(self):
        from unittest import mock
        from hearth import drivers

        for answer, expected in (("AGENT=0\n", False), ("AGENT=1\n", True), ("MANAGER=pacman\n", True)):
            done = mock.Mock(returncode=0, stdout=answer, stderr="")
            with mock.patch.object(drivers.subprocess, "run", return_value=done):
                self.assertIs(drivers._linux_inventory(True)["agent"], expected, answer)

    def test_without_a_password_window_the_button_is_replaced_by_steps(self):
        """On Arch with Hyprland nothing answers pkexec, so the setup would wait with nothing on screen."""
        for probe in (
            linux(flatpak=True, package_manager="pacman", have_agent=False),
            linux(flatpak=True, have_usbmuxd=True, have_agent=False),
        ):
            report = status(probe)
            self.assertEqual(report.kind, "manual", probe)
            self.assertEqual((report.action, report.command), ("", ()), probe)
            self.assertIn("password", report.detail)
            self.assertTrue(report.manual.startswith("sudo sh -c "), report.manual)
            self.assertNotIn("flatpak-spawn", report.manual)

    def test_a_running_service_needs_no_password_window(self):
        self.assertTrue(status(linux(flatpak=True, socket_open=True, have_agent=False)).ready)

    def test_the_desktop_helpers_are_told_apart_by_name_in_both_places(self):
        import re
        import subprocess
        from hearth import drivers

        shell = re.search(r"^\s+(\*polkit\*agent.*?)\) agent=1", Path(drivers.__file__).read_text(encoding="utf-8"), re.M).group(1)
        names = {
            "polkit-gnome-authentication-agent-1": True,
            "hyprpolkitagent": True,
            "polkit-kde-authentication-agent-1": True,
            "lxqt-policykit-agent": True,
            "xfce-polkit": True,
            "gnome-shell": True,
            "soteria": True,
            "polkitd": False,
            "bash": False,
            "Hyprland": False,
        }
        for name, expected in names.items():
            out = subprocess.run(
                ["/bin/sh", "-c", f'case "$1" in {shell}) echo 1;; *) echo 0;; esac', "sh", name],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(out == "1", expected, f"{name} in the host script")
            self.assertEqual(bool(drivers._AGENT_NAME.search(name)), expected, f"{name} in the app")
