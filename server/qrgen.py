"""Minimal, dependency-free QR code encoder.

Implements just enough of ISO/IEC 18004 to encode short byte-mode
strings (like a LAN URL) at QR versions 1-4: mode/length/data bit
stream, Reed-Solomon error correction over GF(256), block
interleaving, matrix placement (finder/timing/alignment/dark module),
all 8 data masks with penalty scoring, and BCH-encoded format info.

No image/QR library dependency at all — this exists specifically so
EventHub Server (which must run on a machine with no internet access
to `pip install`) can still show a scannable QR code.
"""
from __future__ import annotations

# ---- Galois Field GF(256) tables (primitive polynomial 0x11D) --------------
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator_poly(degree: int) -> list[int]:
    poly = [1]
    for i in range(degree):
        new_poly = [0] * (len(poly) + 1)
        for j, coefficient in enumerate(poly):
            new_poly[j] ^= coefficient
            new_poly[j + 1] ^= _gf_mul(coefficient, _EXP[i])
        poly = new_poly
    return poly


def _rs_encode(data: list[int], ec_count: int) -> list[int]:
    generator = _rs_generator_poly(ec_count)
    remainder = list(data) + [0] * ec_count
    for i in range(len(data)):
        coefficient = remainder[i]
        if coefficient == 0:
            continue
        factor = _LOG[coefficient]
        for j, generator_coefficient in enumerate(generator):
            if generator_coefficient == 0:
                continue
            remainder[i + j] ^= _EXP[factor + _LOG[generator_coefficient]]
    return remainder[len(data):]


# ---- Per-version tables (versions 1-4 only — plenty for a LAN URL) --------
# {version: {ec_level: (ec_codewords_per_block, [(block_count, data_codewords), ...])}}
_RS_BLOCKS = {
    1: {"L": (7, [(1, 19)]), "M": (10, [(1, 16)]), "Q": (13, [(1, 13)]), "H": (17, [(1, 9)])},
    2: {"L": (10, [(1, 34)]), "M": (16, [(1, 28)]), "Q": (22, [(1, 22)]), "H": (28, [(1, 16)])},
    3: {"L": (15, [(1, 55)]), "M": (26, [(1, 44)]), "Q": (18, [(2, 17)]), "H": (22, [(2, 13)])},
    4: {"L": (20, [(1, 80)]), "M": (18, [(2, 32)]), "Q": (26, [(2, 24)]), "H": (16, [(4, 9)])},
}
_ALIGNMENT_CENTERS = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26]}
_REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7}

_FORMAT_GENERATOR = 0b10100110111
_FORMAT_MASK = 0b101010000010010
_EC_LEVEL_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}


def _bch_format_bits(ec_level: str, mask_pattern: int) -> list[int]:
    data = (_EC_LEVEL_BITS[ec_level] << 3) | mask_pattern
    # Standard BCH(15,5) division against the format generator polynomial.
    remainder = data << 10
    for i in range(4, -1, -1):
        if remainder & (1 << (i + 10)):
            remainder ^= _FORMAT_GENERATOR << i
    final = ((data << 10) | remainder) ^ _FORMAT_MASK
    return [(final >> i) & 1 for i in range(14, -1, -1)]


_MASK_FUNCTIONS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


class QRCode:
    def __init__(self, version: int, ec_level: str):
        self.version = version
        self.ec_level = ec_level
        self.size = version * 4 + 17
        self.modules: list[list[bool | None]] = [[None] * self.size for _ in range(self.size)]
        self.reserved: list[list[bool]] = [[False] * self.size for _ in range(self.size)]

    # -- module placement helpers --------------------------------------------
    def _set(self, row: int, col: int, dark: bool, reserve: bool = True):
        self.modules[row][col] = dark
        if reserve:
            self.reserved[row][col] = True

    def _place_finder(self, row: int, col: int):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = row + dr, col + dc
                if not (0 <= r < self.size and 0 <= c < self.size):
                    continue
                dark = (0 <= dr <= 6 and dc in (0, 6)) or (0 <= dc <= 6 and dr in (0, 6)) or (2 <= dr <= 4 and 2 <= dc <= 4)
                self._set(r, c, dark)

    def _place_finders_and_separators(self):
        self._place_finder(0, 0)
        self._place_finder(0, self.size - 7)
        self._place_finder(self.size - 7, 0)

    def _place_timing(self):
        for i in range(8, self.size - 8):
            dark = i % 2 == 0
            if self.modules[6][i] is None:
                self._set(6, i, dark)
            if self.modules[i][6] is None:
                self._set(i, 6, dark)

    def _place_alignment(self):
        centers = _ALIGNMENT_CENTERS.get(self.version, [])
        for row_center in centers:
            for col_center in centers:
                if self.modules[row_center][col_center] is not None:
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        dark = max(abs(dr), abs(dc)) != 1
                        self._set(row_center + dr, col_center + dc, dark)

    def _place_dark_module(self):
        self._set(4 * self.version + 9, 8, True)

    def _reserve_format_areas(self):
        for i in range(9):
            if self.modules[8][i] is None:
                self.reserved[8][i] = True
            if self.modules[i][8] is None:
                self.reserved[i][8] = True
        for i in range(8):
            self.reserved[8][self.size - 1 - i] = True
            self.reserved[self.size - 1 - i][8] = True

    def _place_format_info(self, mask_pattern: int):
        bits = _bch_format_bits(self.ec_level, mask_pattern)
        # bits[0..14], MSB first
        for i in range(6):
            self._set(8, i, bool(bits[i]))
        self._set(8, 7, bool(bits[6]))
        self._set(8, 8, bool(bits[7]))
        self._set(7, 8, bool(bits[8]))
        for i in range(9, 15):
            self._set(14 - i, 8, bool(bits[i]))
        for i in range(8):
            self._set(self.size - 1 - i, 8, bool(bits[i]))
        for i in range(8, 15):
            self._set(8, self.size - 15 + i, bool(bits[i]))

    def _data_bit_positions(self):
        positions = []
        col = self.size - 1
        upward = True
        while col > 0:
            if col == 6:  # skip vertical timing column
                col -= 1
            for i in range(self.size):
                row = (self.size - 1 - i) if upward else i
                for c in (col, col - 1):
                    if not self.reserved[row][c]:
                        positions.append((row, c))
            upward = not upward
            col -= 2
        return positions

    def _penalty(self) -> int:
        size = self.size
        modules = self.modules
        score = 0
        # Rule 1: runs of 5+ same-color modules in a row/column
        for row in modules:
            score += _run_penalty(row)
        for c in range(size):
            score += _run_penalty([modules[r][c] for r in range(size)])
        # Rule 2: 2x2 blocks of same color
        for r in range(size - 1):
            for c in range(size - 1):
                v = modules[r][c]
                if v == modules[r][c + 1] == modules[r + 1][c] == modules[r + 1][c + 1]:
                    score += 3
        # Rule 3: finder-like patterns
        pattern_a = [True, False, True, True, True, False, True, False, False, False, False]
        pattern_b = list(reversed(pattern_a))
        for r in range(size):
            row = modules[r]
            for c in range(size - 10):
                window = row[c:c + 11]
                if window == pattern_a or window == pattern_b:
                    score += 40
        for c in range(size):
            col = [modules[r][c] for r in range(size)]
            for r in range(size - 10):
                window = col[r:r + 11]
                if window == pattern_a or window == pattern_b:
                    score += 40
        # Rule 4: overall dark proportion
        dark_count = sum(1 for row in modules for v in row if v)
        ratio = dark_count / (size * size) * 100
        score += int(abs(ratio - 50) / 5) * 10
        return score

    def build(self, codewords: list[int]) -> "QRCode":
        self._place_finders_and_separators()
        self._place_alignment()
        self._place_timing()
        self._place_dark_module()
        self._reserve_format_areas()

        bits: list[int] = []
        for byte in codewords:
            bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
        bits.extend([0] * _REMAINDER_BITS.get(self.version, 0))

        positions = self._data_bit_positions()
        for index, (row, col) in enumerate(positions):
            bit = bits[index] if index < len(bits) else 0
            self.modules[row][col] = bool(bit)

        base_modules = [row[:] for row in self.modules]
        best_mask, best_score, best_modules = None, None, None
        for mask_index, mask_fn in enumerate(_MASK_FUNCTIONS):
            trial = [row[:] for row in base_modules]
            for row, col in positions:
                if mask_fn(row, col):
                    trial[row][col] = not trial[row][col]
            self.modules = trial
            self._place_format_info(mask_index)
            score = self._penalty()
            if best_score is None or score < best_score:
                best_mask, best_score, best_modules = mask_index, score, [row[:] for row in self.modules]
        self.modules = best_modules
        return self


def _run_penalty(line: list[bool]) -> int:
    score = 0
    run_length = 1
    for i in range(1, len(line)):
        if line[i] == line[i - 1]:
            run_length += 1
        else:
            if run_length >= 5:
                score += run_length - 2
            run_length = 1
    if run_length >= 5:
        score += run_length - 2
    return score


def _encode_byte_mode(data: bytes, version: int, ec_level: str) -> list[int]:
    _, blocks_spec = _RS_BLOCKS[version][ec_level]
    total_data_codewords = sum(count * size for count, size in blocks_spec)

    bit_buffer: list[int] = []
    bit_buffer.extend([0, 1, 0, 0])  # byte-mode indicator
    length = len(data)
    bit_buffer.extend((length >> shift) & 1 for shift in range(7, -1, -1))
    for byte in data:
        bit_buffer.extend((byte >> shift) & 1 for shift in range(7, -1, -1))

    capacity_bits = total_data_codewords * 8
    for _ in range(min(4, capacity_bits - len(bit_buffer))):
        bit_buffer.append(0)
    while len(bit_buffer) % 8 != 0:
        bit_buffer.append(0)

    codewords = [
        int("".join(str(b) for b in bit_buffer[i:i + 8]), 2)
        for i in range(0, len(bit_buffer), 8)
    ]
    pad_bytes = [0xEC, 0x11]
    pad_index = 0
    while len(codewords) < total_data_codewords:
        codewords.append(pad_bytes[pad_index % 2])
        pad_index += 1
    return codewords


def _interleave(data_codewords: list[int], version: int, ec_level: str) -> list[int]:
    ec_count, blocks_spec = _RS_BLOCKS[version][ec_level]
    data_blocks: list[list[int]] = []
    ec_blocks: list[list[int]] = []
    offset = 0
    for count, size in blocks_spec:
        for _ in range(count):
            block = data_codewords[offset:offset + size]
            offset += size
            data_blocks.append(block)
            ec_blocks.append(_rs_encode(block, ec_count))

    result: list[int] = []
    max_data_len = max(len(b) for b in data_blocks)
    for i in range(max_data_len):
        for block in data_blocks:
            if i < len(block):
                result.append(block[i])
    max_ec_len = max(len(b) for b in ec_blocks)
    for i in range(max_ec_len):
        for block in ec_blocks:
            if i < len(block):
                result.append(block[i])
    return result


def _select_version(data: bytes, ec_level: str) -> int:
    for version in sorted(_RS_BLOCKS.keys()):
        _, blocks_spec = _RS_BLOCKS[version][ec_level]
        total_data_codewords = sum(count * size for count, size in blocks_spec)
        capacity_bits = total_data_codewords * 8
        needed_bits = 4 + 8 + len(data) * 8
        if needed_bits <= capacity_bits:
            return version
    raise ValueError(
        f"Tekst te lang voor een QR-code van dit formaat ({len(data)} bytes). "
        "Gebruik een korter adres."
    )


def generate_matrix(text: str, ec_level: str = "M") -> list[list[bool]]:
    """Encode `text` (ASCII/Latin-1 URL) as a QR code; returns a 2D bool matrix."""
    data = text.encode("utf-8")
    version = _select_version(data, ec_level)
    data_codewords = _encode_byte_mode(data, version, ec_level)
    all_codewords = _interleave(data_codewords, version, ec_level)
    qr = QRCode(version, ec_level).build(all_codewords)
    return [[bool(v) for v in row] for row in qr.modules]


def matrix_to_svg(matrix: list[list[bool]], module_size: int = 8, border: int = 4) -> str:
    size = len(matrix)
    total = (size + border * 2) * module_size
    rects = []
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                x = (c + border) * module_size
                y = (r + border) * module_size
                rects.append(f'<rect x="{x}" y="{y}" width="{module_size}" height="{module_size}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" '
        f'shape-rendering="crispEdges">'
        f'<rect width="{total}" height="{total}" fill="#ffffff"/>'
        f'<g fill="#0d1117">{"".join(rects)}</g></svg>'
    )
