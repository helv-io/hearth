"""The model call is streamed, only silence times it out, and the person can cancel it.

A small local server stands in for the provider, so the real request code runs.
"""

import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import ai, drivers
from hearth.controller import Controller

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
READY = drivers.Probe(system="Linux", socket_open=True)
PROPOSAL = {"summary": "Two games together.", "dock": [], "pages": [["a", "b"]]}
FAST = ai.Limits(first=2.0, between=1.5, cap=20.0)


def sse(obj) -> bytes:
    return b"data: " + json.dumps(obj).encode() + b"\n\n"


def piece(text: str, key: str = "content") -> bytes:
    return sse({"choices": [{"delta": {key: text}}]})


def pieces_of(text: str, size: int = 12):
    return [piece(text[i:i + size]) for i in range(0, len(text), size)]


class Provider:
    """A local chat endpoint. Each request takes the next scripted behavior and is recorded."""

    def __init__(self, script):
        self.script = list(script)
        self.seen: list[dict] = []
        self.accepts: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                outer.seen.append(json.loads(self.rfile.read(length)))
                outer.accepts.append(self.headers.get("Accept") or "")
                behave = outer.script.pop(0) if len(outer.script) > 1 else outer.script[0]
                try:
                    behave(self)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def start_stream(handler):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()


def write(handler, data: bytes):
    handler.wfile.write(data)
    handler.wfile.flush()


def streams(parts, gap=0.0, lead=0.0, done=True):
    def behave(handler):
        start_stream(handler)
        time.sleep(lead)
        for part in parts:
            write(handler, part)
            time.sleep(gap)
        if done:
            write(handler, b"data: [DONE]\n\n")
    return behave


def goes_silent_after(parts, seconds=30.0):
    def behave(handler):
        start_stream(handler)
        for part in parts:
            write(handler, part)
        time.sleep(seconds)
    return behave


def replies_with_json(content=None):
    def behave(handler):
        data = json.dumps({"choices": [{"message": {"content": content or json.dumps(PROPOSAL)}}]}).encode()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        write(handler, data)
    return behave


def refuses(status, message):
    def behave(handler):
        data = json.dumps({"error": {"message": message}}).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        write(handler, data)
    return behave


TEXT = json.dumps(PROPOSAL)


class ModelCallTests(unittest.TestCase):
    def setUp(self):
        ai.forget_refusals()
        for name in ("current_outline", "catalog"):
            patcher = patch.object(ai, name, return_value=[])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.providers: list[Provider] = []
        self.addCleanup(self.close_all)

    def close_all(self):
        for provider in self.providers:
            provider.close()

    def provider(self, *script) -> Provider:
        made = Provider(script)
        self.providers.append(made)
        return made

    def organize(self, provider, limits=FAST, **extra):
        return ai.organize(provider.base, "key", "some-model", "Put games together.", [], limits=limits, **extra)

    def test_a_streamed_reply_is_assembled(self):
        provider = self.provider(streams(pieces_of(TEXT)))
        self.assertEqual(self.organize(provider), PROPOSAL)
        sent = provider.seen[0]
        self.assertIs(sent["stream"], True)
        self.assertEqual(sent["reasoning_effort"], "low")
        self.assertIn("text/event-stream", provider.accepts[0])

    def test_reasoning_text_is_not_part_of_the_answer(self):
        parts = [piece("let me think about it", "reasoning_content"), *pieces_of(TEXT)]
        provider = self.provider(streams(parts))
        self.assertEqual(self.organize(provider), PROPOSAL)

    def test_progress_says_how_much_has_arrived(self):
        said = []
        provider = self.provider(streams(pieces_of(TEXT, 5), gap=0.03))
        self.organize(provider, progress=said.append)
        self.assertTrue(said)
        self.assertTrue(all(text.startswith("Asking the model…") for text in said))

    def test_silence_before_the_first_word_is_fine_within_the_limit(self):
        provider = self.provider(streams(pieces_of(TEXT), lead=0.9))
        self.assertEqual(self.organize(provider, ai.Limits(first=2.0, between=0.5, cap=20.0)), PROPOSAL)

    def test_a_slow_answer_is_fine_while_words_keep_coming(self):
        # The whole answer takes much longer than the silence limit, but never goes quiet for that long.
        parts = pieces_of(TEXT, 8)
        provider = self.provider(streams(parts, gap=0.25))
        started = time.monotonic()
        result = self.organize(provider, ai.Limits(first=2.0, between=0.6, cap=30.0))
        self.assertEqual(result, PROPOSAL)
        self.assertGreater(time.monotonic() - started, 0.6 * 2)

    def test_silence_before_the_first_word_fails_in_plain_words(self):
        provider = self.provider(goes_silent_after([]))
        started = time.monotonic()
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider, ai.Limits(first=0.6, between=0.3, cap=20.0))
        self.assertEqual(str(caught.exception), "The model did not answer for 1 second.")
        self.assertLess(time.monotonic() - started, 5)

    def test_silence_after_the_first_word_says_it_stopped_partway(self):
        provider = self.provider(goes_silent_after(pieces_of(TEXT)[:2]))
        started = time.monotonic()
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider, ai.Limits(first=5.0, between=0.6, cap=20.0))
        self.assertEqual(str(caught.exception), "The model went quiet for 1 second partway through its answer.")
        self.assertLess(time.monotonic() - started, 4)

    def test_the_limit_is_named_in_minutes_when_it_is_whole_minutes(self):
        self.assertEqual(ai._span(180), "3 minutes")
        self.assertEqual(ai._span(60), "1 minute")
        self.assertEqual(ai._span(90), "90 seconds")
        self.assertEqual(ai._span(600), "10 minutes")

    def test_the_defaults_are_long_enough_for_a_model_that_thinks_first(self):
        limits = ai.Limits()
        self.assertEqual((limits.first, limits.between, limits.cap), (180.0, 60.0, 600.0))

    def test_the_overall_cap_only_stops_an_answer_that_never_ends(self):
        endless = pieces_of("x" * 400, 1)
        provider = self.provider(streams(endless, gap=0.1, done=False))
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider, ai.Limits(first=5.0, between=5.0, cap=0.7))
        self.assertIn("was still going after 1 second", str(caught.exception))

    def test_reasoning_effort_is_dropped_when_refused_and_remembered(self):
        provider = self.provider(
            refuses(400, "Unknown parameter: reasoning_effort"),
            streams(pieces_of(TEXT)),
        )
        self.assertEqual(self.organize(provider), PROPOSAL)
        self.assertEqual(len(provider.seen), 2)
        self.assertIn("reasoning_effort", provider.seen[0])
        self.assertNotIn("reasoning_effort", provider.seen[1])
        self.assertIs(provider.seen[1]["stream"], True)
        self.assertEqual(self.organize(provider), PROPOSAL)
        self.assertEqual(len(provider.seen), 3)
        self.assertNotIn("reasoning_effort", provider.seen[2])

    def test_a_refusal_for_one_model_does_not_affect_another(self):
        provider = self.provider(refuses(422, "this model does not support effort"), streams(pieces_of(TEXT)))
        self.organize(provider)
        ai.organize(provider.base, "key", "other-model", "Sort.", [], limits=FAST)
        self.assertIn("reasoning_effort", provider.seen[2])

    def test_an_unrelated_error_is_not_retried(self):
        provider = self.provider(refuses(401, "bad key"))
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider)
        self.assertIn("returned 401", str(caught.exception))
        self.assertEqual(len(provider.seen), 1)

    def test_a_server_that_answers_without_streaming_still_works(self):
        provider = self.provider(replies_with_json())
        self.assertEqual(self.organize(provider), PROPOSAL)
        self.assertEqual(len(provider.seen), 1)

    def test_a_server_that_refuses_streaming_is_asked_again_without_it(self):
        provider = self.provider(refuses(400, "stream is not supported"), replies_with_json())
        self.assertEqual(self.organize(provider), PROPOSAL)
        self.assertNotIn("stream", provider.seen[1])
        self.assertEqual(self.organize(provider), PROPOSAL)
        self.assertNotIn("stream", provider.seen[2])

    def test_a_plain_reply_that_is_slow_to_start_gets_the_same_silence_limit(self):
        def slow(handler):
            time.sleep(3)
            replies_with_json()(handler)

        provider = self.provider(slow)
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider, ai.Limits(first=0.6, between=0.3, cap=20.0))
        self.assertEqual(str(caught.exception), "The model did not answer for 1 second.")

    def test_an_error_in_the_middle_of_a_stream_is_reported(self):
        provider = self.provider(streams([*pieces_of(TEXT)[:1], sse({"error": {"message": "overloaded"}})]))
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider)
        self.assertIn("overloaded", str(caught.exception))

    def test_an_empty_answer_says_so(self):
        provider = self.provider(streams([piece("")]))
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider)
        self.assertEqual(str(caught.exception), "The model returned an empty reply.")

    def test_a_dropped_connection_says_so(self):
        def drops(handler):
            start_stream(handler)
            write(handler, pieces_of(TEXT)[0])
            handler.connection.close()

        provider = self.provider(drops)
        with self.assertRaises(RuntimeError) as caught:
            self.organize(provider)
        self.assertEqual(str(caught.exception), "The model's answer could not be read as a layout. Try again.")

    def test_cancel_stops_a_stream_at_once(self):
        provider = self.provider(goes_silent_after(pieces_of(TEXT)[:2]))
        cancel = threading.Event()
        threading.Timer(0.4, cancel.set).start()
        started = time.monotonic()
        with self.assertRaises(ai.Cancelled):
            self.organize(provider, cancel=cancel)
        self.assertLess(time.monotonic() - started, 3)

    def test_cancel_before_sending_sends_nothing(self):
        provider = self.provider(streams(pieces_of(TEXT)))
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(ai.Cancelled):
            self.organize(provider, cancel=cancel)
        self.assertEqual(provider.seen, [])

    def test_anthropic_is_streamed_and_gets_no_effort(self):
        events = [
            sse({"type": "message_start", "message": {"model": "m"}}),
            sse({"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "hm"}}),
            *[sse({"type": "content_block_delta", "delta": {"type": "text_delta", "text": TEXT[i:i + 10]}})
              for i in range(0, len(TEXT), 10)],
            sse({"type": "message_stop"}),
        ]
        provider = self.provider(streams(events, done=False))
        result = ai.organize(provider.base, "key", "m", "Sort.", [], adapter="anthropic", limits=FAST)
        self.assertEqual(result, PROPOSAL)
        sent = provider.seen[0]
        self.assertIs(sent["stream"], True)
        self.assertNotIn("reasoning_effort", sent)
        self.assertNotIn("response_format", sent)

    def test_anthropic_without_streaming_still_works(self):
        data = json.dumps({"content": [{"type": "text", "text": TEXT}], "model": "m"}).encode()

        def plain(handler):
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            write(handler, data)

        provider = self.provider(plain)
        self.assertEqual(ai.organize(provider.base, "key", "m", "Sort.", [], adapter="anthropic", limits=FAST), PROPOSAL)

    def test_listing_models_keeps_a_short_normal_timeout(self):
        class Reply:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"data":[{"id":"b"},{"id":"a"}]}'

        with patch("hearth.ai.urlopen", return_value=Reply()) as opened:
            self.assertEqual(ai.list_models("https://api.example.com/v1", "key"), ["a", "b"])
        self.assertEqual(opened.call_args.kwargs["timeout"], ai.LIST_TIMEOUT)
        self.assertLessEqual(ai.LIST_TIMEOUT, 60)

    def test_no_model_names_are_matched_anywhere(self):
        text = Path(ai.__file__).read_text(encoding="utf-8").lower()
        for name in ("gpt", "grok-", "claude", "gemini", "o3", "reasoner"):
            self.assertNotIn(name, text.replace("grok.com", "").replace("grok_sso", ""))


class OrganizeControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])
        cls._versions = tempfile.TemporaryDirectory()
        cls._patch = patch("hearth.device.version_dir", return_value=Path(cls._versions.name))
        cls._patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._patch.stop()
        cls._versions.cleanup()

    def setUp(self):
        with patch.object(drivers, "live_probe", return_value=READY):
            self.controller = Controller()
        self.addCleanup(self.controller.shutdown)
        self.controller._state = [[], [{"displayIdentifier": "a"}]]
        resolved = patch(
            "hearth.presets.resolve",
            return_value=({"base_url": "https://x.example/v1", "model": "m"}, {"adapter": ""}, "key", False),
        )
        resolved.start()
        self.addCleanup(resolved.stop)

    def fake_model(self, behave):
        patcher = patch("hearth.ai.organize", side_effect=behave)
        patcher.start()
        self.addCleanup(patcher.stop)

    def wait_for(self, condition, what):
        end = time.time() + 5
        while time.time() < end:
            QCoreApplication.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail(f"timed out waiting for {what}")

    def hangs_until_cancelled(self, late=None):
        def behave(*args, cancel=None, **kwargs):
            cancel.wait(5)
            if late:
                return late
            raise ai.Cancelled()
        self.fake_model(behave)

    def test_cancel_gives_the_app_back_at_once(self):
        self.hangs_until_cancelled()
        self.controller.propose("Sort.")
        self.assertTrue(self.controller.organizeWaiting)
        self.assertTrue(self.controller.busy)
        self.controller.cancelOrganize()
        self.assertFalse(self.controller.organizeWaiting)
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.controller._status, "Cancelled.")
        self.assertFalse(self.controller._error)

    def test_a_stopped_worker_cannot_post_a_result_or_an_error(self):
        self.hangs_until_cancelled(late=PROPOSAL)
        self.controller.propose("Sort.")
        job = self.controller._job
        self.controller.cancelOrganize()
        self.wait_for(lambda: not job.isRunning(), "the worker to stop")
        for _ in range(20):
            QCoreApplication.processEvents()
            time.sleep(0.01)
        self.assertFalse(self.controller.proposalReady)
        self.assertEqual(self.controller._status, "Cancelled.")
        self.assertEqual(self.controller._retired, [])

    def test_the_worker_is_told_to_stop_and_a_second_request_can_start(self):
        self.hangs_until_cancelled()
        self.controller.propose("Sort.")
        first = self.controller._job
        self.controller.cancelOrganize()
        self.assertTrue(first.cancel.is_set())
        self.controller.propose("Sort again.")
        self.assertIsNot(self.controller._job, first)
        self.assertTrue(self.controller.organizeWaiting)
        self.assertNotEqual(self.controller._status, "Wait for the current step to finish.")

    def test_a_finished_request_stops_waiting(self):
        self.fake_model(lambda *a, **k: dict(PROPOSAL))
        self.controller.propose("Sort.")
        self.wait_for(lambda: not self.controller.busy, "the request to finish")
        self.assertFalse(self.controller.organizeWaiting)
        self.assertEqual(self.controller.proposalSummary, PROPOSAL["summary"])

    def test_a_silent_model_shows_the_plain_message_and_frees_the_app(self):
        def silent(*a, **k):
            raise RuntimeError("The model did not answer for 3 minutes.")

        self.fake_model(silent)
        self.controller.propose("Sort.")
        self.wait_for(lambda: self.controller._error, "the error")
        self.wait_for(lambda: not self.controller.busy, "the app to be free")
        self.assertEqual(self.controller._status, "The model did not answer for 3 minutes.")
        self.assertFalse(self.controller.organizeWaiting)

    def test_cancel_does_nothing_when_nothing_is_waiting(self):
        self.controller.cancelOrganize()
        self.assertEqual(self.controller._status, "Plug in an iPhone or iPad.")

    def test_progress_reaches_the_status_line(self):
        def talks(*args, progress=None, cancel=None, **kwargs):
            progress("Asking the model… 40 characters")
            cancel.wait(0.3)
            return dict(PROPOSAL)

        self.fake_model(talks)
        self.controller.propose("Sort.")
        self.wait_for(lambda: self.controller._status.startswith("Asking the model… 40"), "progress")
        self.wait_for(lambda: not self.controller.busy, "the request to finish")

    def test_closing_the_window_stops_a_waiting_request(self):
        self.hangs_until_cancelled()
        self.controller.propose("Sort.")
        job = self.controller._job
        started = time.time()
        self.controller.shutdown()
        self.assertFalse(job.isRunning())
        self.assertLess(time.time() - started, 3)

    def test_the_button_turns_into_cancel_while_waiting(self):
        self.hangs_until_cancelled()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", self.controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        try:
            window = engine.rootObjects()[0]
            button = window.findChild(object, "organizeButton")
            self.assertEqual(button.property("text"), "Reorganize")
            self.controller.propose("Sort.")
            self.assertEqual(button.property("text"), "Cancel")
            self.assertTrue(button.property("enabled"))
            self.controller.cancelOrganize()
            self.assertEqual(button.property("text"), "Reorganize")
        finally:
            shiboken6.delete(engine)


if __name__ == "__main__":
    unittest.main()
