from __future__ import annotations

import logging

from fin_feast.logging import get_logger


def test_get_logger_respects_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logger = get_logger("test.logger")
    assert logger.level == logging.DEBUG


def test_get_logger_single_handler(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    name = "test.single"
    logger1 = get_logger(name)
    handler_count_1 = len(logger1.handlers)
    logger2 = get_logger(name)
    handler_count_2 = len(logger2.handlers)
    assert handler_count_1 == handler_count_2 == 1
