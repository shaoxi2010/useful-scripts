import numpy as np
import matplotlib.pyplot as plt
from argparse import ArgumentParser


def pwl_data_gen(
    bandrate: int,
    waves: int,
    v_low: float,
    v_high: float,
    bits: int = 7,
    rise_time=2e-9,
    fall_time=2e-9,
):
    if 1 / bandrate < rise_time + fall_time:
        raise ValueError("Bandrate is too low for the given rise and fall times.")
    sequence = np.random.randint(1, bits, waves)
    bittime = 1 / bandrate
    costtime = 0
    timebase = []
    value = []
    for count in sequence:
        time = bittime * count
        timebase.append(costtime + rise_time)
        timebase.append(costtime + time - fall_time)
        costtime += time
    for i in range(len(timebase) // 2):
        value.append(v_low if i % 2 == 0 else v_high)
        value.append(v_low if i % 2 == 0 else v_high)
    return np.array(timebase), np.array(value)


def PWL_file_gen(
    timebase: np.array,
    value: np.array,
    filename: str,
):
    with open(filename, "w") as f:
        for i in range(len(timebase)):
            f.write(f"{timebase[i]} {value[i]}\n")

parser = ArgumentParser()
parser.add_argument("bandrate", type=float, help="Bandrate in Hz")
parser.add_argument("waves", type=int, help="Number of waves")
parser.add_argument("v_low", type=float, help="Low voltage")
parser.add_argument("v_high", type=float, help="High voltage")
parser.add_argument("filename", type=str, help="Output filename")
parser.add_argument("--bits", type=int, default=7, help="Max continue bits")
parser.add_argument(
    "--rise_time", type=float, default=2e-9, help="Rise time in s default=2ns"
)
parser.add_argument(
    "--fall_time", type=float, default=2e-9, help="Fall time in s default=2ns"
)
parser.add_argument("--plot", action="store_true", help="Plot the data")

if __name__ == "__main__":
    # print(pwl_data_gen(1e9, 1000, 1, 0))
    args = parser.parse_args()
    timebase, value = pwl_data_gen(
        args.bandrate,
        args.waves,
        args.v_low,
        args.v_high,
        args.bits,
        args.rise_time,
        args.fall_time,
    )
    if args.plot:
        plt.plot(timebase, value)
        plt.xlabel("Time [s]")
        plt.ylabel("Voltage [V]")
        plt.show()
    PWL_file_gen(timebase, value, args.filename)