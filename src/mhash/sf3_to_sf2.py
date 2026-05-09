"""One-shot converter: MuseScore SF3 (OGG-Vorbis samples) → SF2 (raw PCM).

Why this exists: fluidsynth decompresses every OGG sample inside an SF3 on
*every* invocation. For MS-Basic.sf3 that's a 6-second startup tax per
render. Converting once to SF2 trades ~140 MB of disk for an 80× faster
load (74 ms vs 6075 ms locally).

Audio is bit-identical to the SF3 path: same OGG decoder (libsndfile via
soundfile), just done once at install time instead of per-render.

Format reference (FluidSynth's `fluid_defsfont.c`):
- SF3 stores each sample as an OGG-Vorbis blob in the `smpl` chunk.
- The sample header (`shdr`) record's `start`/`end` fields hold *byte*
  offsets into `smpl` for OGG samples; `startloop`/`endloop` are
  sample-frame offsets relative to the decoded blob's frame 0.
- `sample_type & 0x10` flags an OGG-encoded sample.
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path


SHDR_SIZE = 46
PADDING_FRAMES = 46  # SF2 spec's mandated post-sample silent guard


def _find_top_lists(data: bytes) -> dict[bytes, tuple[int, int, int, int]]:
    """Return {listid: (chunk_start, chunk_end, payload_start, payload_end)}
    for each LIST inside the top-level RIFF/sfbk container."""
    if data[:4] != b"RIFF" or data[8:12] != b"sfbk":
        raise ValueError("not a SoundFont (RIFF/sfbk) file")
    riff_end = 8 + struct.unpack_from("<I", data, 4)[0]
    out: dict[bytes, tuple[int, int, int, int]] = {}
    i = 12
    while i < riff_end:
        cid = data[i:i+4]
        sz = struct.unpack_from("<I", data, i+4)[0]
        if cid == b"LIST":
            listid = data[i+8:i+12]
            out[listid] = (i, i + 8 + sz, i + 12, i + 8 + sz)
        i += 8 + sz + (sz & 1)
    return out


def _find_subchunk(data: bytes, payload_s: int, payload_e: int,
                   target: bytes) -> tuple[int, int]:
    i = payload_s
    while i < payload_e:
        cid = data[i:i+4]
        sz = struct.unpack_from("<I", data, i+4)[0]
        if cid == target:
            return (i + 8, i + 8 + sz)
        i += 8 + sz + (sz & 1)
    raise KeyError(f"subchunk {target!r} not found")


def convert(sf3_path: str | Path, sf2_path: str | Path,
            verbose: bool = True) -> tuple[int, int]:
    """Convert an SF3 to an SF2. Returns (n_decoded_samples, output_size_bytes)."""
    import soundfile as sf  # imported lazily so import-time cost is paid only when needed
    import numpy as np

    sf3_path = Path(sf3_path)
    sf2_path = Path(sf2_path)
    data = sf3_path.read_bytes()

    lists = _find_top_lists(data)
    info_s, info_e, _, _ = lists[b"INFO"]
    sdta_s, sdta_e, sdta_ps, sdta_pe = lists[b"sdta"]
    pdta_s, pdta_e, pdta_ps, pdta_pe = lists[b"pdta"]

    smpl_s, smpl_e = _find_subchunk(data, sdta_ps, sdta_pe, b"smpl")
    shdr_s, shdr_e = _find_subchunk(data, pdta_ps, pdta_pe, b"shdr")
    smpl = data[smpl_s:smpl_e]
    shdr = bytearray(data[shdr_s:shdr_e])

    n_records = len(shdr) // SHDR_SIZE
    new_smpl = bytearray()
    decoded = 0

    for n in range(n_records):
        off = n * SHDR_SIZE
        name = bytes(shdr[off:off+20]).split(b"\x00", 1)[0]
        start = struct.unpack_from("<I", shdr, off+20)[0]
        end_ = struct.unpack_from("<I", shdr, off+24)[0]
        sloop = struct.unpack_from("<I", shdr, off+28)[0]
        eloop = struct.unpack_from("<I", shdr, off+32)[0]
        sample_type = struct.unpack_from("<H", shdr, off+44)[0]

        if name == b"EOS":
            n_frames = len(new_smpl) // 2
            struct.pack_into("<I", shdr, off+20, n_frames)
            struct.pack_into("<I", shdr, off+24, n_frames)
            struct.pack_into("<I", shdr, off+28, 0)
            struct.pack_into("<I", shdr, off+32, 0)
            continue

        if sample_type & 0x10:
            # OGG-Vorbis blob: decode and append PCM
            blob = smpl[start:end_]
            try:
                pcm, _sr = sf.read(io.BytesIO(blob), dtype="int16")
            except Exception as e:
                raise RuntimeError(
                    f"OGG decode failed for sample {name!r} (idx {n}): {e}"
                )
            if pcm.ndim > 1:
                pcm = pcm[:, 0]
            new_start = len(new_smpl) // 2
            new_smpl += pcm.astype("<i2", copy=False).tobytes()
            new_smpl += b"\x00" * (PADDING_FRAMES * 2)
            new_end = new_start + len(pcm)
            new_sloop = new_start + sloop
            new_eloop = new_start + eloop
            struct.pack_into("<I", shdr, off+20, new_start)
            struct.pack_into("<I", shdr, off+24, new_end)
            struct.pack_into("<I", shdr, off+28, new_sloop)
            struct.pack_into("<I", shdr, off+32, new_eloop)
            struct.pack_into("<H", shdr, off+44, sample_type & ~0x10)
            decoded += 1
        else:
            # Already PCM (raw SF2-style entry); copy verbatim.
            pcm_bytes = smpl[start*2:end_*2]
            new_start = len(new_smpl) // 2
            new_smpl += pcm_bytes
            new_smpl += b"\x00" * (PADDING_FRAMES * 2)
            n_frames = len(pcm_bytes) // 2
            struct.pack_into("<I", shdr, off+20, new_start)
            struct.pack_into("<I", shdr, off+24, new_start + n_frames)
            struct.pack_into("<I", shdr, off+28, new_start + (sloop - start))
            struct.pack_into("<I", shdr, off+32, new_start + (eloop - start))

    if verbose:
        print(f"  decoded {decoded} OGG samples, "
              f"new smpl chunk: {len(new_smpl)/1e6:.1f} MB", file=sys.stderr)

    # ─── Reassemble the RIFF ─────────────────────────────────────────
    # Layout: RIFF<sz>sfbk INFO_LIST(unchanged) sdta_LIST(new smpl) pdta_LIST(modified shdr)
    pad = b"\x00" if (len(new_smpl) & 1) else b""
    new_sdta_payload = (b"sdta"
                        + b"smpl" + struct.pack("<I", len(new_smpl))
                        + bytes(new_smpl) + pad)
    new_sdta_chunk = (b"LIST"
                      + struct.pack("<I", len(new_sdta_payload))
                      + new_sdta_payload)

    # pdta with shdr replaced. shdr length is unchanged, so a byte-splice works.
    pdta_blob = bytearray(data[pdta_s:pdta_e])
    rel_shdr_s = shdr_s - pdta_s
    rel_shdr_e = shdr_e - pdta_s
    pdta_blob[rel_shdr_s:rel_shdr_e] = bytes(shdr)

    # Bump the SF version chunk to 2.04 inside INFO.
    info_blob = bytearray(data[info_s:info_e])
    try:
        ifil_s, ifil_e = _find_subchunk(bytes(info_blob), 12, len(info_blob), b"ifil")
        struct.pack_into("<HH", info_blob, ifil_s, 2, 4)
    except KeyError:
        pass

    body = bytes(info_blob) + new_sdta_chunk + bytes(pdta_blob)
    final = (b"RIFF"
             + struct.pack("<I", len(body) + 4)
             + b"sfbk"
             + body)
    sf2_path.parent.mkdir(parents=True, exist_ok=True)
    sf2_path.write_bytes(final)
    return decoded, len(final)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m mhash.sf3_to_sf2 <in.sf3> <out.sf2>",
              file=sys.stderr)
        sys.exit(2)
    n, sz = convert(sys.argv[1], sys.argv[2])
    print(f"  ✓ wrote {sys.argv[2]} ({sz/1e6:.1f} MB, {n} samples decoded)",
          file=sys.stderr)
