"""Own one dashboard and one log-only worker in the launcher's console."""

import logging
from pathlib import Path
import signal
import subprocess
import sys
import time


logger = logging.getLogger("dashboard_supervisor")
SHUTDOWN_TIMEOUT = 5


def stop_children(children):
    success = True
    for child in children:
        try:
            if child.poll() is None:
                child.terminate()
        except OSError as error:
            if child.poll() is None:
                logger.error("Child termination failed (%s)", type(error).__name__)
                success = False

    for child in children:
        try:
            try:
                child.wait(timeout=SHUTDOWN_TIMEOUT)
            except subprocess.TimeoutExpired:
                try:
                    child.kill()
                except OSError:
                    if child.poll() is None:
                        raise
                child.wait(timeout=SHUTDOWN_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as error:
            logger.error("Child cleanup failed (%s)", type(error).__name__)
            success = False
    return success


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    children = []
    previous_handlers = {}
    stop_signal = None
    exit_code = 1

    def request_stop(signum, frame):
        nonlocal stop_signal
        if stop_signal is None:
            stop_signal = signum

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, request_stop)
        backend = Path(__file__).resolve().parent
        for script in ("app.py", "monitor_worker.py"):
            if stop_signal is not None:
                break
            child = subprocess.Popen(
                [sys.executable, "-u", str(backend / script)],
                cwd=backend,
            )
            children.append(child)
            logger.info("Started %s (pid=%s)", script, child.pid)

        while stop_signal is None:
            for child in children:
                return_code = child.poll()
                if return_code is not None:
                    logger.error("Child pid=%s exited unexpectedly (code=%s)", child.pid, return_code)
                    break
            else:
                time.sleep(0.2)
                continue
            break
    except KeyboardInterrupt:
        stop_signal = signal.SIGINT
    except OSError as error:
        logger.error("Could not launch dashboard processes (%s)", type(error).__name__)
    finally:
        cleaned_up = stop_children(children)
        if stop_signal is not None and cleaned_up:
            exit_code = 128 + stop_signal
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())