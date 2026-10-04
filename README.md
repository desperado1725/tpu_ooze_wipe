# TPU ooze wipe for Bambu Lab H2D

A Bambu Studio postprocessing script that adds TPU wipes on the existing prime tower before an eligible nozzle switch.

**[Download the ready-to-use ZIP](tpu_ooze_wipe.zip?raw=true)** · **[Windows setup instructions](START_HERE.txt)**

## What it does

- Adds 10 zigzag strokes over the prime tower, alternating in Y and progressing in X.
- Uses approximately 10 seconds of commanded wiping motion, with 0.1% extrusion.
- Requests a 200°C TPU nozzle target as wiping begins. It **does not wait** for the nozzle to reach 200°C.
- Returns to the previous position and restores motion settings before the original G-code continues.

This is the **wipe-only** edition. It preserves every original G-code line. It does not change PLA-on-TPU print speeds, remove existing retractions, limit repeated retractions, or reroute model travel. The inserted routine has its own matched retract/refeed moves for travel to and from the tower.

## Requirements

- Bambu Lab H2D, developed with TPU on the right/nozzle 2 and PLA on the left/nozzle 1.
- Dual-nozzle, by-layer printing with an actual prime tower and TPU identified as TPU in the filament profile.
- Python 3.10 or newer. No additional Python packages are required.

The prime-tower paths used to determine its footprint must be planar straight-line extrusion. Arc fitting and scarf seams elsewhere are not automatically incompatible. A suitable prime tower must exist at the outgoing TPU height; otherwise that wipe is skipped.

## Install

1. Download the ZIP above and use **Extract All** into a permanent folder.
2. Follow **[START_HERE.txt](START_HERE.txt)** to install Python if needed.
3. Run `setup_command.py` with Python. It creates `BAMBU_COMMAND.txt` with the correct command for your computer.
4. Paste that whole command into Bambu Studio's **Process → Others → Post-processing Scripts** field (Advanced mode).
5. Save a separate process preset and re-slice your original project.

Do not paste the Python script into a machine G-code field. Do not add the G-code filename to the command; Bambu Studio supplies it. Avoid adding the script twice or combining it with another version of this same wipe routine.

To disable it, remove the command and re-slice the original project. Removing the command does not undo a previously modified export.

## Scope

This is an unofficial, user-developed script, not a Bambu Lab product. The fixed 200°C cooldown and wiping behavior need testing with your filament and printer setup. Start with a small supervised test. It is an oozing workaround, not a proven cure for extrusion-force errors or clogs.

Normal sliced temperature commands continue after the inserted routine. No printer credentials, firmware modification, or network connection are required by the script.

## Optional command-line use

```text
python tpu_ooze_wipe.py input.gcode --output output.gcode
python tpu_ooze_wipe.py input.gcode.3mf --output output.gcode.3mf
```

Plain G-code is modified in place if `--output` is omitted. A 3MF archive requires a different output path. Optional `--report report.json` saves a report. Run `--help` for details.
