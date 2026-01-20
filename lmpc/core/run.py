from lmpc.core.base import (
    _Metrics,
    BaseDataModule,
    BasePlatformModule,
    BaseTestModule
)


class Evaluator:
    """Class for evaluating model performance."""

    def __init__(
        self,
        data: BaseDataModule,
        platforms: list[BasePlatformModule],
        tests: list[BaseTestModule],
    ):
        self.data = data
        self.platforms = platforms
        self.tests = tests

    def evaluate(self) -> None:
        """Evaluate the model using the provided metrics."""
        pass

    def export_report(self, filepath: str) -> None:
        """Export the evaluation report to a file.

        Args:
            filepath (str): Path to the file where the report will be saved.
        """
        pass
