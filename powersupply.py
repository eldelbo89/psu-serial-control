"""
psu-serial-control

Author: eldelbo89

This code controls and monitors a programmable bench power supply over
a serial (UART) interface.

It was written and tested specifically for the RND 320-KWR103 power supply.
The software sends raw serial commands directly to the device.

DISCLAIMER:
Use of this code on any device, tested or untested, is entirely at your
own risk. The author assumes no responsibility for damage, malfunction,
or any consequences resulting from its use.

This project is shared to spread knowledge and inspire others.
"""

import serial
import argparse
import sys
import time
import socket
import threading
import os

SOCKET_PATH = "/tmp/powersupply.sock"

DEF_PORT = "/dev/ttyACM0"
DEF_BAUD = 9600
DEF_TIMEOUT = 1
DEF_REFRESH = 1
TESTED_DEVICES = [
    "RND 320-KWR103",
]

RAW_COMMANDS = [
    "VSET:<voltage>",
    "VSET?",
    "ISET:<current>",
    "ISET?",
    "VOUT?",
    "IOUT?",
    "OUT:<stat>",
    "LOCK:<stat>",
    "SAV:<slot>",
    "RCL:<slot>",
    "*IDN?",
]


class PowerSupply:
    def __init__(
        self,
        refreshrate=DEF_REFRESH,
        port=DEF_PORT,
        baudrate=DEF_BAUD,
        timeout=DEF_TIMEOUT,
        no_device_check=False,
    ):

        self.refreshrate = refreshrate
        self.is_connected = False
        self.socket_path = SOCKET_PATH

        try:
            self.connection = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
            )
            self.is_connected = True
            self.connection.reset_input_buffer()
            self.no_device_check = no_device_check
            self.confirmation_cached = False

        except Exception as e:
            print(f"{port} failure: {e}")
            raise

    def user_enter_button(self):
        try:
            input("\nPress Enter...")
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)

    def print_help(self):
        print(
            """
    Power Supply Controller
    =======================

    Control and monitor a programmable power supply over a serial interface.
    Supports live monitoring and safe multi-process access via a UNIX socket.

    -----------------------------------------------------------------------
    SAFETY WARNING
    -----------------------------------------------------------------------

    This program sends RAW serial commands directly to the device.

    It does NOT identify the device automatically.
    It does NOT verify compatibility.

    The program has ONLY been tested on the following devices:
    """
        )
        for dev in TESTED_DEVICES:
            print(f"  - {dev}")
        self.user_enter_button()
        print(
            """
    Using this program with any other device may be unsafe.
    Always consult your device manual before use.

    By default, the program will ask for confirmation before executing
    ANY command.

    To bypass this confirmation, use:
    --no-device-check
    """
        )
        self.user_enter_button()
        print(
            """
    -----------------------------------------------------------------------
    MONITOR MODE
    -----------------------------------------------------------------------

    Start live dashboard and background control server:

    powersupply.py --monitor

    While running, other terminals can safely issue commands.
    Confirmation is requested once at startup.

    -----------------------------------------------------------------------
    RAW SERIAL COMMANDS USED
    -----------------------------------------------------------------------
    """
        )

        for cmd in RAW_COMMANDS:
            print(f"  {cmd}")

        print(
            """
    Compare these commands with your device manual to ensure compatibility."""
        )
        self.user_enter_button()
        print(
            """
    -----------------------------------------------------------------------
    OPTIONS
    -----------------------------------------------------------------------

    --monitor              Start live dashboard and socket server
    --get-voltage-set      Read configured voltage
    --get-voltage-out      Read output voltage
    --get-current-set      Read configured current
    --get-current-out      Read output current
    --set-voltage <v>      Set output voltage
    --set-current <i>      Set output current
    --on                   Enable output
    --off                  Disable output
    --lock                 Lock front panel
    --unlock               Unlock front panel
    --save <n>             Save settings to memory slot
    --load <n>             Recall memory slot
    --idn                  Send *IDN? explicitly
    --no-device-check      Skip safety confirmation (UNSAFE)

    -----------------------------------------------------------------------
    EXAMPLES
    -----------------------------------------------------------------------

    powersupply.py --monitor
    powersupply.py --set-voltage 12.5
    powersupply.py --set-current 2.0
    powersupply.py --on

    -----------------------------------------------------------------------
    """
        )

    def _user_confirmation(self):
        if self.no_device_check:
            return True

        print("\nWARNING:")
        print("This program sends raw serial commands to a power supply.")
        print("It has ONLY been tested on the following devices:\n")

        for dev in TESTED_DEVICES:
            print(f"  - {dev}")

        print("\nUsing it with any other device may be unsafe.")
        print("Check your device manual before continuing.\n")

        print("If you are sure you want to continue, type: confirm")
        user_input = input("> ").strip()

        if user_input != "confirm":
            print("Aborted.")
            return False

        print("\nConfirmed.")
        print("Tip: to skip this confirmation in the future, use --no-device-check\n")
        return True

    def _serial_command(self, data):
        if not self.is_connected:
            return None
        self.connection.write((data + "\r\n").encode())
        reply = self.connection.readline().decode(errors="ignore").strip()
        return reply if reply else None

    def _check_server(self):
        """Try to connect to the UNIX socket server."""
        socket_path = self.socket_path
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(socket_path)
            return client
        except FileNotFoundError:
            return None
        except ConnectionRefusedError:
            return None

    def send_command_via_socket(self, cmd):
        client = self._check_server()
        if client is None:
            return None
        client.sendall((cmd + "\n").encode())
        data = client.recv(4096).decode(errors="ignore").strip()
        client.close()
        return data

    def start_server(self):
        """Starts UNIX domain socket server for remote control."""
        socket_path = self.socket_path
        try:
            if os.path.exists(socket_path):
                os.unlink(socket_path)
        except OSError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(socket_path)
        server.listen(1)
        self._server_socket = server

        self._server_thread = threading.Thread(
            target=self._serve_clients, args=(server, socket_path), daemon=True
        )
        self._server_thread.start()

    def _serve_clients(self, server, socket_path):
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                break

            with conn:
                try:
                    data = conn.recv(1024)
                    if not data:
                        continue

                    cmd = data.decode(errors="ignore").strip()
                    reply = self._serial_command(cmd)

                    if reply is None:
                        conn.sendall(b"\n")
                    else:
                        conn.sendall((reply + "\n").encode())

                except Exception as e:
                    err_msg = f"ERROR: {e}\n"
                    conn.sendall(err_msg.encode())

        try:
            server.close()
        except:
            pass
        try:
            if os.path.exists(socket_path):
                os.unlink(socket_path)
        except:
            pass

    def _execute_psu_command(self, cmd):
        if not self.confirmation_cached:
            if self._user_confirmation():
                return None
            self.confirmation_cached = True

        reply = self.send_command_via_socket(cmd)
        if reply is None:
            return self._serial_command(cmd)
        return reply

    def set_current(self, amps):
        cmd = f"ISET:{amps}"
        return self._execute_psu_command(cmd)

    def set_voltage(self, volts):
        cmd = f"VSET:{volts}"
        return self._execute_psu_command(cmd)

    def get_voltage_set(self):
        cmd = "VSET?"
        return self._execute_psu_command(cmd)

    def get_voltage_out(self):
        cmd = "VOUT?"
        return self._execute_psu_command(cmd)

    def get_current_set(self):
        cmd = "ISET?"
        return self._execute_psu_command(cmd)

    def get_current_out(self):
        cmd = "IOUT?"
        return self._execute_psu_command(cmd)

    def get_idn(self):
        cmd = f"*IDN?"
        return self._execute_psu_command(cmd)

    def get_all(self):
        print("Voltage set :", self.get_voltage_set())
        self.confirmation_cached = True
        print("Voltage out :", self.get_voltage_out())
        print("Current set :", self.get_current_set())
        print("Current out :", self.get_current_out())

    def output_on(self):
        cmd = f"OUT:1"
        return self._execute_psu_command(cmd)

    def output_off(self):
        cmd = f"OUT:0"
        return self._execute_psu_command(cmd)

    def lock_front_panel(self):
        cmd = f"LOCK:1"
        return self._execute_psu_command(cmd)

    def unlock_front_panel(self):
        cmd = f"LOCK:0"
        return self._execute_psu_command(cmd)

    def save_preset(self, slot):
        cmd = f"SAV:{slot}"
        return self._execute_psu_command(cmd)

    def recall_preset(self, slot):
        cmd = f"RCL:{slot}"
        return self._execute_psu_command(cmd)

    def monitor(self):
        if not self._user_confirmation():
            return
        self.confirmation_cached = True
        self.start_server()

        try:
            while True:
                vset = self.get_voltage_set() or "?"
                iset = self.get_current_set() or "?"
                vout = self.get_voltage_out() or "?"
                iout = self.get_current_out() or "?"

                output_state = (
                    "ON" if vout not in ("0", "0.0", "0.00", "00.000", None) else "OFF"
                )
                mem_slot = "-"

                print("\033[2J\033[H", end="")
                print(
                    "================================= PSU ================================="
                )
                print(f"  VSET: {vset:<8} V                          VOUT: {vout:<8} V")
                print(
                    f"  ISET: {iset:<8} A                          IOUT: {iout:<8} A\n"
                )
                print(
                    f"                   OUTPUT: {output_state:<3}      MEM: {mem_slot}"
                )
                print(
                    "======================================================================="
                )
                print(
                    f"Refreshing every {self.refreshrate} seconds...  (Ctrl+C to stop)\n"
                )

                time.sleep(self.refreshrate)

        except KeyboardInterrupt:
            print("\nStopping monitor...")
            self.closeConnection()
            print("Serial connection closed.")

    def closeConnection(self):
        try:
            self.connection.close()
        finally:
            self.is_connected = False


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(
        description="Power supply controller", add_help=False
    )

    PARSER.add_argument("--get-all", "-a", action="store_true")
    PARSER.add_argument("--get-voltage-set", action="store_true")
    PARSER.add_argument("--get-voltage-out", action="store_true")
    PARSER.add_argument("--get-current-set", action="store_true")
    PARSER.add_argument("--get-current-out", action="store_true")

    PARSER.add_argument("--set-voltage", "-v", type=str)
    PARSER.add_argument("--set-current", "-i", type=str)

    PARSER.add_argument("--on", "-o", action="store_true")
    PARSER.add_argument("--off", "-f", action="store_true")

    PARSER.add_argument("--lock", "-l", action="store_true")
    PARSER.add_argument("--unlock", "-u", action="store_true")

    PARSER.add_argument("--save", "-s", type=str)
    PARSER.add_argument("--load", "-r", type=str)

    PARSER.add_argument("--idn", "-n", action="store_true")

    PARSER.add_argument("--monitor", "-m", action="store_true")

    PARSER.add_argument("-p", "--port", type=str, default="/dev/ttyACM0")
    PARSER.add_argument("-b", "--baudrate", type=int, default=9600)
    PARSER.add_argument("--refreshrate", type=float, default=1.0)
    PARSER.add_argument("-t", "--timeout", type=float, default=1.0)
    PARSER.add_argument(
        "--no-device-check",
        action="store_true",
        help="Skip safety confirmation. UNSAFE. Use only if you know what you are doing.",
        default=False,
    )
    PARSER.add_argument(
        "--help", action="store_true", help="Show detailed help and exit"
    )

    ARG = PARSER.parse_args()

    PSU = PowerSupply(
        port=ARG.port,
        baudrate=ARG.baudrate,
        refreshrate=ARG.refreshrate,
        timeout=ARG.timeout,
        no_device_check=ARG.no_device_check,
    )

    if ARG.help:
        PSU.print_help()
        sys.exit(0)

    if ARG.monitor:
        PSU.monitor()
        sys.exit(0)

    if ARG.get_all:
        print(PSU.get_all())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.get_voltage_set:
        print(PSU.get_voltage_set())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.get_voltage_out:
        print(PSU.get_voltage_out())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.get_current_set:
        print(PSU.get_current_set())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.get_current_out:
        print(PSU.get_current_out())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.set_voltage is not None:
        result = PSU.set_voltage(ARG.set_voltage)
        if result is not None:
            print(result)
        PSU.closeConnection()
        sys.exit(0)

    if ARG.set_current is not None:
        result = PSU.set_current(ARG.set_current)
        if result is not None:
            print(result)
        PSU.closeConnection()
        sys.exit(0)

    if ARG.on:
        print(PSU.output_on())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.off:
        print(PSU.output_off())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.lock:
        print(PSU.lock_front_panel())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.unlock:
        print(PSU.unlock_front_panel())
        PSU.closeConnection()
        sys.exit(0)

    if ARG.save is not None:
        print(PSU.save_preset(ARG.save))
        PSU.closeConnection()
        sys.exit(0)

    if ARG.load is not None:
        print(PSU.recall_preset(ARG.load))
        PSU.closeConnection()
        sys.exit(0)

    if ARG.idn:
        print(PSU.get_idn())
        PSU.closeConnection()
        sys.exit(0)
