# z80_async_bus.py
import time
import pic18_link  # Import the constants


def do_cmd(pic, args, output=None, raise_on_error=False, timeout=1.0):
    """
    Sends a command to the PIC and manages the Async Protocol state machine.
    Normalizes the output so the calling script seamlessly receives 'OK' or 'OK <data>'.
    """
    resp = pic.handle_command(args)

    # 1. Check for immediate failures (NACK, syntax errors, etc.)
    if not resp.startswith(pic18_link.RES_OK):
        msg = f">> FAILED: cmd {args} response '{resp}'"
        if raise_on_error:
            if output: output(msg)
            pic.handle_command(["CLK", "OFF"])
            pic.handle_command(["GHOST", "1"])
            raise RuntimeError(msg)
        return resp

    # 2. If it's an immediate command (e.g., CLK SYNC -> OK), return instantly
    if not resp.startswith(pic18_link.RES_OK_QUEUED):
        return resp

    # 3. It is queued. Enter the HOST_WAITING polling state machine
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        status_resp = pic.handle_command(["STATUS"])

        # output(f"STATUS result: {status_resp}")

        # We use startswith() because DONE might have a data byte appended
        if status_resp.startswith(pic18_link.RES_OK_DONE):
            # Normalize "OK DONE 42" -> "OK 42" for legacy parser compatibility
            parts = status_resp.split()
            if len(parts) >= 3:
                return f"{pic18_link.RES_OK} {parts[2]}"
            return pic18_link.RES_OK

        elif status_resp.startswith(pic18_link.RES_OK_PENDING):
            time.sleep(0.010)

        elif status_resp.startswith(pic18_link.RES_OK_IDLE):
            msg = f">> FAILED: Queue unexpectedly went IDLE for cmd {args}"
            if raise_on_error:
                if output: output(msg)
                raise RuntimeError(msg)
            return "FAIL IDLE"
        else:
            if output:
                msg = f">> WARN: Unsupported STATUS response '{status_resp}'"
                output(msg)

    # 4. Timeout Fallback
    msg = f">> TIMEOUT waiting for async cmd {args} to complete"
    if raise_on_error:
        if output: output(msg)
        raise RuntimeError(msg)

    return "TIMEOUT"