import unittest
from unittest import mock

from hearth import device, drivers, wireless


class WordingTests(unittest.TestCase):
    def test_the_two_failures_say_what_to_do_in_few_words(self):
        self.assertEqual(
            device.friendly(wireless.CantFind()),
            "Can't find your iPhone on this network. Wake it, or plug it in.",
        )
        self.assertEqual(
            device.friendly(wireless.Lost()),
            "Lost the connection to your iPhone. Wake it and try again.",
        )

    def test_no_failure_text_uses_jargon_or_dashes(self):
        for text in (wireless.CANT_FIND, wireless.LOST, wireless.WIFI_LABEL, wireless.WIFI_HINT):
            self.assertNotRegex(text.lower(), r"usbmux|lockdown|bonjour|mdns|\u2014|\u2013")

    def test_install_success_names_no_removed_button(self):
        ready = drivers.Report(False, True, "ready")
        needed = drivers.Report(True, False, "install", command=("x",))
        with mock.patch.object(drivers, "status", side_effect=[needed, ready]), \
                mock.patch.object(drivers, "_run", return_value=(0, "")), \
                mock.patch.object(drivers, "_is_windows", return_value=False):
            text = drivers.install()
        self.assertTrue(text.startswith("USB support is ready."))
        self.assertNotIn("pull", text.lower())


if __name__ == "__main__":
    unittest.main()
