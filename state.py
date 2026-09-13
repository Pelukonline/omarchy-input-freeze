"""Private state storage; the parent holds the lock for the entire Bash action."""

import fcntl
import os
import re
import secrets
import stat
import subprocess
import sys
import time

LOCK = "operation.lock"
DEVICES = "disabled-pointers"
FLAGS = os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def validate(fd, directory=False, migrate=False):
    info = os.fstat(fd)
    correct_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not correct_type or info.st_uid != os.getuid():
        raise ValueError("Unsafe state owner or file type")
    if not directory and info.st_nlink != 1:
        raise ValueError("State files must have exactly one hard link")
    if info.st_mode & 0o077:
        if not migrate:
            raise ValueError("State permissions must be private (0700 directory, 0600 files)")
        os.fchmod(fd, 0o700 if directory else 0o600)
    return info


def open_file(directory, name, create=False):
    flags = FLAGS | (os.O_RDWR if create else os.O_RDONLY)
    fd = os.open(name, flags | (os.O_CREAT if create else 0), 0o600, dir_fd=directory)
    try:
        validate(fd, migrate=True)
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_state(directory):
    try:
        fd = open_file(directory, DEVICES)
    except FileNotFoundError:
        return []
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError("State file is too large")
    names = data.splitlines()
    if any(not re.fullmatch(r"[A-Za-z0-9._:-]+", name) for name in names):
        raise ValueError("Invalid device name in state")
    return list(dict.fromkeys(names))


def write_state(directory, names):
    # Validate an existing target, but never open it for writing or truncation.
    read_state(directory)
    temporary = ".devices-" + secrets.token_hex(16)
    fd = os.open(temporary, FLAGS | os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("".join(name + "\n" for name in names))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, DEVICES, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def acquire_lock(fd):
    deadline = time.monotonic() + 5
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError("Input Freeze is busy; retry recovery shortly")
            time.sleep(0.05)


def run(helper, arguments):
    # All actions, including emergency recovery, share this directory lock.
    # It is independent of persistent state, and never unlinked/replaced.
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if not os.path.isabs(runtime):
        raise ValueError("XDG_RUNTIME_DIR must be absolute")
    parent = os.open(runtime, FLAGS | os.O_RDONLY | os.O_DIRECTORY)
    try:
        validate(parent, directory=True)
        try:
            os.mkdir("omarchy-input-freeze", 0o700, dir_fd=parent)
        except FileExistsError:
            pass
        coordinator = os.open("omarchy-input-freeze", FLAGS | os.O_RDONLY | os.O_DIRECTORY,
                              dir_fd=parent)
    finally:
        os.close(parent)
    try:
        validate(coordinator, directory=True)
        acquire_lock(coordinator)
        if arguments == ["recover"]:
            return subprocess.run(["bash", helper, "--state-session", "recover"],
                                  pass_fds=(coordinator,), check=False).returncode
        return run_with_state(helper, arguments, coordinator)
    finally:
        os.close(coordinator)


def run_with_state(helper, arguments, coordinator):
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    if not os.path.isabs(base):
        raise ValueError("XDG_STATE_HOME must be absolute")
    os.makedirs(base, mode=0o700, exist_ok=True)
    # The XDG base is user-configured; reject a symlink at its final component.
    base_fd = os.open(base, FLAGS | os.O_RDONLY | os.O_DIRECTORY)
    try:
        info = os.fstat(base_fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError("Unsafe XDG state directory")
        try:
            os.mkdir("omarchy-input-freeze", 0o700, dir_fd=base_fd)
        except FileExistsError:
            pass
        directory = os.open("omarchy-input-freeze", FLAGS | os.O_RDONLY | os.O_DIRECTORY,
                            dir_fd=base_fd)
    finally:
        os.close(base_fd)
    try:
        validate(directory, directory=True, migrate=True)
        lock = open_file(directory, LOCK, create=True)
        try:
            acquire_lock(lock)
            read_state(directory)
            env = dict(os.environ, INPUT_FREEZE_DIR_FD=str(directory),
                       INPUT_FREEZE_LOCK_FD=str(lock))
            return subprocess.run(["bash", helper, "--state-session", *arguments],
                                  env=env, pass_fds=(directory, lock, coordinator),
                                  check=False).returncode
        finally:
            os.close(lock)
    finally:
        os.close(directory)


def main():
    if sys.argv[1] == "run":
        return run(sys.argv[2], sys.argv[3:])
    directory = int(os.environ["INPUT_FREEZE_DIR_FD"])
    lock = int(os.environ["INPUT_FREEZE_LOCK_FD"])
    validate(directory, directory=True)
    info = validate(lock)
    current = os.stat(LOCK, dir_fd=directory, follow_symlinks=False)
    if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
        raise ValueError("State lock was replaced")
    names = read_state(directory)
    action = sys.argv[1]
    if action == "read":
        print("\n".join(names), end="\n" if names else "")
    elif action == "add":
        name = sys.argv[2]
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", name):
            raise ValueError("Invalid device name")
        if name not in names:
            write_state(directory, names + [name])
    elif action == "clear":
        write_state(directory, [])
    else:
        raise ValueError("Unknown state operation")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f"Input Freeze state error: {error}", file=sys.stderr)
        sys.exit(1)
