"""Print the Bambu Studio command for this copy of the package."""
import sys
from pathlib import Path
if sys.version_info < (3,10):
    raise SystemExit('Python 3.10 or newer is required.')
import tpu_ooze_wipe
script=Path(__file__).resolve().with_name('tpu_ooze_wipe.py')
command=f'"{sys.executable}" "{script}"'
script.with_name('BAMBU_COMMAND.txt').write_text(command+'\n')
print('Setup check passed. Copy the entire following line into Bambu Studio:')
print(command)
print('A copy was saved in BAMBU_COMMAND.txt beside the scripts.')
