from time import perf_counter


class Timer:
    def __init__(self) -> None:
        self.started = perf_counter()

    def ms(self) -> int:
        return round((perf_counter() - self.started) * 1000)
