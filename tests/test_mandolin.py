from mtab.mandolin import assign_frets, choose_shift, fit_range, OPEN
from mtab.rhythm import QNote


def q(midi):
    return QNote(onset=0, duration=1, midi=midi, residual=0, periodicity=1, stability=1,
                 stem="x")


def test_open_strings_win_in_first_position():
    # D major scale from open D: D E F# G A B C# D
    notes = [q(m) for m in (62, 64, 66, 67, 69, 71, 73, 74)]
    fit_range(notes, 0)
    assign_frets(notes)
    assert [(n.string, n.fret) for n in notes] == [
        (3, 0), (3, 2), (3, 4), (3, 5), (2, 0), (2, 2), (2, 4), (2, 5)]


def test_every_note_is_playable_and_correct():
    notes = [q(m) for m in range(55, 92)]
    fit_range(notes, 0)
    assign_frets(notes)
    for n in notes:
        assert OPEN[n.string] + n.fret == n.written
        assert 0 <= n.fret <= 15


def test_shift_moves_a_low_vocal_line_up_an_octave():
    baritone = [45, 47, 48, 50, 52, 53, 55, 57]  # A2..A3: below the mandolin
    assert choose_shift(baritone, tonic=9, mode="minor", key_change=False) == 12


def test_shift_keeps_a_line_already_in_range():
    assert choose_shift([62, 64, 66, 67, 69, 71], 2, "major", False) == 0


def test_key_change_prefers_friendly_key():
    eb_major = [63, 65, 67, 68, 70, 72, 74, 75]
    s = choose_shift(eb_major, tonic=3, mode="major", key_change=True)
    assert (3 + s) % 12 in {7, 2, 9, 0, 5}


def test_out_of_range_notes_are_folded():
    notes = [q(50), q(62)]
    assert fit_range(notes, 0) == 1
    assert notes[0].written == 62
