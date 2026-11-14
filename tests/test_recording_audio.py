from scripts.render_recording_audio import played_chunks


def receipt(name, time, count, start=0, chunk='a'):
    return {'name': name, 'aligned_server_ms': time * 1000,
        'details': {'response_id': 'r1', 'audio_context_time': time,
            'sample_rate': 24000, 'chunks': [{'chunk_id': chunk,
                'sample_start': start, 'played_samples_in_chunk': count}]}}


def test_interrupted_output_excludes_unplayed_tail():
    events = [receipt('playback_start', 1, 0),
        receipt('playback_progress', 1.05, 1200),
        receipt('playback_end', 1.1, 2400)]
    chunks = played_chunks(events, 0)
    assert len(chunks) == 1
    assert chunks[0]['samples'] == 2400
    assert chunks[0]['start'] == 1


def test_silent_gap_is_not_collapsed():
    chunks = played_chunks([receipt('playback_start', 1, 0),
        receipt('playback_chunk_ended', 1.1, 2400),
        receipt('playback_chunk_ended', 2.1, 2400, 2400, 'b')], 0)
    assert [chunk['start'] for chunk in chunks] == [1, 2]
    assert [chunk['source_start'] for chunk in chunks] == [0, 2400]


def test_never_played_output_is_absent():
    assert played_chunks([receipt('playback_end', 1, 0)], 0) == []
