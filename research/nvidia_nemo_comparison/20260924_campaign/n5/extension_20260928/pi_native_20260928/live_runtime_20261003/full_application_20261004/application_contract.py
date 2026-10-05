"""Mature application intent, independent of backend selection. See README.md."""
from copy import deepcopy
import json
import math
import uuid


SCHEMA = 'just-peachy.application-intent.v1'
MODES = ('caption_only', 'enrolled_names', 'selected_focus', 'selected_closed',
         'spatial_assisted', 'strongly_spatial_assisted', 'spatial_selected',
         'strongly_spatial_selected', 'assigned_direction', 'assigned_hybrid',
         'anonymous_conversation', 'open_with_names')
SELECTED = {'selected_focus', 'selected_closed', 'spatial_selected',
            'strongly_spatial_selected', 'assigned_hybrid'}
SPATIAL = {'spatial_assisted', 'strongly_spatial_assisted', 'spatial_selected',
           'strongly_spatial_selected', 'assigned_direction', 'assigned_hybrid'}
SEATS = {'assigned_direction', 'assigned_hybrid'}
FIELDS = {'schema', 'mode', 'recipe', 'tap', 'selected_ids', 'display_ids',
          'strict', 'seating', 'identity_overrides', 'settings'}


def identifiers(values):
    if not isinstance(values, list) or len(values) > 256 or len(set(values)) != len(values):
        raise ValueError('Unique bounded participant UUID list required')
    for value in values:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError('Canonical personal UUID required')
    return list(values)


def default(embedding):
    return dict(schema=SCHEMA, mode='anonymous_conversation' if embedding == 'anonymous' else 'open_with_names',
                recipe='balanced', tap='O0', selected_ids=[], display_ids=[], strict=False,
                seating=None, identity_overrides={}, settings={})


def compatibility(selection, mode):
    """Expose specific existing integration limits instead of changing gates."""
    if mode not in MODES:
        return 'Unknown application Mode'
    if selection.embedding == 'anonymous' and mode not in ('caption_only', 'anonymous_conversation'):
        return 'This backend has no personal embedding gallery; choose a named embedding backend'
    if mode in SPATIAL and selection.input_source != 'live':
        return 'Spatial association needs bound live direction/motion observations; saved-spatial replay is not implemented'
    if mode in SEATS and (selection.diarizer != 'pyannote' or selection.embedding != 'redimnet'):
        return 'The retained seat resolver uses Pyannote/ReDimNet C088 voice-event gates; replacing them with N2 calibration is not implemented'
    return None


def validate(value, selection, *, people=None):
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA:
        raise ValueError('Complete exact application intent required')
    if len(json.dumps(value, allow_nan=False).encode()) > 65536:
        raise ValueError('Application intent exceeds 64 KiB')
    reason = compatibility(selection, value['mode'])
    if reason:
        raise ValueError(reason)
    if value['recipe'] not in ('fast', 'classic', 'balanced', 'patient') or value['tap'] != 'O0':
        raise ValueError('Current qualified acquisition is O0; use a retained recipe')
    if value['recipe'] == 'fast' and value['mode'] != 'caption_only':
        raise ValueError('Fast captions has no speaker inference')
    if value['recipe'] == 'classic' and (selection.diarizer != 'pyannote' or value['mode'] not in ('caption_only', 'anonymous_conversation')):
        raise ValueError('Classic continuity uses the original Pyannote tracker')
    selected, display = identifiers(value['selected_ids']), identifiers(value['display_ids'])
    if people is not None and (set(selected) | set(display)) - set(people):
        raise ValueError('A selected person no longer exists in this encoder gallery')
    if value['mode'] in SELECTED and not selected:
        raise ValueError('Select compatible enrolled participants first')
    if type(value['strict']) is not bool or (value['strict'] and (not display or value['mode'] in ('caption_only', 'anonymous_conversation'))):
        raise ValueError('Display filtering requires a named mode and a separate display roster')
    if not isinstance(value['identity_overrides'], dict) or not isinstance(value['settings'], dict):
        raise ValueError('Explicit settings/overrides dictionaries required')
    if (selection.diarizer == 'nemotron' or selection.embedding == 'titanet') and value['identity_overrides']:
        raise ValueError('N2 keeps its exact model/domain naming calibration; baseline overrides cannot replace it')
    if value['mode'] in SEATS:
        seat = value['seating']
        if not isinstance(seat, dict) or seat.get('valid') is not True or not seat.get('rows'):
            raise ValueError('Apply the seat layout at this location before Start')
        if set(selected) != {r['person_id'] for r in seat['rows']}:
            raise ValueError('Assigned layout and participant roster differ')
    elif value['seating'] is not None:
        raise ValueError('Seat intent belongs only to assigned-seat modes')
    return deepcopy(value)


def capacity_seconds(free_bytes, reserve_bytes, *, raw_bytes_per_second=0,
                     metadata_bytes_per_second=262144, export_copy=True):
    """Compute a storage ceiling, not a conversation timer; reserve export room."""
    for value in (free_bytes, reserve_bytes, raw_bytes_per_second, metadata_bytes_per_second):
        if type(value) is not int or value < 0:
            raise ValueError('Measured nonnegative byte counts required')
    if type(export_copy) is not bool:
        raise ValueError('Explicit independent export allocation required')
    # Two model-input representations (float32 and PCM16), actual raw, plus
    # existing worst-case evidence allocation and fixed metadata/closure reserve.
    fixed = 24 * 1024**2
    available = (free_bytes-reserve_bytes)//(2 if export_copy else 1)-fixed
    rate = 16000*6 + raw_bytes_per_second + metadata_bytes_per_second
    seconds = available//rate
    if seconds < 1:
        raise ValueError('Storage cannot admit audio and complete independent export')
    # Signed 64-bit source indexes and segmented audio are used downstream.
    return min(seconds, 2**31-1)
