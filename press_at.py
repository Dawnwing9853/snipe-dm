"""Press the real Enter key at an exact GMT+7 time, into the front window (must be Edge).

Usage: python press_at.py TIME [--early MS]
  TIME: 00.00, 0:00, 23:05, 23:05:30 ... (GMT+7, next occurrence)
  --early MS: press this many ms early (default: measured one-way delay to Messenger; 0 = never early)
"""
import argparse, ctypes, datetime as dt, socket, struct, time

TZ7 = dt.timezone(dt.timedelta(hours=7))
CHAT_HOST = "edge-chat.messenger.com"
user32 = ctypes.windll.user32


def parse_time(s):
    """'00.00' / '0:00' / '23:05:30' -> 'HH:MM:SS'."""
    parts = [int(p) for p in s.replace(".", ":").split(":")]
    parts += [0] * (3 - len(parts))
    return dt.time(*parts[:3]).isoformat()


def ntp_offset(host="time.google.com"):
    """Seconds to add to the local clock to get real time. 0 if NTP is unreachable."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            t0 = time.time()
            s.sendto(b"\x1b" + 47 * b"\0", (host, 123))
            data = s.recv(48)
            t1 = time.time()
        secs, frac = struct.unpack("!II", data[40:48])
        return secs - 2208988800 + frac / 2**32 - (t0 + t1) / 2
    except OSError as e:
        print(f"NTP failed ({e}); using local clock")
        return 0.0


def one_way_ms(host=CHAT_HOST, n=7):
    """Half the best TCP connect time to the chat server = one-way network delay."""
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        print(f"Can't resolve {host} ({e}); delay 0")
        return 0.0
    rtts = []
    for _ in range(n):
        try:
            t0 = time.perf_counter()
            socket.create_connection((ip, 443), timeout=3).close()
            rtts.append((time.perf_counter() - t0) * 1000)
        except OSError:
            pass
    return min(rtts) / 2 if rtts else 0.0


def next_target(hms, now):
    t = dt.datetime.combine(now.date(), dt.time.fromisoformat(hms), TZ7)
    return t if t > now else t + dt.timedelta(days=1)


def front_title():
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(user32.GetForegroundWindow(), buf, 512)
    return buf.value


CHAT_SITES = ("Facebook", "Messenger", "Instagram")


def chat_host(title):
    """Chat server for the active tab, to measure network delay against."""
    return "edge-chat.instagram.com" if "Instagram" in title else CHAT_HOST


def window_problem(title):
    """None if the front window is Edge showing a chat site tab, else why not.
    Edge's window title starts with the active tab's title."""
    if "Edge" not in title:
        return f"front window is not Edge ({title!r})"
    tab = title.split(" and ")[0].split(" - ")[0]
    if not any(s in tab for s in CHAT_SITES):
        return f"active Edge tab is not Facebook/Messenger/Instagram ({tab!r})"
    return None


def press_enter():
    user32.keybd_event(0x0D, 0, 0, 0)
    user32.keybd_event(0x0D, 0, 2, 0)


class _KI(ctypes.Structure):
    _fields_ = [("vk", ctypes.c_ushort), ("scan", ctypes.c_ushort), ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("extra", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("ki", _KI), ("pad", ctypes.c_byte * 32)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def _key(vk=0, scan=0, flags=0):
    return _INPUT(1, _U(ki=_KI(vk, scan, flags, 0, 0)))


def _send(events):
    arr = (_INPUT * len(events))(*events)
    return user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))


def type_text(text):
    """Select all in the focused box, then type text as Unicode (Thai OK, any keyboard layout).
    Newlines become Shift+Enter so they don't send."""
    ev = [_key(0x11), _key(0x41), _key(0x41, flags=2), _key(0x11, flags=2)]  # Ctrl+A
    raw = text.replace("\r", "").encode("utf-16-le")
    for u in struct.unpack(f"<{len(raw) // 2}H", raw):
        if u == 10:
            ev += [_key(0x10), _key(0x0D), _key(0x0D, flags=2), _key(0x10, flags=2)]
        else:
            ev += [_key(scan=u, flags=4), _key(scan=u, flags=6)]  # KEYEVENTF_UNICODE (+KEYUP)
    return _send(ev) == len(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("at")
    ap.add_argument("--early", type=float, default=None)
    ap.add_argument("--msg-file", help="UTF-8 file with the message; typed 10 s before the time")
    args = ap.parse_args()
    msg = open(args.msg_file, encoding="utf-8-sig").read().strip() if args.msg_file else None
    if msg:
        print(f"Message: {msg}")

    offset = ntp_offset()
    now7 = dt.datetime.fromtimestamp(time.time() + offset, TZ7)
    target = next_target(parse_time(args.at), now7)
    print(f"Now {now7:%H:%M:%S} GMT+7. Target {target:%Y-%m-%d %H:%M:%S} GMT+7 "
          f"({(target - now7).total_seconds() / 60:.1f} min away).")
    print("Click inside the chat box in Edge and leave Edge in front. Don't touch the PC.")

    while (left := target.timestamp() - offset - 15 - time.time()) > 0:
        time.sleep(min(left, 30))
    offset = ntp_offset()
    host = chat_host(front_title())
    early = args.early if args.early is not None else one_way_ms(host)
    fire = target.timestamp() - offset - early / 1000
    print(f"Clock offset {offset*1000:+.0f} ms, delay to {host} -> pressing {early:.0f} ms early.")

    if msg:
        while (left := fire - 10 - time.time()) > 0:
            time.sleep(left)
        title = front_title()
        if why := window_problem(title):
            raise SystemExit(f"Stopped: {why}. Nothing typed or pressed.")
        if not type_text(msg):
            raise SystemExit("Typing was blocked by Windows. Nothing pressed.")
        print("Message typed.")

    while (left := fire - time.time()) > 1:
        time.sleep(left - 1)
    title = front_title()
    if why := window_problem(title):
        raise SystemExit(f"Stopped: {why}. Nothing pressed.")
    while time.time() < fire:
        pass
    press_enter()
    pressed = dt.datetime.fromtimestamp(time.time() + offset, TZ7)
    arrive = pressed + dt.timedelta(milliseconds=early)
    print(f"Enter pressed {pressed:%H:%M:%S.%f}"[:-3] + f" GMT+7, est. arrival {arrive:%H:%M:%S.%f}"[:-3]
          + f" into: {title}")


if __name__ == "__main__":
    main()
