import os
import random
import dataclasses as dc
import meerk40t.device.lhystudios.laserspeed as tested
import pytest

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "codes.fixture")


@dc.dataclass
class FixtureLine:
    code: str
    board: str
    speed: float
    step: int

    @classmethod
    def from_text_line(cls, line: str):
        code, board, speed, step = line.split(" ")
        return cls(code, board, float(speed), int(step))

    def as_laserspeed(self):
        return tested.LaserSpeed(
            board=self.board, speed=self.speed, raster_step=self.step
        )


with open(FIXTURE_PATH, "r") as file:
    lines = file.read().splitlines()
    codes_fixtures = [
        FixtureLine.from_text_line(line) for line in lines if "#" not in line
    ]

codes_fixtures = [FixtureLine.from_text_line("CV2470262035000011 B1 34 0")]


@pytest.mark.parametrize("code_fixture", codes_fixtures)
class TestLaserSpeedDecoding:
    def test_speedvalue(self, code_fixture):
        result = code_fixture.as_laserspeed().speedcode

        if "G" in result:
            assert pytest.approx(
                tested.LaserSpeed.decode_16bit(result[1:7]), rel=1
            ) == tested.LaserSpeed.decode_16bit(code_fixture.code[1:7])

        else:
            if "V167" not in result:
                assert pytest.approx(
                    tested.LaserSpeed.decode_16bit(result[2:8]), rel=1
                ) == tested.LaserSpeed.decode_16bit(code_fixture.code[2:8])

    def test_generate_gearing(self, code_fixture):
        result = code_fixture.as_laserspeed().speedcode

        if "G" in result:
            assert result[7] == code_fixture.code[7]
        else:
            if "V167" not in result:
                assert result[8] == code_fixture.code[8]

    def test_generate_step(self, code_fixture):
        result = code_fixture.as_laserspeed().speedcode
        if "G" in result:
            return
        if "V167" not in result:
            assert result[9:12] == code_fixture.code[9:12]

    def test_generate_diagonal(self, code_fixture):
        result = code_fixture.as_laserspeed().speedcode
        if "G" in result:
            return
        if "V167" not in result:
            v0 = tested.LaserSpeed.decode_16bit(result[12:18])
            v1 = tested.LaserSpeed.decode_16bit(code_fixture.code[12:18])
            delta = max(1.0, v1 / 3000)
            print(delta)
            assert pytest.approx(v0, rel=delta) == v1

    def test_decode_speedcode(self, code_fixture):
        result = tested.LaserSpeed.get_speed_from_code(
            code_fixture.code, board=code_fixture.board
        )
        # print("%s %s  %f ~= %f" % (board, speed_code, mm_per_second, determined_speed))
        if "G" not in code_fixture.code and code_fixture.speed > 240:
            return
            # In these cases the given speed code is for ~19.05 mm/second.
        if "G" in code_fixture.code and code_fixture.speed < 7:
            return
            # In these case the given speed code is much higher than requested, ambiguous.
        assert pytest.approx(result, rel=code_fixture.speed / 100) == code_fixture.speed


class TestFull:
    @pytest.mark.parametrize("x", random.sample(range(1, 2400, 3), 10))
    @pytest.mark.parametrize("board", ["A", "B", "B1", "B2", "M", "M1", "M2"])
    def test_full_circle(self, x, board):
        speed = x / 10.0
        speedcode = tested.LaserSpeed(board=board, speed=speed).speedcode
        determined_speed = tested.LaserSpeed.get_speed_from_code(speedcode, board)
        assert pytest.approx(speed, rel=speed / 200) == determined_speed

    @pytest.mark.parametrize(
        "x",
        random.sample(range(0, 25000, 7), 10),
    )
    @pytest.mark.parametrize("board", ["A", "B", "B1", "B2", "M", "M1", "M2"])
    def test_validate_speeds(self, x, board):
        speed = x / 100.0
        i_speed = speed
        speed_code = tested.LaserSpeed.get_code_from_speed(
            speed, board=board, fix_lows=True
        )
        # print("%s %f %f %f = %s" % (board, i_speed, speed, validated_speed, speed_code))
        if speed_code[-1] == "C":
            speed_code = speed_code[:-1]
        assert len(speed_code) == 18 or len(speed_code) == 9

    @pytest.mark.parametrize(
        "x",
        random.sample(range(1, 2400, 3), 10),
    )
    @pytest.mark.parametrize("board", ["B2", "M", "M1", "M2"])
    def test_full_circle_gear0(self, x, board):
        speed = x / 10.0
        speed_code = tested.LaserSpeed.get_code_from_speed(
            speed, board=board, acceleration=1, suffix_c=True
        )
        determined_speed = tested.LaserSpeed.get_speed_from_code(speed_code, board)
        assert pytest.approx(speed, rel=speed / 100) == determined_speed

    @pytest.mark.parametrize(
        "x",
        random.sample(range(1, 2400, 3), 10),
    )
    @pytest.mark.parametrize("accel", [1, 2, 3, 4])
    @pytest.mark.parametrize("board", ["A", "B", "B1", "B2", "M", "M1", "M2"])
    def test_full_circle_gearx(self, x, accel, board):
        speed = x / 10.0
        speed_code = tested.LaserSpeed.get_code_from_speed(
            speed, board=board, acceleration=1, suffix_c=False
        )
        determined_speed = tested.LaserSpeed.get_speed_from_code(speed_code, board)
        # print("%s %s  %f ~= %f" % (board, speed_code, speed, determined_speed))
        assert pytest.approx(speed, rel=speed / 100) == determined_speed

    @pytest.mark.parametrize(
        "x",
        random.sample(range(140, 5000, 3), 10),
    )
    @pytest.mark.parametrize("board", ["A", "B", "B1", "B2", "M", "M1", "M2"])
    def test_full_circle_raster(self, x, board):
        speed = x / 10.0
        speed_code = tested.LaserSpeed.get_code_from_speed(
            speed, raster_step=2, board=board
        )
        determined_speed = tested.LaserSpeed.get_speed_from_code(speed_code, board)
        # print("%s %s  %f ~= %f" % (board, speed_code, speed, determined_speed))
        assert pytest.approx(speed, rel=speed / 100) == determined_speed

    @pytest.mark.parametrize(
        "x",
        random.sample(range(140, 5000, 3), 10),
    )
    @pytest.mark.parametrize("board", ["A", "B", "B1", "B2", "M", "M1", "M2"])
    def test_full_circle_raster_uni(self, x, board):
        speed = x / 10.0
        laserspeed1 = tested.LaserSpeed(board, speed, raster_step=(2, 1))
        speed_text = str(laserspeed1)
        laserspeed2 = tested.LaserSpeed(board, speed_text)
        determined_speed = laserspeed2.speed
        # print("%s %s  %f ~= %f" % (board, laserspeed.speedcode, speed, determined_speed))
        assert pytest.approx(speed, rel=speed / 100) == determined_speed
        assert laserspeed2.raster_step == (2, 1)

    @pytest.mark.parametrize("speed", random.sample(range(1, 1000), 10))
    def test_ratio_flaw(self, speed):
        flaw = 0.919493599053179
        speed = speed / 10.0
        speed_code = tested.LaserSpeed.get_code_from_speed(
            speed, board="M2", fix_speeds=False
        )
        determined_speed = tested.LaserSpeed.get_speed_from_code(
            speed_code, board="M2", fix_speeds=True
        )
        determined_speed /= flaw
        assert pytest.approx(speed, rel=speed / 100) == determined_speed
