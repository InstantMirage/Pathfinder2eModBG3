Spell Support Tool PF2 specifics:
- Assumes the base template for object stats has 2 action points for spells as standard. You would need to change some code to make it detect 1 action point instead.
- You need to manually copy the various input files as required, including the Object stats file, your spell stats files, and your localization file.
- Will skip spells ending in "\_AI".
- Use the Owner field to manually define a spell to be learnt instead of that which is cast. This is useful for ranked modal spells, where there is no upcast container spell normally. One can make a ranked version of the container, make it inaccessible by non-scroll means, and then have the learnt spell point to the real spell.
- Ensure that Divine.exe, the backend to the Export Tool, is in your path, in order to convert LSF files.
- You will need to manually provide the controllerUI-sized DDS icons for any spell icons you might be using, and place them in the Input/Icons folder. Do the same for the full-sized icons with fade effects in Input/Icons/Large.
- You will need ImageMagick installed for image manipulation, and the python library Wand to interface with it.
- When finished running the script, start up TK and open the object.stats file. If it doesn't yet have the new scrolls added, close the stats editor and reloat stats. Once those additionas are visible, export the object.stats file. Restart TK, and the linkages between the new root templates and the stats elements should be resolved.
- UI icons will need to be imported manually using toolkit, as directly saving as DDS was too finicky to get working. Should be able to target the folders and import the whole lot.
