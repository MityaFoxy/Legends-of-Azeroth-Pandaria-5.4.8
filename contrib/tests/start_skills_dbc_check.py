"""Read-only original-5.4.8 DBC checks; pass the runtime Data/dbc directory."""
import argparse
from pathlib import Path
import struct

OBSOLETE = {26, 256, 257, 803, 184, 267, 594, 50, 51, 163, 38, 39,
            253, 797, 176, 56, 78, 613, 770, 771, 772, 373, 374, 375,
            801, 6, 8, 237, 799, 354, 355, 593, 802, 134, 573, 574}
CLASS_SKILLS = {1: 840, 2: 800, 3: 795, 4: 921, 5: 804, 6: 796,
                7: 924, 8: 904, 9: 849, 10: 829, 11: 798}


def read_dbc(path, expected_fields):
    data = path.read_bytes()
    magic, count, fields, size, strings = struct.unpack_from('<4s4I', data)
    if (magic != b'WDBC' or fields != expected_fields or size != fields * 4
            or len(data) != 20 + count * size + strings):
        raise ValueError(f'Unexpected original-MoP DBC layout: {path}')
    return list(struct.iter_unpack('<' + 'I' * fields, data[20:20 + count * size]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dbc', type=Path)
    args = parser.parse_args()
    skills = read_dbc(args.dbc / 'SkillLine.dbc', 9)
    race_class = read_dbc(args.dbc / 'SkillRaceClassInfo.dbc', 8)
    abilities = read_dbc(args.dbc / 'SkillLineAbility.dbc', 13)
    for name, rows, field in [('SkillLine', skills, 0),
                              ('SkillRaceClassInfo', race_class, 1),
                              ('SkillLineAbility', abilities, 1)]:
        found = OBSOLETE.intersection(row[field] for row in rows)
        if found:
            raise ValueError(f'{name}: legacy IDs still referenced: {sorted(found)}')
        print(f'PASS: all 36 legacy IDs absent from {name}')
    present = {row[0] for row in skills}
    for cls, skill in CLASS_SKILLS.items():
        # Layout: ID, SkillID, RaceMask, ClassMask, Flags, Availability,
        # ReqLevel, SkillTierID. Mirrors the automatic loader's predicates.
        matches = [r for r in race_class if r[1] == skill and r[2]
                   and r[3] & (1 << (cls - 1)) and r[5] == 1 and r[6] <= 1]
        if skill not in present or not matches:
            raise ValueError(f'No automatic starting class skill: class={cls}, skill={skill}')
        print(f'PASS: class {cls}, skill {skill}, automatic record(s) {[r[0] for r in matches]}')
    print('DBC validation only; not a character-creation/client gameplay test.')


if __name__ == '__main__':
    main()
