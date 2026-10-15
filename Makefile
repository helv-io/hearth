PYTHON ?= .venv/bin/python
export QT_QPA_PLATFORM ?= offscreen

.PHONY: test
test:
	$(PYTHON) -m unittest discover -s tests -q
