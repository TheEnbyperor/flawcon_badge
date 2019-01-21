from micropython import const
from machine import Pin, EPSPI
import time

WHITE = 0
BLACK = 1
RED = 2

_SPI_COMMAND = False
_SPI_DATA = True


class _EPD:
    def __init__(self, spi, cs_pin, reset_pin, busy_pin):

        self.resolution = const((296, 128))
        self.width, self.height = self.resolution
        self.cols, self.rows, self.rotation = const((128, 296, -90))

        self.buf = [[0 for _ in range(self.height)] for _ in range(self.width)]
        self.border_colour = 0

        self._reset_pin = reset_pin
        self._busy_pin = busy_pin
        self._cs_pin = cs_pin
        self._spi = spi

        self._luts = {
            'default': [
                # Phase 0     Phase 1     Phase 2     Phase 3     Phase 4     Phase 5     Phase 6
                # A B C D     A B C D     A B C D     A B C D     A B C D     A B C D     A B C D
                0b01001000, 0b10100000, 0b00010000, 0b00010000, 0b00010011, 0b00000000, 0b00000000,  # LUT0 - Black
                0b01001000, 0b10100000, 0b10000000, 0b00000000, 0b00000011, 0b00000000, 0b00000000,  # LUTT1 - White
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,  # IGNORE
                0b01001000, 0b10100101, 0b00000000, 0b10111011, 0b00000000, 0b00000000, 0b00000000,  # LUT3 - Red
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,  # LUT4 - VCOM

                # Duration            |  Repeat
                # A   B     C     D   |
                64,   12,   32,   12,    6,   # 0 Flash
                16,   8,    4,    4,     6,   # 1 clear
                4,    8,    8,    16,    16,  # 2 bring in the black
                2,    2,    2,    64,    32,  # 3 time for red
                2,    2,    2,    2,     2,   # 4 final black sharpen phase
                0,    0,    0,    0,     0,   # 5
                0,    0,    0,    0,     0    # 6
            ]
        }

    def setup(self):
        self._reset_pin.off()
        time.sleep(0.1)
        self._reset_pin.on()
        time.sleep(0.1)

        self._send_command(0x12)  # Soft Reset
        self._busy_wait()

    def _busy_wait(self):
        while self._busy_pin.value():
            time.sleep(0.01)

    def _update(self, buf_a, buf_b):
        self.setup()

        packed_height = list(struct.pack('<H', self.rows))

        self._send_command(0x74, 0x54)  # Set Analog Block Control
        self._send_command(0x7e, 0x3b)  # Set Digital Block Control

        self._send_command(0x01, packed_height + [0x00])  # Gate setting

        self._send_command(0x03, [0b10000, 0b0001])  # Gate Driving Voltage

        self._send_command(0x3a, 0x07)  # Dummy line period
        self._send_command(0x3b, 0x04)  # Gate line width
        self._send_command(0x11, 0x03)  # Data entry mode setting 0x03 = X/Y increment

        self._send_command(0x04)  # Power On
        self._send_command(0x2c, 0x3c)  # VCOM Register, 0x3c = -1.5v?

        self._send_command(0x3c, 0x00)
        self._send_command(0x3c, 0xFF)

        self._send_command(0x32, self._luts['default'])  # Set LUTs

        self._send_command(0x44, [0x00, (self.cols // 8) - 1])  # Set RAM X Start/End
        self._send_command(0x45, [0x00, 0x00] + packed_height)  # Set RAM Y Start/End

        # 0x24 == RAM B/W, 0x26 == RAM Red
        for data in ((0x24, buf_a), (0x26, buf_b)):
            cmd, buf = data
            self._send_command(0x4e, 0x00)  # Set RAM X Pointer Start
            self._send_command(0x4f, [0x00, 0x00])  # Set RAM Y Pointer Start
            self._send_command(cmd, buf)

        self._send_command(0x22, 0xc7)  # Display Update Sequence
        self._send_command(0x20)  # Trigger Display Update
        time.sleep(0.05)
        self._busy_wait()
        self._send_command(0x10, 0x01)  # Enter Deep Sleep

    def set_pixel(self, x, y, v):
        if v in (WHITE, BLACK, RED):
            self.buf[y][x] = v

    def _rotate_buf(self, matrix, degree=0):
        if degree not in [0, 90, 180, 270, 360]:
            raise ValueError
        return matrix if not degree else self._rotate_buf(zip(*matrix[::-1]), degree-90)

    def show(self):
        region = self.buf

        if self.rotation:
            region = self._rotate_buf(region, self.rotation)

        buf_a = []
        buf_b = []

        for row in region:
            for cell in region:
                if cell == BLACK:
                    buf_a.append(1)
                else:
                    buf_a.append(0)
                if cell == RED:
                    buf_b.append(1)
                else:
                    buf_b.append(0)

        self._update(buf_a, buf_b)

    def _spi_write(self, dc, values):
        self._spi.write(data, dc)

    def _send_command(self, command, data=None):
        self._spi_write(_SPI_COMMAND, [command])
        if data is not None:
            self._send_data(data)

    def _send_data(self, data):
        if isinstance(data, int):
            data = [data]
            self._spi_write(_SPI_DATA, data)


epd = _EPD(spi=EPSPI(), cs_pin=Pin(15, Pin.OUT), reset_pin=Pin(0, Pin.OUT), busy_pin=Pin(16, Pin.IN))
