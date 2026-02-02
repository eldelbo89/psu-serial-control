# psu-serial-control
A small Python tool for controlling and monitoring a programmable bench power supply over a serial (UART) interface. This is working code written for RND 320-KWR103, shared to spread knowledge and inspire others. Disclaimer: Sends raw serial commands. Use on any device is entirely at your own risk.


## Disclaimer

This tool sends **raw serial commands** directly to the connected power supply.

* It has only been tested on **RND 320-KWR103**
* Compatibility with any other device is **not guaranteed**
* Using this software with untested hardware may cause unexpected behavior, device damage, or unsafe conditions

**You use this software entirely at your own risk.**
The author takes **no responsibility** for any damage, malfunction, or consequences resulting from its use on any device, tested or untested.

Always consult your power supply's documentation and verify supported commands before use.

---

## Overview

`psu-serial-control` is a **command-line based (CLI) tool**.
It does **not** provide a graphical user interface (GUI).

Instead, it offers:

* Direct CLI commands for control and queries
* An optional **ASCII-based live monitor**
* A local UNIX socket server for safe multi-process access

---
## Requirements

* Python 3
* `pyserial`

Install dependency:

```bash
pip install pyserial
```

---

## Virtual Environments (General Advice)

It is good practice to use a **separate Python virtual environment (`venv`) for each project**.
This avoids dependency conflicts between projects and keeps your system Python clean.

Using isolated environments makes projects easier to maintain, reproduce, and share.

Example:

```bash
python3 -m venv power-supply-venv
source power-supply-venv/bin/activate
pip install pyserial
```

Using a dedicated virtual environment keeps dependencies isolated and makes the setup reproducible.

---

## Usage

Basic command structure:

```bash
python powersupply.py [OPTIONS]
```

### Live Monitor (ASCII UI)

Start a live dashboard and background control server:

```bash
python powersupply.py --port /dev/ttyACM0 --monitor
```

This displays an ASCII-based status view showing:

* Set voltage and current
* Output voltage and current
* Output state

The display refreshes at a configurable interval.

---

## Supported Commands

### Read values

```bash
--get-voltage-set
--get-voltage-out
--get-current-set
--get-current-out
--get-all
```

### Set values

```bash
--set-voltage <voltage>
--set-current <current>
```

### Output control

```bash
--on
--off
```

### Front panel control

```bash
--lock
--unlock
```

### Presets

```bash
--save <slot>
--load <slot>
```

### Identification

```bash
--idn
```

---

## Examples

```bash
python powersupply.py --monitor
python powersupply.py --set-voltage 12.5
python powersupply.py --set-current 2.0
python powersupply.py --on
```

---

## Notes

* By default, the program requires a safety confirmation before executing commands
* Use `--no-device-check` **only if you fully understand the risks**
* Designed for practical, hands-on hardware control, not abstraction or auto-detection

---
