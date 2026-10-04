# TPU ooze wipe for Bambu Lab H2D

Give TPU time to ooze over the prime tower before switching to the other nozzle. This Python script runs automatically through Bambu Studio after slicing.

**[Download the ZIP](tpu_ooze_wipe.zip?raw=true)** · **[Step-by-step Windows setup](START_HERE.txt)**

## How it works

Before switching away from TPU, the nozzle moves to the existing prime tower and makes 10 zigzag wiping strokes over approximately 10 seconds. The strokes alternate in Y while progressing across the tower in X, using a very small extrusion amount (0.1%).

The script sets the TPU nozzle target to **200°C when wiping begins**. Cooling and wiping happen together; it does not wait for the nozzle to reach 200°C. After wiping, the original print sequence and temperature commands continue.

Wipes are added at nozzle switches, not on every layer. If TPU prints several consecutive layers, it wipes when switching away from TPU. A prime tower must exist at the outgoing TPU layer height for a wipe to be added.

## Requirements

- **Bambu Lab H2D.** Developed with TPU on the right/nozzle 2 and PLA on the left/nozzle 1.
- A dual-nozzle project, **Print sequence: By layer**, and an enabled, printed prime tower.
- A filament profile identified as **TPU**.
- **Python 3.10 or newer** on your computer. No additional Python packages are needed.

The prime-tower extrusion must use planar, straight-line moves. Arc fitting and scarf seams elsewhere in the model may remain enabled.

## Setup

1. Download the ZIP and extract it into a permanent folder.
2. Follow [START_HERE.txt](START_HERE.txt) to install Python if needed and run `setup_command.py`.
3. Copy the generated command from `BAMBU_COMMAND.txt` into Bambu Studio: **Process → Others → Post-processing Scripts**, with Advanced mode enabled.
4. Save a separate process preset and slice your project.
5. Check the processed preview and try a small supervised print with your filament.

The generated command contains the paths to Python and the script. Keep both sets of quotes. Bambu Studio supplies the G-code filename automatically. Regenerate the command if you move the script folder or change your Python installation.

To turn it off, remove the command from the process preset and re-slice your project. Previously exported G-code retains its wipes.

## Troubleshooting

See [START_HERE.txt](START_HERE.txt) for installation errors and missing wipes. The preview can make the strokes difficult to see because they use very little extrusion.

This is a community-developed script. Test the fixed 200°C cooldown with your filament and printer setup before a long print.

## Optional command-line use

```text
python tpu_ooze_wipe.py input.gcode --output output.gcode
python tpu_ooze_wipe.py input.gcode.3mf --output output.gcode.3mf
```

Plain G-code is modified in place if `--output` is omitted. A 3MF archive requires a different output path. Use `--report report.json` to save a report, or `--help` to view the available options.
