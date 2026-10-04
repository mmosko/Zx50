from dataclasses import dataclass


@dataclass
class AdderResult:
    res: bytearray
    cf: bool
    zf: bool
    sf: bool
    vf: bool


class AdderCore:
    @staticmethod
    def adder_core(a: bytes, b: bytes, cin: int, sub: bool) -> AdderResult:
        """Pure 32-bit carry-lookahead/ripple adder-subtractor core.

        Models MachXO2 CCU2C dedicated carry chains connected directly to HA_BUS and HB_BUS.

        :param hw: Hardware instance holding registers and datapath buses
        :param cin: Carry-in (0 or 1) for addition; Borrow-in (0 or 1) for subtraction
        :param sub: True for subtraction (HA - HB - cin), False for addition (HA + HB + cin)
        :return: (result, carry_borrow_out, zf, sf, vf)
        """

        if len(a) != 4 or len(b) != 4:
            raise ValueError(f"Operands must be 4 bytes each, got len(a)={len(a)}, len(b)={len(b)}")

        res = bytearray(4)

        # In two's-complement subtraction: A - B - borrow = A + (~B) + (1 - borrow)
        carry = (0 if cin else 1) if sub else cin

        for i in range(4):
            b_val = (b[i] ^ 0xFF) if sub else b[i]
            temp = a[i] + b_val + carry
            res[i] = temp & 0xFF
            carry = (temp >> 8) & 1

        # Zero flag: all 32 bits are 0
        zf = res == b"\x00\x00\x00\x00"

        # Sign flag: bit 31 of result is 1
        sf = bool(res[3] & 0x80)

        a_msb = bool(a[3] & 0x80)
        b_msb = bool(b[3] & 0x80)
        r_msb = sf

        if sub:
            # Borrow out: carry == 0 means borrow occurred (A < B + borrow_in)
            cf = carry == 0
            # Two's complement signed overflow on subtraction:
            # Occurs when operands have different signs and result sign differs from A
            vf = (a_msb != b_msb) and (a_msb != r_msb)
        else:
            # Unsigned carry out of MSB
            cf = bool(carry)
            # Two's complement signed overflow on addition:
            # Occurs when operands have same sign and result sign differs from inputs
            vf = (a_msb == b_msb) and (a_msb != r_msb)

        return AdderResult(res, cf, zf, sf, vf)
