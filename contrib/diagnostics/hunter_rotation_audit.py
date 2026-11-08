"""Acceptance of native Hunter effects and the Engine path that produced them."""
import re


def audit_rotation(actions, lines, guid):
    rows = [line.split('Sting rotation summary ', 1)[1] for line in lines
            if f'Sting rotation summary guid={guid} ' in line]
    errors = []
    observation = dict(re.findall(r'(\w+)=(\w+)', rows[-1])) if len(rows) == 1 else {}
    if len(rows) != 1:
        errors.append('Expected one native rotation summary for the requested Hunter')

    def succeeded(name):
        return actions.get(name, {}).get('OK', 0) > 0

    for effect in ('primary', 'secondary', 'mark', 'damage'):
        if observation.get(effect) != 'true':
            errors.append(f'Missing native effect: {effect}')
    if not succeeded("hunter's mark"):
        errors.append("Missing Engine success: hunter's mark")
    required_arrow = observation.get('requires_black_arrow')
    if required_arrow not in ('true', 'false'):
        errors.append('Missing native Black Arrow capability observation')
    elif required_arrow == 'true':
        if observation.get('black_arrow') != 'true' or not succeeded('black arrow'):
            errors.append('Missing native Black Arrow effect or Engine success')

    direct = {name: succeeded(name) for name in ('serpent sting', 'serpent sting on attacker')}
    # spell_hunt_multishot::HandleHit casts owned 118253 only if HasSpell(87935).
    # Spec alone, an OK alone, or auras alone do not establish this route.
    spread = observation.get('known_serpent_spread') == 'true' and succeeded('multi-shot')
    route = 'direct' if all(direct.values()) else 'serpent-spread' if spread else 'unproved'
    if route == 'unproved':
        errors.append('Missing direct Sting Engine successes or native Serpent Spread + Multi-Shot')
    return {'passed': not errors, 'errors': errors, 'sting_route': route,
            'direct_actions_observed': direct, 'native_observation': observation}
