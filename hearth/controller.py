"""UI state. Phone and model calls run on a worker thread."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from threading import Event, Thread

from PySide6.QtCore import QObject, QThread, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication

from hearth import __version__, ai, device, drivers, grok_sso, icons, layout, presets, screens, settings, updates


class _Job(QThread):
    failed = Signal(str)
    progressed = Signal(str)
    pulled = Signal(object)
    icon_ready = Signal(str, str)
    missed = Signal(object)
    pushed = Signal(object)
    models_ready = Signal(object)
    proposed = Signal(object)
    grok_code = Signal(object)
    grok_finished = Signal(str)
    driver_done = Signal(str)

    def __init__(self, kind: str, cancel: Event, **payload):
        super().__init__()
        self.kind = kind
        self.cancel = cancel
        self.payload = payload

    def run(self):
        try:
            if self.kind == "pull":
                misses = asyncio.run(device.pull(
                    self.cancel,
                    lambda meta: self.pulled.emit(meta),
                    lambda ident, url: self.icon_ready.emit(ident, url),
                    lambda text: self.progressed.emit(text),
                ))
                self.missed.emit(misses)
            elif self.kind == "push":
                result = asyncio.run(device.push(self.payload["state"]))
                self.pushed.emit(result)
            elif self.kind == "models":
                config, preset, key, oauth = presets.resolve()
                found = ai.list_models(config["base_url"], key, adapter=preset["adapter"], oauth=oauth)
                self.models_ready.emit(found)
            elif self.kind == "propose":
                config, preset, key, oauth = presets.resolve()
                proposal = ai.organize(
                    config["base_url"],
                    key,
                    config["model"],
                    self.payload["instruction"],
                    self.payload["state"],
                    adapter=preset["adapter"],
                    oauth=oauth,
                )
                self.proposed.emit(proposal)
            elif self.kind == "grok":
                flow = grok_sso.start_device()
                self.grok_code.emit({
                    "user_code": flow.get("user_code") or "",
                    "verification_uri": flow.get("verification_uri") or "",
                    "verification_uri_complete": flow.get("verification_uri_complete") or "",
                })
                self.grok_finished.emit(grok_sso.poll(flow, self.cancel))
            elif self.kind == "driver":
                self.driver_done.emit(drivers.install())
        except Exception as exc:
            self.failed.emit(device.friendly(exc))


class _UpdateJob(QThread):
    """Asks for the newest version in the background. It never raises and never says why it failed."""

    found = Signal(str)

    def run(self):
        self.found.emit(updates.offer())


class Controller(QObject):
    layoutChanged = Signal()
    folderChanged = Signal()
    statusChanged = Signal()
    selectionChanged = Signal()
    settingsChanged = Signal()
    versionsChanged = Signal()
    proposalChanged = Signal()
    iconReady = Signal(str, str)
    iconRevChanged = Signal()
    grokChanged = Signal()
    busyChanged = Signal()
    driverChanged = Signal()
    linkChanged = Signal()
    updateChanged = Signal()
    scanned = Signal(int, str, bool)

    def __init__(self):
        super().__init__()
        self._state = [[], []]
        self._screen = screens.IPHONE
        layout.set_screen(self._screen)
        self._view = layout.build_view(self._state)
        self._open = None
        self._undo: list = []
        self._redo: list = []
        self._dirty = False
        self._busy = False
        self._status = "Plug in an iPhone or iPad."
        self._error = False
        self._device_name = ""
        self._model_name = ""
        self._ios = ""
        self._wallpaper = ""
        self._icons: dict[str, str] = {}
        self._icon_rev = 0
        self._selected = ""
        self._drag = ""
        self._config = settings.load()
        self._models: list[str] = []
        self._versions = device.list_versions()
        self._proposal = None
        self._proposal_lines: list[str] = []
        self._proposal_summary = ""
        self._proposal_base = None
        self._grok_code = ""
        self._grok_link = ""
        self._driver = drivers.status()
        self._driver_failed = False
        self._link = ""
        self._pending_link = ""
        self._pending_hits = 0
        self._scan_gen = 0
        self._cancel = Event()
        self._job: _Job | None = None
        self._update_state = updates.load_state()
        self._update_version = ""
        self._update_job: _UpdateJob | None = None
        self.scanned.connect(self._on_scanned)
        if self._driver.needed and not self._driver.ready:
            self._status = self._driver.headline
            self._error = True

    # --- properties -----------------------------------------------------

    def _layout(self):
        return self._view

    layoutView = Property("QVariant", _layout, notify=layoutChanged)

    def _folder(self):
        if self._open is None:
            return {}
        payload = layout.folder_payload(self._state, self._open)
        return payload or {}

    folder = Property("QVariant", _folder, notify=folderChanged)

    def _status_text(self):
        return self._status

    status = Property(str, _status_text, notify=statusChanged)

    def _is_error(self):
        return self._error

    error = Property(bool, _is_error, notify=statusChanged)

    def _is_busy(self):
        return self._busy

    busy = Property(bool, _is_busy, notify=busyChanged)

    def _is_dirty(self):
        return self._dirty

    dirty = Property(bool, _is_dirty, notify=layoutChanged)

    def _has_holes(self):
        return bool(self._state) and layout.has_holes(self._state)

    hasHoles = Property(bool, _has_holes, notify=layoutChanged)

    def _device(self):
        return self._device_name

    deviceName = Property(str, _device, notify=layoutChanged)

    def _link_label(self):
        if self._link == "many":
            return "More than one device"
        if self._link == "one":
            return "Device connected"
        return "Nothing connected yet"

    linkLabel = Property(str, _link_label, notify=linkChanged)

    def _link_detail(self):
        if self._device_name:
            return ""
        if self._link == "many":
            return "Unplug one."
        if self._link == "one":
            return "Found one device."
        return ""

    linkDetail = Property(str, _link_detail, notify=linkChanged)

    def _subtitle(self):
        bits = []
        if self._model_name:
            bits.append(self._model_name)
        if self._ios:
            os_name = "iPadOS" if self._screen.family == "ipad" else "iOS"
            bits.append(f"{os_name} {self._ios}")
        if self._screen.warning:
            bits.append("older model")
        return " · ".join(bits)

    subtitle = Property(str, _subtitle, notify=layoutChanged)

    def _driver_needed(self):
        return self._driver.needed and not self._driver.ready

    driverNeeded = Property(bool, _driver_needed, notify=driverChanged)

    def _driver_headline(self):
        return self._driver.headline

    driverHeadline = Property(str, _driver_headline, notify=driverChanged)

    def _driver_detail(self):
        return self._driver.detail

    driverDetail = Property(str, _driver_detail, notify=driverChanged)

    def _driver_action(self):
        return self._driver.action

    driverAction = Property(str, _driver_action, notify=driverChanged)

    def _driver_manual(self):
        """The same step as text, only after the button failed or when there is no button."""
        if self._driver_failed or self._driver.kind == "manual":
            return self._driver.manual
        return ""

    driverManual = Property(str, _driver_manual, notify=driverChanged)

    def _driver_url_action(self):
        return self._driver.url_action

    driverUrlAction = Property(str, _driver_url_action, notify=driverChanged)

    def _wall(self):
        return self._wallpaper

    wallpaper = Property(str, _wall, notify=layoutChanged)

    def _icon_rev_value(self):
        return self._icon_rev

    iconRev = Property(int, _icon_rev_value, notify=iconRevChanged)

    @Slot(str, result=str)
    def iconUrl(self, ident: str) -> str:
        return self._icons.get(ident or "", "")

    def _selected_text(self):
        return self._selected

    selected = Property(str, _selected_text, notify=selectionChanged)

    def _detail(self):
        if not self._selected:
            return "Select an icon"
        try:
            item = layout._object_at(self._state, self._selected)
        except (KeyError, IndexError, ValueError):
            return "Select an icon"
        name = layout.label(item)
        kind = layout.kind_of(item)
        if layout.is_folder(item):
            return f"{name}  ·  {len(layout.flatten_folder(item))} apps"
        extra = layout.ident(item)
        return f"{name}  ·  {kind}  ·  {extra}"

    detail = Property(str, _detail, notify=selectionChanged)

    def _base(self):
        return self._config["base_url"]

    baseUrl = Property(str, _base, notify=settingsChanged)

    def _model(self):
        return self._config["model"]

    model = Property(str, _model, notify=settingsChanged)

    def _provider(self):
        return self._config.get("provider") or "grok"

    provider = Property(str, _provider, notify=settingsChanged)

    def _preset_rows(self):
        return presets.PRESETS

    providerPresets = Property("QVariant", _preset_rows, constant=True)

    def _grok_signed_in(self):
        return grok_sso.signed_in()

    grokSignedIn = Property(bool, _grok_signed_in, notify=grokChanged)

    def _grok_code_text(self):
        return self._grok_code

    grokCode = Property(str, _grok_code_text, notify=grokChanged)

    def _key_hint(self):
        if self._provider() == "grok" and grok_sso.signed_in():
            return "Signed in to Grok. An API key is optional."
        preset = presets.by_id(self._provider())
        if not preset["needs_key"] and not preset["optional"]:
            return "No key needed."
        source = self._config.get("key_source")
        if source == "file":
            return "A key is saved on this computer."
        if source == "env":
            return "Using XAI_API_KEY from the environment."
        return "No key yet."

    keyHint = Property(str, _key_hint, notify=settingsChanged)

    def _has_key(self):
        return bool(self._config.get("has_key"))

    hasKey = Property(bool, _has_key, notify=settingsChanged)

    def _model_choices(self):
        choices = list(self._models)
        current = self._config["model"]
        if current and current not in choices:
            choices.insert(0, current)
        return choices

    modelChoices = Property("QVariant", _model_choices, notify=settingsChanged)

    def _version_rows(self):
        return self._versions

    versions = Property("QVariant", _version_rows, notify=versionsChanged)

    def _summary(self):
        return self._proposal_summary

    proposalSummary = Property(str, _summary, notify=proposalChanged)

    def _lines(self):
        return self._proposal_lines

    proposalLines = Property("QVariant", _lines, notify=proposalChanged)

    def _ready(self):
        return self._proposal is not None

    proposalReady = Property(bool, _ready, notify=proposalChanged)

    # --- updates --------------------------------------------------------

    def _update_available(self):
        return bool(self._update_version)

    updateAvailable = Property(bool, _update_available, notify=updateChanged)

    def _update_text(self):
        return self._update_version

    updateVersion = Property(str, _update_text, notify=updateChanged)

    def _app_version(self):
        return __version__

    appVersion = Property(str, _app_version, constant=True)

    def _check_updates(self):
        return bool(self._update_state.get("enabled", True))

    checkUpdates = Property(bool, _check_updates, notify=updateChanged)

    @Slot()
    def startUpdateCheck(self):
        """Once, at startup. Does nothing when the person turned the check off."""
        if self._update_job is not None or not self._check_updates():
            return
        job = _UpdateJob()
        job.found.connect(self._on_update_found)
        self._update_job = job
        job.start()

    def _on_update_found(self, version: str):
        if not self._check_updates():
            return
        self._update_version = version
        self.updateChanged.emit()

    @Slot(bool)
    def setCheckUpdates(self, enabled: bool):
        self._update_state = updates.set_enabled(enabled)
        if not enabled:
            self._update_version = ""
        self.updateChanged.emit()

    @Slot()
    def openUpdatePage(self):
        QDesktopServices.openUrl(QUrl(updates.DOWNLOAD_PAGE))
        self.dismissUpdate()

    @Slot()
    def dismissUpdate(self):
        """Not now. It comes back the next time Hearth starts."""
        self._update_version = ""
        self.updateChanged.emit()

    @Slot()
    def skipUpdate(self):
        if self._update_version:
            self._update_state = updates.skip(self._update_version)
        self.dismissUpdate()

    # --- editing --------------------------------------------------------

    @Slot(str)
    def beginDrag(self, source: str):
        self._drag = source

    @Slot(str, str)
    def move(self, source: str, target: str):
        if self._busy or not source or not target:
            return
        try:
            moved = layout._object_at(self._state, source)
        except (KeyError, IndexError, ValueError):
            moved = None
        before = layout.fingerprint(self._state)
        previous = deepcopy(self._state)
        error = layout.move(self._state, source, target)
        if error:
            self._set_status(error, True)
            return
        if layout.fingerprint(self._state) == before:
            return
        self._push_undo(previous)
        self._dirty = True
        if moved is not None:
            self._selected = layout.source_for(self._state, moved) or self._selected
        elif source.startswith("folder:") or source.startswith("dock:") or source.startswith("page:"):
            self._selected = source
        if self._open is not None and layout.find(self._state, self._open) is None:
            self._open = None
            self._selected = ""
        self._note_edit()

    @Slot(str)
    def select(self, source: str):
        self._selected = source
        self.selectionChanged.emit()

    @Slot(str)
    def openFolder(self, source: str):
        try:
            item = layout._object_at(self._state, source)
        except (KeyError, IndexError, ValueError):
            return
        if not layout.is_folder(item):
            return
        self._open = item
        self._selected = source
        self.folderChanged.emit()
        self.selectionChanged.emit()

    @Slot()
    def closeFolder(self):
        self._open = None
        self.folderChanged.emit()

    @Slot(str)
    def renameFolder(self, name: str):
        if self._open is None or self._busy:
            return
        previous = deepcopy(self._state)
        error = layout.rename_folder(self._state, self._folder_source(), name)
        if error:
            self._set_status(error, True)
            return
        self._push_undo(previous)
        self._dirty = True
        self._note_edit()

    @Slot()
    def addPage(self):
        if self._busy:
            return
        previous = deepcopy(self._state)
        layout.add_page(self._state)
        self._push_undo(previous)
        self._dirty = True
        self._note_edit()

    @Slot(int)
    def deletePage(self, index: int):
        if self._busy:
            return
        previous = deepcopy(self._state)
        error = layout.delete_page(self._state, index)
        if error:
            self._set_status(error, True)
            return
        self._push_undo(previous)
        self._dirty = True
        self._note_edit()

    @Slot()
    def undo(self):
        if self._busy or not self._undo:
            return
        self._redo.append(deepcopy(self._state))
        self._state = self._undo.pop()
        self._open = None
        self._dirty = True
        self._note_edit()

    @Slot()
    def redo(self):
        if self._busy or not self._redo:
            return
        self._undo.append(deepcopy(self._state))
        self._state = self._redo.pop()
        self._open = None
        self._dirty = True
        self._note_edit()

    # --- phone ----------------------------------------------------------

    @Slot()
    def checkDevice(self):
        """Background presence check. A newly seen single device is read."""
        self._start_scan(False)

    @Slot()
    def refreshDevice(self):
        """Look again, and only report. Does not replace the canvas."""
        self._start_scan(True)

    def _start_scan(self, manual: bool):
        if self._busy:
            return
        self._scan_gen += 1
        gen = self._scan_gen
        Thread(target=self._scan_thread, args=(gen, manual), daemon=True).start()

    def _scan_thread(self, gen: int, manual: bool):
        self.scanned.emit(gen, device.presence(), manual)

    @Slot(int, str, bool)
    def _on_scanned(self, gen: int, kind: str, manual: bool):
        if gen != self._scan_gen:
            return
        if manual:
            self._apply_link(kind, read=False)
            if kind == "one":
                self._set_status("One device is connected.", False)
            elif kind == "many":
                self._set_status("More than one device is connected. Unplug one.", True)
            else:
                self._set_status("No device is connected.", True)
            return
        if kind == self._link:
            self._pending_link = ""
            self._pending_hits = 0
            return
        if kind != self._pending_link:
            self._pending_link = kind
            self._pending_hits = 0
        self._pending_hits += 1
        # A device shows up on the first sighting. A dropout has to repeat, so a
        # one-off usbmux miss does not read the phone a second time.
        needed = 1 if kind == "one" else 2
        if self._pending_hits < needed:
            return
        self._pending_link = ""
        self._pending_hits = 0
        previous = self._link
        self._apply_link(kind, read=kind == "one" and previous != "one" and not self._dirty)

    def _apply_link(self, kind: str, read: bool):
        self._link = kind
        self.linkChanged.emit()
        if read and not self._busy:
            self.pull()

    @Slot()
    def installDriver(self):
        report = drivers.status()
        self._driver = report
        self.driverChanged.emit()
        if not report.needed or report.ready:
            self._set_status("USB support is already in place.", False)
            return
        if report.url and not report.command:
            QDesktopServices.openUrl(QUrl(report.url))
            self._set_status("Opened the Apple Devices page. Come back when it has finished.", False)
            return
        if not report.command:
            self._set_status(report.detail, True)
            return
        self._start(_Job("driver", self._cancel))

    @Slot()
    def openDriverPage(self):
        url = self._driver.url
        if url:
            QDesktopServices.openUrl(QUrl(url))
            self._set_status("Opened the Apple Devices page. Come back when it has finished.", False)

    @Slot()
    def pull(self):
        self._start(_Job("pull", self._cancel))

    @Slot()
    def push(self):
        if not self._state or self._busy:
            return
        outgoing = deepcopy(self._state)
        layout.strip_positions(outgoing)
        layout.strip_empty_pages(outgoing)
        for index, page in enumerate(outgoing[1:], start=1):
            if not layout.page_fits(page):
                self._set_status(f"Page {index} does not fit on the phone. Move something off it.", True)
                return
        self._start(_Job("push", self._cancel, state=outgoing))

    @Slot(str)
    def loadVersion(self, path: str):
        if self._busy:
            return
        try:
            state = device.load_version(path)
        except (OSError, Exception) as exc:
            self._set_status(device.friendly(exc), True)
            return
        if not isinstance(state, list) or not state:
            self._set_status("That version is empty.", True)
            return
        dock_count = len(state[0]) if isinstance(state[0], list) else 0
        self._use_screen(screens.from_note(device.load_note(path)), dock_count)
        self._replace_state(state, dirty=True)
        self._restore_icons(state)
        self._set_status("Opened a saved version. Send to Device writes it.", False)

    # --- settings and organizer -----------------------------------------

    @Slot(str, str, str, str, bool)
    def saveSettings(self, provider: str, base: str, key: str, model: str, forget: bool):
        self._config = settings.save(
            base,
            model,
            key if key.strip() else None,
            forget_key=forget,
            provider=provider or "grok",
        )
        self.settingsChanged.emit()
        self._set_status("LLM settings saved.", False)

    @Slot()
    def refreshModels(self):
        self._start(_Job("models", self._cancel))

    @Slot()
    def startGrokSignIn(self):
        self._grok_code = ""
        self._grok_link = ""
        self.grokChanged.emit()
        self._start(_Job("grok", self._cancel))

    @Slot()
    def signOutGrok(self):
        grok_sso.sign_out()
        self._grok_code = ""
        self._grok_link = ""
        self.grokChanged.emit()
        self.settingsChanged.emit()
        self._set_status("Signed out of Grok.", False)

    @Slot(str)
    def propose(self, instruction: str):
        if not self._state or not any(self._state[1:]):
            self._set_status("Read a home screen first.", True)
            return
        self._start(_Job(
            "propose",
            self._cancel,
            instruction=instruction,
            state=deepcopy(self._state),
        ))

    @Slot()
    def applyProposal(self):
        if not self._proposal or self._proposal_base is None:
            return
        rebuilt, error = layout.apply_proposal(self._proposal_base, self._proposal)
        if error or rebuilt is None:
            self._set_status(error or "Could not apply that layout.", True)
            return
        lines = layout.change_summary(self._state, rebuilt)
        previous = deepcopy(self._state)
        self._state = rebuilt
        self._push_undo(previous)
        self._dirty = True
        self._proposal = None
        self._proposal_base = None
        self._proposal_lines = lines
        self._open = None
        self.proposalChanged.emit()
        self._note_edit()
        self._set_status("Applied on the canvas. Send to Device writes it.", False)

    @Slot()
    def discardProposal(self):
        self._proposal = None
        self._proposal_base = None
        self._proposal_summary = ""
        self._proposal_lines = []
        self.proposalChanged.emit()

    @Slot()
    def shutdown(self):
        self._cancel.set()
        if self._job is not None and self._job.isRunning():
            self._job.wait(4000)
        if self._update_job is not None and self._update_job.isRunning():
            self._update_job.wait(updates.TIMEOUT_SECONDS * 1000 + 1000)

    # --- internals ------------------------------------------------------

    def _folder_source(self) -> str:
        found = layout.find(self._state, self._open)
        if not found or found[0] != "page":
            return ""
        return f"page:{found[1]}:{found[2]}"

    def _push_undo(self, previous):
        self._undo.append(previous)
        if len(self._undo) > 50:
            self._undo.pop(0)
        self._redo.clear()

    def _note_edit(self):
        self._rebuild()
        self._set_status("Edited on the canvas. Send to Device writes it.", False)

    def _replace_state(self, state, dirty: bool):
        self._state = state
        self._open = None
        self._undo.clear()
        self._redo.clear()
        self._dirty = dirty
        self._selected = ""
        self._rebuild()
        self.selectionChanged.emit()

    def _use_screen(self, screen, dock_count: int):
        self._screen = screens.with_dock(screen, dock_count)
        layout.set_screen(self._screen)

    def _rebuild(self):
        self._view = layout.build_view(self._state)
        self.layoutChanged.emit()
        self.folderChanged.emit()

    def _set_status(self, text: str, is_error: bool):
        self._status = text
        self._error = is_error
        self.statusChanged.emit()

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.busyChanged.emit()

    def _start(self, job: _Job):
        if self._job is not None and self._job.isRunning():
            self._set_status("Wait for the current step to finish.", True)
            return
        self._cancel.clear()
        self._job = job
        job.failed.connect(self._on_failed)
        job.progressed.connect(lambda text: self._set_status(text, False))
        job.pulled.connect(self._on_pulled)
        job.icon_ready.connect(self._on_icon)
        job.missed.connect(self._on_missed)
        job.pushed.connect(self._on_pushed)
        job.models_ready.connect(self._on_models)
        job.proposed.connect(self._on_proposed)
        job.grok_code.connect(self._on_grok_code)
        job.grok_finished.connect(self._on_grok_finished)
        job.driver_done.connect(self._on_driver)
        job.finished.connect(lambda: self._set_busy(False))
        self._set_busy(True)
        if job.kind == "pull":
            self._set_status("Reading the device…", False)
        elif job.kind == "push":
            self._set_status("Sending the layout…", False)
        elif job.kind == "propose":
            self._set_status("Asking the model…", False)
        elif job.kind == "grok":
            self._set_status("Starting Grok sign-in…", False)
        elif job.kind == "driver":
            self._set_status("Installing USB support…", False)
        job.start()

    def _on_failed(self, text: str):
        self._grok_code = ""
        self._grok_link = ""
        self.grokChanged.emit()
        was_driver = self._job is not None and self._job.kind == "driver"
        self._remember_driver()
        if was_driver and self._driver_needed():
            self._driver_failed = True
            self.driverChanged.emit()
        self._set_status(text, True)

    def _on_driver(self, text: str):
        self._remember_driver()
        ready = self._driver.ready or not self._driver.needed
        self._driver_failed = not ready
        self.driverChanged.emit()
        self._set_status(text, not ready)

    def _remember_driver(self):
        self._driver = drivers.status()
        if not self._driver_needed():
            self._driver_failed = False
        self.driverChanged.emit()

    @Slot()
    def copyDriverManual(self):
        text = self._driver_manual()
        if text:
            QGuiApplication.clipboard().setText(text)
            self._set_status("Copied.", False)

    def _on_pulled(self, meta: dict):
        state = meta.get("state")
        if not isinstance(state, list) or not state:
            self._set_status("The device returned an empty layout.", True)
            return
        self._device_name = str(meta.get("name") or "iPhone")
        self._model_name = str(meta.get("model") or "")
        self._ios = str(meta.get("ios") or "")
        self._wallpaper = str(meta.get("wallpaper") or "")
        dock_count = len(state[0]) if isinstance(state[0], list) else 0
        chosen = screens.for_device(str(meta.get("product") or ""), str(meta.get("deviceClass") or ""))
        self._use_screen(chosen, dock_count)
        self._replace_state(state, dirty=False)
        device.save_version(state, "read", self._device_name, self._screen)
        self._versions = device.list_versions()
        self.versionsChanged.emit()
        count = len(layout.idents(state))
        message = f"Read {count} icons."
        if self._screen.warning:
            message = f"{self._screen.warning} {message}"
        self._set_status(message, False)

    def _restore_icons(self, state):
        """The icon map starts empty on each launch. Fill it from the cache on disk."""
        found, _ = device.restore_icons(state)
        changed = False
        for ident, url in found.items():
            if self._icons.get(ident) != url:
                self._icons[ident] = url
                changed = True
        if changed:
            self._icon_rev += 1
            self.iconRevChanged.emit()

    def _remember_icon(self, ident: str, url: str):
        if not ident or not url or self._icons.get(ident) == url:
            return
        self._icons[ident] = url
        self._icon_rev += 1
        self.iconRevChanged.emit()

    def _on_icon(self, ident: str, url: str):
        self._remember_icon(ident, url)

    def _on_missed(self, payload):
        if isinstance(payload, dict):
            misses = payload.get("misses") or []
            phone = int(payload.get("phone") or 0)
            store = int(payload.get("store") or 0)
        else:
            misses = list(payload or [])
            phone = 0
            store = 0
        for job in misses:
            url = icons.generate(job["ident"], job["letter"], job["kind"])
            self._remember_icon(job["ident"], url)
        parts = []
        if phone:
            parts.append(f"{phone} from the phone")
        if store:
            parts.append(f"{store} from the App Store")
        if misses:
            parts.append(f"{len(misses)} placeholders")
        if parts:
            self._set_status("Icons: " + ", ".join(parts) + ".", False)

    def _on_pushed(self, result: dict):
        device.save_version(result["previous"], "before-send", self._device_name, self._screen)
        state = result["state"]
        if isinstance(state, list) and state and isinstance(state[0], list):
            self._use_screen(self._screen, len(state[0]))
        self._replace_state(state, dirty=False)
        device.save_version(result["state"], "sent", self._device_name, self._screen)
        self._versions = device.list_versions()
        self.versionsChanged.emit()
        self._set_status("The phone is showing this layout.", False)

    def _on_grok_code(self, info: dict):
        self._grok_code = str(info.get("user_code") or "")
        link = str(info.get("verification_uri_complete") or info.get("verification_uri") or "")
        self._grok_link = link
        self.grokChanged.emit()
        if link.startswith("https://"):
            QDesktopServices.openUrl(QUrl(link))
        self._set_status("Enter the code in the browser to finish Grok sign-in.", False)

    def _on_grok_finished(self, result: str):
        self._grok_code = ""
        self._grok_link = ""
        self.grokChanged.emit()
        self.settingsChanged.emit()
        if result == "ok":
            self._set_status("Signed in to Grok.", False)
        elif result == "cancelled" and self._status != "Signed out of Grok.":
            self._set_status("Grok sign-in cancelled.", False)

    def _on_models(self, found: list):
        self._models = list(found)
        self.settingsChanged.emit()
        self._set_status(f"{len(found)} models.", False)

    def _on_proposed(self, proposal: dict):
        summary = str(proposal.get("summary") or "Proposed a new arrangement.")
        preview, error = layout.apply_proposal(self._state, proposal)
        if error or preview is None:
            self._proposal = None
            self._proposal_base = None
            self._proposal_summary = summary
            self._proposal_lines = [error or "Could not read that layout."]
            self.proposalChanged.emit()
            self._set_status(error or "The model’s layout could not be used.", True)
            return
        self._proposal = proposal
        self._proposal_base = deepcopy(self._state)
        self._proposal_summary = summary
        self._proposal_lines = layout.change_summary(self._state, preview) or ["No visible moves."]
        self.proposalChanged.emit()
        self._set_status("Review the proposal. Applying it stays on the canvas.", False)
