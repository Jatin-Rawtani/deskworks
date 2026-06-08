from deskworks import core


# ----- chunking -----
def test_chunk_short_text_single():
    assert core._chunk("hello world", 100, 10) == ["hello world"]


def test_chunk_empty():
    assert core._chunk("   ", 100, 10) == []


def test_chunk_overlap_and_coverage():
    text = "abcdefghij" * 30          # 300 chars
    chunks = core._chunk(text, 100, 20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    # overlap: end of chunk0 reappears at start of chunk1
    assert chunks[0][-20:] == chunks[1][:20]
    # full coverage: concatenated unique content reconstructs the text
    assert text.startswith(chunks[0])


# ----- reciprocal-rank fusion -----
def test_rrf_basic_scores():
    # idx 1 is top of both rankings -> highest fused score
    fused = core.rrf_fuse([[1, 2, 3], [1, 3, 2]], k=60.0)
    assert fused[1] == 2 * (1.0 / 60.0)
    assert fused[1] > fused[2]
    assert fused[1] > fused[3]


def test_rrf_rewards_agreement_over_single_list_top():
    # idx 5 is #1 in list A only; idx 9 is #2 in BOTH lists.
    fused = core.rrf_fuse([[5, 9, 1], [2, 9, 7]], k=10.0)
    # 9 appears twice (rank1 in both) -> should beat 5 (rank0 once)
    assert fused[9] > fused[5]


def test_rrf_empty():
    assert core.rrf_fuse([]) == {}


# ----- per-document dedup -----
def test_dedup_caps_per_key():
    items = [("a", 1), ("a", 2), ("a", 3), ("b", 4)]
    kept = core.dedup_by_key(items, key_of=lambda it: it[0], max_per_key=2)
    keys = [k for k, _ in kept]
    assert keys.count("a") == 2          # capped
    assert keys.count("b") == 1
    assert kept[0] == ("a", 1)            # order preserved


def test_dedup_preserves_rank_order():
    items = list(range(10))
    kept = core.dedup_by_key(items, key_of=lambda x: x % 3, max_per_key=1)
    # one per residue class, first occurrence wins
    assert kept == [0, 1, 2]
