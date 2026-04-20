import time


def wait_until_enabled(button, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        if button.is_enabled():
            return
        time.sleep(0.3)
    raise Exception("Button did not become enabled")
